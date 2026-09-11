"""Convert CIC-IDS2017 flow-record CSV rows into SAT-SA canonical
alert dicts (the shape ``satsa.ingest`` expects — see
``satsa/ingest/spec.py``'s ``ALERT_FIELDS``).

Schema note (read before trusting a parse failure is a real-data bug):
the dataset's official CSVs are notoriously inconsistent about leading
whitespace in column headers across mirrors (``" Destination Port"``
vs. ``"Destination Port"``). This module normalizes every header by
stripping whitespace and matching case-insensitively, so that
inconsistency should never itself cause a parse failure.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from public_benchmarks.provenance import source_derived

SOURCE_DATASET = "CIC-IDS2017"

# The only columns this adapter actually needs. Every other CICFlowMeter
# feature column (there are dozens) is ignored — SAT-SA's alert model has
# no use for raw flow statistics, only the supervisory-relevant fields.
REQUIRED_COLUMNS = ("destination ip", "timestamp", "label")
OPTIONAL_COLUMNS = ("source ip", "destination port", "protocol")

# Attack-type -> SAT-SA severity. Deliberately conservative and named
# per attack family, not invented per-row. An unrecognized non-BENIGN
# label maps to "medium" with a warning surfaced by convert() rather
# than silently guessing "low" (matches satsa.ingest.spec's own
# "unrecognized -> unknown + warning" discipline for severities it
# cannot classify — here we choose a safe non-"unknown" default
# because CIC-IDS2017 guarantees every non-BENIGN row *is* an attack,
# just possibly one this map doesn't yet name).
ATTACK_SEVERITY = {
    "ddos": "critical",
    "dos hulk": "critical",
    "dos goldeneye": "critical",
    "dos slowloris": "high",
    "dos slowhttptest": "high",
    "heartbleed": "critical",
    "bot": "critical",
    "infiltration": "critical",
    "portscan": "medium",
    "web attack - brute force": "high",
    "web attack - xss": "high",
    "web attack - sql injection": "critical",
    "ftp-patator": "high",
    "ssh-patator": "high",
}

BENIGN_LABEL = "benign"

# CIC-IDS2017 timestamp formats seen across the official files and
# common mirrors — tried in order; the first that parses wins. A
# timestamp matching none of these is a real, surfaced parse error,
# never silently defaulted.
_TIMESTAMP_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
)


class CicIds2017ParseError(ValueError):
    pass


@dataclass
class ConvertReport:
    rows_read: int = 0
    alerts_emitted: int = 0
    benign_skipped: int = 0
    rejected: list = None  # [{row, reason}]
    unrecognized_labels: dict = None  # {label: count}

    def __post_init__(self):
        if self.rejected is None:
            self.rejected = []
        if self.unrecognized_labels is None:
            self.unrecognized_labels = {}

    def to_dict(self) -> dict:
        return {
            "rows_read": self.rows_read,
            "alerts_emitted": self.alerts_emitted,
            "benign_skipped": self.benign_skipped,
            "rejected": list(self.rejected),
            "unrecognized_labels": dict(self.unrecognized_labels),
        }


def _normalize_headers(fieldnames) -> dict:
    """Map normalized-lowercase-stripped header -> original header."""
    return {str(h).strip().lower(): h for h in (fieldnames or [])}


def _parse_timestamp(raw: str) -> float:
    raw = (raw or "").strip()
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt).timestamp()
        except ValueError:
            continue
    raise CicIds2017ParseError(f"unrecognized timestamp format: {raw!r}")


def _severity_for(label: str) -> tuple:
    """(severity, recognized)."""
    key = label.strip().lower()
    if key in ATTACK_SEVERITY:
        return ATTACK_SEVERITY[key], True
    return "medium", False


def _native_id(source_name: str, row_index: int) -> str:
    """Deterministic, reproducible given the same file and row
    position — not random, so re-running the adapter on the same file
    produces the same native_ids."""
    return f"cicids-{source_name}-{row_index}"


def parse_rows(rows: list, *, source_name: str) -> tuple:
    """Convert already-parsed CSV row dicts (normalized-lowercase-key
    -> value) into (alert_dicts, ConvertReport). Pure function — no
    file I/O — so it is directly testable against hand-built rows."""
    report = ConvertReport()
    alerts: list = []
    for i, row in enumerate(rows):
        report.rows_read += 1
        missing = [c for c in REQUIRED_COLUMNS if c not in row]
        if missing:
            report.rejected.append({
                "row": i, "reason": f"missing required column(s): {missing}"})
            continue
        label = str(row["label"]).strip()
        if label.lower() == BENIGN_LABEL:
            report.benign_skipped += 1
            continue
        try:
            created_at = _parse_timestamp(row["timestamp"])
        except CicIds2017ParseError as exc:
            report.rejected.append({"row": i, "reason": str(exc)})
            continue
        dest_ip = str(row["destination ip"]).strip()
        if not dest_ip:
            report.rejected.append({
                "row": i, "reason": "empty destination ip"})
            continue
        severity, recognized = _severity_for(label)
        if not recognized:
            report.unrecognized_labels[label] = (
                report.unrecognized_labels.get(label, 0) + 1)
        alerts.append({
            "native_id": _native_id(source_name, i),
            "created_at": created_at,
            "severity": severity,
            "category": label,
            "asset_ids": [dest_ip],
            "provenance": source_derived(SOURCE_DATASET).to_dict(),
        })
        report.alerts_emitted += 1
    return alerts, report


def convert_file(path: Path) -> tuple:
    """Read a real CIC-IDS2017 CSV file and convert it. See this
    module's docstring: not yet run against an actual downloaded
    dataset file in this development environment — schema-conformant
    against the documented column layout, verified via
    ``parse_rows()`` against hand-built sample rows in the test
    suite."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header_map = _normalize_headers(reader.fieldnames)
        rows = []
        for raw_row in reader:
            normalized = {}
            for norm_key, orig_key in header_map.items():
                normalized[norm_key] = raw_row.get(orig_key, "")
            rows.append(normalized)
    return parse_rows(rows, source_name=path.stem)


def to_alerts_csv(alerts: list) -> str:
    """Render converted alerts as a satsa.ingest-ready alerts.csv
    body (native_id,created_at,severity,category,asset_ids). Uses the
    csv module (not manual string joins) so a category name that ever
    contains a comma or quote is escaped correctly rather than
    corrupting the file."""
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["native_id", "created_at", "severity", "category", "asset_ids"])
    for a in alerts:
        writer.writerow([
            a["native_id"], a["created_at"], a["severity"], a["category"],
            ";".join(a["asset_ids"]),
        ])
    return buf.getvalue()

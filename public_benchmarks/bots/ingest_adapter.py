"""Convert Splunk BOTS-style notable-event JSON records into SAT-SA
canonical alert dicts (see ``satsa/ingest/spec.py``'s ``ALERT_FIELDS``).

Input shape: one JSON object per line (or a JSON array of objects) in
Splunk Enterprise Security's standard notable-event field layout:
``_time``, ``search_name`` (or ``signature``), ``urgency`` (or
``severity``), ``dest`` (and optionally ``src``). This is Splunk's own
documented, stable notable-event schema — not something invented for
this adapter — but see this package's ``__init__.py`` for the
disclosed limitation: not run against an actual downloaded BOTS
export in this development environment.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from public_benchmarks.provenance import source_derived

DEFAULT_SOURCE_DATASET = "Splunk BOTS"

REQUIRED_FIELDS = ("_time", "dest")

# Splunk ES's standard urgency vocabulary maps almost 1:1 onto SAT-SA's
# severities; only "informational" needs renaming.
URGENCY_TO_SEVERITY = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
    "info": "info",
}


class BotsParseError(ValueError):
    pass


@dataclass
class ConvertReport:
    rows_read: int = 0
    alerts_emitted: int = 0
    rejected: list = None
    unrecognized_urgency: dict = None

    def __post_init__(self):
        if self.rejected is None:
            self.rejected = []
        if self.unrecognized_urgency is None:
            self.unrecognized_urgency = {}

    def to_dict(self) -> dict:
        return {
            "rows_read": self.rows_read,
            "alerts_emitted": self.alerts_emitted,
            "rejected": list(self.rejected),
            "unrecognized_urgency": dict(self.unrecognized_urgency),
        }


def _parse_time(raw) -> float:
    """``_time`` in a Splunk export is usually an epoch number (int or
    numeric string), occasionally an ISO-8601 string when exported via
    some report formats. Both are accepted; anything else is a real,
    surfaced parse error."""
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    try:
        return float(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.split("+")[0].split("Z")[0], fmt).timestamp()
        except ValueError:
            continue
    raise BotsParseError(f"unrecognized _time value: {raw!r}")


def _severity_for(urgency: Optional[str]) -> tuple:
    """(severity, recognized). Missing urgency is treated as
    unrecognized -> "unknown", matching satsa.ingest.spec's own
    convention for a severity that cannot be classified — never
    guessed."""
    if not urgency:
        return "unknown", False
    key = str(urgency).strip().lower()
    if key in URGENCY_TO_SEVERITY:
        return URGENCY_TO_SEVERITY[key], True
    return "unknown", False


def _native_id(source_name: str, row_index: int, row: dict) -> str:
    """Prefer the event's own stable identifier if the export carries
    one (``event_id`` or Splunk's internal ``_cd``); otherwise fall
    back to a deterministic hash of the row's own content plus
    position, so re-running the adapter on the same export is
    reproducible."""
    for key in ("event_id", "_cd"):
        if row.get(key):
            return f"bots-{row[key]}"
    basis = json.dumps(row, sort_keys=True, default=str)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"bots-{source_name}-{row_index}-{digest}"


def parse_rows(rows: list, *, source_name: str,
               source_dataset: str = DEFAULT_SOURCE_DATASET) -> tuple:
    """Convert already-parsed notable-event dicts into
    (alert_dicts, ConvertReport). Pure function, directly testable
    against hand-built rows."""
    report = ConvertReport()
    alerts: list = []
    for i, row in enumerate(rows):
        report.rows_read += 1
        missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
        if missing:
            report.rejected.append({
                "row": i, "reason": f"missing required field(s): {missing}"})
            continue
        try:
            created_at = _parse_time(row["_time"])
        except BotsParseError as exc:
            report.rejected.append({"row": i, "reason": str(exc)})
            continue
        dest = str(row["dest"]).strip()
        if not dest:
            report.rejected.append({"row": i, "reason": "empty dest"})
            continue
        urgency = row.get("urgency") or row.get("severity")
        severity, recognized = _severity_for(urgency)
        if not recognized:
            key = str(urgency) if urgency else "(missing)"
            report.unrecognized_urgency[key] = (
                report.unrecognized_urgency.get(key, 0) + 1)
        category = row.get("search_name") or row.get("signature") or "unspecified"
        asset_ids = [dest]
        if row.get("src") and str(row["src"]).strip() != dest:
            asset_ids.append(str(row["src"]).strip())
        alerts.append({
            "native_id": _native_id(source_name, i, row),
            "created_at": created_at,
            "severity": severity,
            "category": category,
            "asset_ids": asset_ids,
            "provenance": source_derived(source_dataset).to_dict(),
        })
        report.alerts_emitted += 1
    return alerts, report


def convert_jsonl(path: Path, *,
                  source_dataset: str = DEFAULT_SOURCE_DATASET) -> tuple:
    """Read a newline-delimited-JSON BOTS notable-event export and
    convert it. Also accepts a single JSON array in the same file.
    See this module's docstring for the disclosed
    not-run-against-real-data boundary."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.strip()
    if stripped.startswith("["):
        rows = json.loads(stripped)
    else:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return parse_rows(rows, source_name=path.stem, source_dataset=source_dataset)


def to_alerts_csv(alerts: list) -> str:
    """Render converted alerts as a satsa.ingest-ready alerts.csv
    body (native_id,created_at,severity,category,asset_ids)."""
    import csv
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

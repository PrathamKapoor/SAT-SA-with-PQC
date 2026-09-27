"""Map the UCI incident-management event log to SAT-SA submissions.

Source: Amaral, C., Fantinato, M., Peres, S. (2018). *Incident management
process enriched event log*. UCI Machine Learning Repository,
https://doi.org/10.24432/C57S4H, licence CC BY 4.0. Every mapped record is
``derived_from_source``: it is computed from a real event row; nothing is
invented. The original file is read, never modified; derived submissions are
written to a separate directory with a transformation report.

Mapping (adapter version ``uci498-adapter/1``):

* entity = the incident's final ``assignment_group`` (the resolver group);
  incidents whose final group is unknown (``?``) are excluded.
* incident -> one alert and one case with the same native id.
  - alert.created_at = ``opened_at``; severity from ``priority``;
    acknowledged_at = ``sys_updated_at`` of the first event whose state is
    not ``New``; closed_at = ``resolved_at``.
  - case.opened_at = ``opened_at``; closed_at = ``closed_at``;
    status ``closed`` when a closure time exists.
* each event in state ``Active`` or ``Awaiting *`` -> one investigation step
  (action = state, performed_at = ``sys_updated_at``, sequence =
  ``sys_mod_count``, analyst = ``sys_updated_by`` pseudonym).
* each increase of ``reassignment_count`` -> one escalation record. This is a
  *proxy*: a reassignment moves work between groups; it is not necessarily a
  severity escalation.
* closure -> one disposition with outcome ``other`` (closure codes in the
  source are anonymized) and the code as reason.
* Not mapped: assets (``cmdb_ci`` is known for 54 of 24,918 incidents),
  caller, location, category, symptom, knowledge, vendor and problem fields.
* ``made_sla`` is **never** written into a submission; it is kept only in
  the separate label file as an independent operational outcome.

Timestamps are ``d/m/Y H:M`` without a zone; they are interpreted as UTC.
Values that would violate SAT-SA chronology (acknowledgement before opening,
resolution before acknowledgement, closure before opening) are set to empty
and counted in the transformation report rather than altered.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from public_benchmarks.provenance import source_derived

ADAPTER_VERSION = "uci498-adapter/1"
SOURCE_DATASET = "UCI-498 incident management process enriched event log"
SOURCE = {
    "name": "Incident management process enriched event log",
    "creators": "Amaral, C., Fantinato, M., Peres, S.",
    "year": 2018,
    "doi": "10.24432/C57S4H",
    "landing_page": "https://archive.ics.uci.edu/dataset/498",
    "download_url": (
        "https://archive.ics.uci.edu/static/public/498/"
        "incident+management+process+enriched+event+log.zip"
    ),
    "license": "CC BY 4.0",
    "domain": "IT service management (ServiceNow), not a security operations centre",
}
FIELDS_USED = (
    "number",
    "incident_state",
    "reassignment_count",
    "sys_mod_count",
    "sys_updated_at",
    "sys_updated_by",
    "opened_at",
    "priority",
    "assignment_group",
    "resolved_at",
    "closed_at",
    "closed_code",
)
LABEL_FIELDS = ("made_sla",)
SEVERITY = {
    "1 - Critical": "critical",
    "2 - High": "high",
    "3 - Moderate": "medium",
    "4 - Low": "low",
}
WORK_STATES = {
    "Active",
    "Awaiting User Info",
    "Awaiting Vendor",
    "Awaiting Problem",
    "Awaiting Evidence",
}


def parse_time(value: str) -> float | None:
    if not value or value == "?":
        return None
    return (
        datetime.strptime(value, "%d/%m/%Y %H:%M")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_incidents(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    """Group event rows by incident, ordered by modification count/time."""
    incidents: dict[str, list[dict[str, str]]] = defaultdict(list)
    with Path(csv_path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            incidents[row["number"]].append(row)
    for events in incidents.values():
        events.sort(
            key=lambda e: (
                int(e["sys_mod_count"]),
                parse_time(e["sys_updated_at"]) or 0,
            )
        )
    return dict(incidents)


def map_incident(
    number: str, events: list[dict[str, str]], adjustments: Counter
) -> dict[str, Any]:
    """Map one incident's events to SAT-SA records (no label fields)."""
    last = events[-1]
    opened = parse_time(last["opened_at"])
    resolved = parse_time(last["resolved_at"])
    closed = parse_time(last["closed_at"])
    ack = next(
        (
            parse_time(e["sys_updated_at"])
            for e in events
            if e["incident_state"] != "New"
        ),
        None,
    )
    if ack is not None and opened is not None and ack < opened:
        adjustments["acknowledgement_before_opening_dropped"] += 1
        ack = None
    if resolved is not None and ack is not None and resolved < ack:
        adjustments["resolution_before_acknowledgement_dropped"] += 1
        resolved = None
    if resolved is not None and opened is not None and resolved < opened:
        adjustments["resolution_before_opening_dropped"] += 1
        resolved = None
    if closed is not None and opened is not None and closed < opened:
        adjustments["closure_before_opening_dropped"] += 1
        closed = None
    if resolved is None:
        adjustments["no_resolution_time"] += 1
    severity = SEVERITY.get(last["priority"], "")
    alert = {
        "native_id": number,
        "created_at": opened,
        "severity": severity,
        "ack_at": ack if ack is not None else "",
        "closed_at": resolved if resolved is not None else "",
        "case_id": number,
        "asset_id": "",
    }
    case = {
        "native_id": number,
        "opened_at": opened,
        "status": "closed" if closed is not None else "open",
        "closed_at": closed,
        "owner": last["sys_updated_by"],
        "alert_ids": [number],
        "closure_reason": last["closed_code"],
    }
    steps = []
    seen_steps = set()
    for event in events:
        if event["incident_state"] not in WORK_STATES:
            continue
        key = (event["incident_state"], event["sys_updated_at"], event["sys_mod_count"])
        if key in seen_steps:
            adjustments["duplicate_step_events_merged"] += 1
            continue
        seen_steps.add(key)
        steps.append(
            {
                "case_id": number,
                "action_type": event["incident_state"].lower().replace(" ", "_"),
                "performed_at": parse_time(event["sys_updated_at"]),
                "sequence": int(event["sys_mod_count"]),
                "analyst": event["sys_updated_by"],
                "note": "",
                "evidence_ids": "",
            }
        )
    escalations = []
    previous = None
    for event in events:
        count = int(event["reassignment_count"])
        if previous is not None and count > previous:
            escalations.append(
                {
                    "alert_id": number,
                    "case_id": number,
                    "occurred_at": parse_time(event["sys_updated_at"]),
                    "destination": "reassigned-group",
                    "trigger": "reassignment",
                    "outcome": "reassigned",
                }
            )
        previous = count
    dispositions = []
    if closed is not None:
        dispositions.append(
            {
                "alert_id": number,
                "case_id": number,
                "occurred_at": closed,
                "outcome": "other",
                "reason": last["closed_code"],
                "approver": "",
            }
        )
    return {
        "group": last["assignment_group"],
        "alert": alert,
        "case": case,
        "steps": steps,
        "escalations": escalations,
        "dispositions": dispositions,
        "label": {
            "incident": number,
            "made_sla_final": last["made_sla"] == "true",
            "sla_missed": last["made_sla"] == "false",
        },
    }


def build_submissions(
    csv_path: Path, out_dir: Path, *, min_incidents: int = 30
) -> dict[str, Any]:
    """Write one SAT-SA submission directory per eligible group.

    Returns (and writes) the transformation report. ``out_dir`` must not
    contain the original file.
    """
    from satsa.analysis.synth import _CSE, _write_cse

    csv_path = Path(csv_path)
    out_dir = Path(out_dir)
    if out_dir.resolve() == csv_path.parent.resolve():
        raise ValueError("derived output must be separate from the original data")
    incidents = load_incidents(csv_path)
    adjustments: Counter = Counter()
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for number, events in sorted(incidents.items()):
        mapped = map_incident(number, events, adjustments)
        by_group[mapped["group"]].append(mapped)
    excluded_unknown = len(by_group.pop("?", []))
    eligible = {g: rows for g, rows in by_group.items() if len(rows) >= min_incidents}
    out_dir.mkdir(parents=True, exist_ok=True)
    labels: dict[str, Any] = {}
    period_start = min(
        m["alert"]["created_at"] for rows in eligible.values() for m in rows
    )
    period_end = (
        max(
            max(
                v
                for v in (
                    m["alert"]["created_at"],
                    m["case"]["closed_at"],
                    *(s["performed_at"] for s in m["steps"]),
                )
                if v not in (None, "")
            )
            for rows in eligible.values()
            for m in rows
        )
        + 86400
    )
    for group, rows in sorted(eligible.items()):
        slug = group.replace(" ", "_")
        cse = _CSE(
            name=f"ITSM-{slug}",
            sector="itsm-public-dataset",
            environment="uci-498",
            assets=[],
            alerts=[m["alert"] for m in rows],
            cases=[m["case"] for m in rows],
            steps=[s for m in rows for s in m["steps"]],
            escalations=[e for m in rows for e in m["escalations"]],
            dispositions=[d for m in rows for d in m["dispositions"]],
        )
        _write_cse(cse, out_dir / "submissions" / slug)
        # An empty assets.csv would read as "category submitted but empty";
        # assets are genuinely not mapped, so the file is removed.
        (out_dir / "submissions" / slug / "assets.csv").unlink()
        missed = sum(m["label"]["sla_missed"] for m in rows)
        labels[group] = {
            "incidents": len(rows),
            "sla_missed": missed,
            "sla_miss_rate": missed / len(rows),
        }
    report = {
        "adapter_version": ADAPTER_VERSION,
        "source": SOURCE,
        "source_file": csv_path.name,
        "source_file_sha256": sha256_file(csv_path),
        "provenance": source_derived(SOURCE_DATASET).to_dict(),
        "fields_used": list(FIELDS_USED),
        "label_fields_kept_separately": list(LABEL_FIELDS),
        "fields_discarded": "all other source columns",
        "timezone_assumption": "UTC",
        "entity_definition": "final assignment_group of each incident",
        "min_incidents_per_entity": min_incidents,
        "incidents_total": len(incidents),
        "incidents_unknown_group_excluded": excluded_unknown,
        "groups_total": len(by_group),
        "groups_eligible": len(eligible),
        "incidents_in_eligible_groups": sum(len(r) for r in eligible.values()),
        "assessment_period": {"start": period_start, "end": period_end},
        "chronology_adjustments": dict(sorted(adjustments.items())),
        "mapped_counts": {
            "alerts": sum(len(r) for r in eligible.values()),
            "investigation_steps": sum(
                len(m["steps"]) for r in eligible.values() for m in r
            ),
            "escalations_from_reassignment": sum(
                len(m["escalations"]) for r in eligible.values() for m in r
            ),
            "dispositions": sum(
                len(m["dispositions"]) for r in eligible.values() for m in r
            ),
        },
    }
    (out_dir / "labels.json").write_text(
        json.dumps(
            {
                "label": "final made_sla flag (false = SLA missed), per incident "
                "aggregated per group; never shown to SAT-SA",
                "groups": labels,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (out_dir / "transformation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report

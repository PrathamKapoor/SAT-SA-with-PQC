"""Canonical ingestion field specs for the six SIH input categories.

Each category declares the column/field names a submission file uses, which
are required (absence rejects the row, never silently defaults), how to
coerce timestamps, and the severity vocabulary mapping. This keeps every
normalization rule in one inspectable place (Rule 2: no hidden logic).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Severity mapping. Native strings are free text; mapped_severity is one of
# SEVERITIES below. Unmapped native values map to "unknown" plus a warning
# (never silently coerced to a real severity).
SEVERITIES = ("critical", "high", "medium", "low", "info", "unknown")

SEVERITY_MAP = {
    "critical": "critical", "crit": "critical", "p1": "critical", "sev1": "critical",
    "severity 1": "critical", "1": "critical",
    "high": "high", "p2": "high", "sev2": "high", "severity 2": "high", "2": "high",
    "medium": "medium", "med": "medium", "moderate": "medium", "p3": "medium",
    "sev3": "medium", "severity 3": "medium", "3": "medium",
    "low": "low", "p4": "low", "sev4": "low", "severity 4": "low", "4": "low",
    "info": "info", "informational": "info", "information": "info", "p5": "info",
    "sev5": "info", "5": "info",
}

CASE_STATUSES = ("open", "in_progress", "closed", "merged", "on_hold")

DISPOSITION_CATEGORIES = (
    "true_positive", "false_positive", "benign", "duplicate", "test",
    "suppressed", "no_action", "other", "unknown",
)

DISPOSITION_MAP = {
    "true positive": "true_positive", "true_positive": "true_positive", "tp": "true_positive",
    "false positive": "false_positive", "false_positive": "false_positive", "fp": "false_positive",
    "benign": "benign", "duplicate": "duplicate", "dup": "duplicate",
    "test": "test", "testing": "test", "suppressed": "suppressed",
    "no action": "no_action", "no_action": "no_action", "none": "no_action",
    "other": "other", "unknown": "unknown",
}

ASSET_CRITICALITIES = ("critical", "high", "medium", "low", "unknown")
CRITICALITY_MAP = {
    "critical": "critical", "crit": "critical", "tier1": "critical", "tier 1": "critical",
    "high": "high", "important": "high", "tier2": "high", "tier 2": "high",
    "medium": "medium", "moderate": "medium", "tier3": "medium", "tier 3": "medium",
    "low": "low", "tier4": "low", "tier 4": "low",
}

# The six SIH categories and the filename bases a submission directory may use.
CATEGORIES = ("alerts", "cases", "investigation_steps", "escalations",
              "dispositions", "assets")


@dataclass(frozen=True)
class FieldSpec:
    """One canonical field: accepted column aliases, requiredness, type."""
    name: str
    aliases: tuple = ()
    required: bool = False
    kind: str = "str"          # str | float | int | list | record
    default: Optional[object] = None

    def all_names(self) -> tuple:
        return (self.name, *self.aliases)


ALERT_FIELDS = (
    FieldSpec("native_id", ("alert_id", "id", "AlertID"), required=True),
    FieldSpec("created_at", ("timestamp", "time", "created", "raised_at"), required=True, kind="timestamp"),
    FieldSpec("severity", ("native_severity", "priority", "sev")),
    FieldSpec("category", ("native_category", "type", "alert_type")),
    FieldSpec("acknowledged_at", ("ack_at", "acknowledged"), kind="timestamp"),
    FieldSpec("closed_at", ("resolved_at", "closed", "close_time"), kind="timestamp"),
    FieldSpec("case_ids", ("case_id", "cases", "case"), kind="list"),
    FieldSpec("asset_ids", ("assets", "asset", "asset_id", "host", "hostname"), kind="list"),
)

CASE_FIELDS = (
    FieldSpec("native_id", ("case_id", "id", "CaseID"), required=True),
    FieldSpec("opened_at", ("created_at", "opened", "timestamp"), required=True, kind="timestamp"),
    FieldSpec("status", ()),
    FieldSpec("closed_at", ("closed", "resolve_time"), kind="timestamp"),
    FieldSpec("owner", ("owner_pseudonym", "analyst", "assignee")),
    FieldSpec("alert_ids", ("alerts", "alert_id", "alert"), kind="list"),
    FieldSpec("closure_reason", ("reason_notes", "closure_notes")),
)

INVESTIGATION_STEP_FIELDS = (
    FieldSpec("case_id", ("case",), required=True),
    FieldSpec("action_type", ("action", "step_type", "type"), required=True),
    FieldSpec("performed_at", ("timestamp", "time", "performed"), required=True, kind="timestamp"),
    FieldSpec("sequence", ("seq", "order", "step_no"), kind="int"),
    FieldSpec("analyst", ("analyst_pseudonym", "analyst_id", "actor")),
    FieldSpec("note", ("note_text", "notes", "description", "details")),
    FieldSpec("evidence_ids", ("evidence", "evidence_refs"), kind="list"),
)

ESCALATION_FIELDS = (
    FieldSpec("alert_id", ("alert",), kind="str"),
    FieldSpec("case_id", ("case",), kind="str"),
    FieldSpec("occurred_at", ("timestamp", "time", "escalated_at"), required=True, kind="timestamp"),
    FieldSpec("destination_role", ("destination", "escalated_to", "to_role")),
    FieldSpec("trigger", ("reason", "trigger_reason")),
    FieldSpec("outcome", ("result",)),
)

DISPOSITION_FIELDS = (
    FieldSpec("alert_id", ("alert",), kind="str"),
    FieldSpec("case_id", ("case",), kind="str"),
    FieldSpec("occurred_at", ("timestamp", "time", "decided_at"), required=True, kind="timestamp"),
    FieldSpec("outcome", ("category", "verdict", "classification")),
    FieldSpec("reason", ("justification", "notes")),
    FieldSpec("approver_role", ("approver",)),
)

ASSET_FIELDS = (
    FieldSpec("native_id", ("asset_id", "id", "hostname", "host"), required=True),
    FieldSpec("criticality", ("criticality_level", "tier")),
    FieldSpec("environment", ("env", "zone")),
    FieldSpec("controls", ("control_applicability", "applicable_controls"), kind="list"),
)

CATEGORY_FIELDS = {
    "alerts": ALERT_FIELDS,
    "cases": CASE_FIELDS,
    "investigation_steps": INVESTIGATION_STEP_FIELDS,
    "escalations": ESCALATION_FIELDS,
    "dispositions": DISPOSITION_FIELDS,
    "assets": ASSET_FIELDS,
}


def map_severity(raw: str) -> tuple[str, bool]:
    """(mapped, recognized). Unrecognized -> ("unknown", False) + warning upstream."""
    if raw is None or str(raw).strip() == "":
        return "unknown", False
    key = str(raw).strip().lower()
    if key in SEVERITIES:
        return key, True
    mapped = SEVERITY_MAP.get(key)
    return (mapped, True) if mapped else ("unknown", False)


def map_disposition_category(raw: str) -> tuple[str, bool]:
    if raw is None or str(raw).strip() == "":
        return "unknown", False
    key = str(raw).strip().lower()
    if key in DISPOSITION_CATEGORIES:
        return key, True
    mapped = DISPOSITION_MAP.get(key)
    return (mapped, True) if mapped else ("unknown", False)


def map_criticality(raw: str) -> tuple[str, bool]:
    if raw is None or str(raw).strip() == "":
        return "unknown", False
    key = str(raw).strip().lower()
    if key in ASSET_CRITICALITIES:
        return key, True
    mapped = CRITICALITY_MAP.get(key)
    return (mapped, True) if mapped else ("unknown", False)

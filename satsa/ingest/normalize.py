"""Normalization: raw parsed rows -> validated canonical domain records,
with cross-reference resolution and per-record source provenance.

Every decision a row goes through is recorded: accepted rows get a domain
record + SourceRecord; rejected rows are counted and explained (never
silently dropped); warnings capture suspected-but-tolerated issues
(unrecognized severity labels, unresolvable *optional* references). A
mandatory reference that does not resolve rejects the row — an
InvestigationStep cannot exist without its Case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from satsa.domain.entities import Asset
from satsa.domain.evidence import SourceRecord
from satsa.domain.workflow import (
    Alert,
    Case,
    Disposition,
    Escalation,
    InvestigationStep,
)
from satsa.ingest.readers import ParsedFile, RawRow
from satsa.ingest.spec import (
    CATEGORY_FIELDS,
    CASE_STATUSES,
    FieldSpec,
    map_criticality,
    map_disposition_category,
    map_severity,
)


class TimestampError(ValueError):
    pass


def parse_timestamp(value) -> Optional[float]:
    """Epoch seconds (number or numeric string) or ISO-8601 -> epoch float.
    None/empty -> None (caller decides if that is allowed). Naive ISO
    datetimes are interpreted as UTC (submissions are period-bounded; the
    canonical store is epoch-UTC per data-architecture.md)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    iso = text
    if iso.endswith(("Z", "z")):
        iso = iso[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise TimestampError(f"invalid timestamp {text!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def extract_fields(row: RawRow, specs: tuple) -> dict:
    """Pull canonical fields out of a raw row using alias matching.
    Header matching is case/space-insensitive."""
    lookup = {}
    for key, val in row.data.items():
        lookup[str(key).strip().lower().replace(" ", "_").replace("-", "_")] = val
    out = {}
    for spec in specs:
        for name in spec.all_names():
            norm = name.lower()
            if norm in lookup:
                out[spec.name] = lookup[norm]
                break
    return out


def _listify(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    for sep in (";", "|", ","):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]


@dataclass
class RejectedRow:
    category: str
    locator: str
    native_id: str
    reasons: list


@dataclass
class NormResult:
    """Outcome of normalizing one category file."""
    category: str
    records: list = field(default_factory=list)       # accepted domain records
    source_records: list = field(default_factory=list)  # matching SourceRecords
    rejected: list = field(default_factory=list)      # list[RejectedRow]
    warnings: list = field(default_factory=list)      # human-readable strings
    received: int = 0
    accepted_native: list = field(default_factory=list)  # native ids accepted (id-bearing cats)

    def summary(self) -> dict:
        return {
            "present": True,
            "received": self.received,
            "accepted": len(self.records),
            "rejected": len(self.rejected),
            "rejections": [
                {"locator": r.locator, "native_id": r.native_id, "reasons": r.reasons}
                for r in self.rejected
            ],
            "warnings": list(self.warnings),
        }


def _missing_required(fields: dict, specs: tuple) -> list:
    missing = []
    for spec in specs:
        if spec.required:
            v = fields.get(spec.name)
            if v is None or (isinstance(v, str) and not v.strip()):
                missing.append(spec.name)
    return missing


def normalize_category(pf: ParsedFile, *, entity_id: str, assessment_id: str,
                       case_native_to_id: dict, alert_native_to_id: dict,
                       asset_native_to_id: dict, preassigned: dict | None = None,
                       existing_natives: set | None = None) -> NormResult:
    """Normalize one parsed file into domain records + source records.

    case/alert/asset native->internal maps must contain the ids of the
    *persisted* canonical records. ``preassigned`` maps native_id -> internal
    id for id-bearing categories (alerts/cases/assets): the service
    pre-registers these before normalization so mutually-referencing
    categories (alert.case_refs / case.alert_refs) resolve in either parse
    order, then prunes entries for rows normalization rejected."""
    specs = CATEGORY_FIELDS[pf.category]
    preassigned = preassigned or {}
    existing_natives = existing_natives or set()
    res = NormResult(category=pf.category, received=len(pf.rows))
    seen_native: set = set()

    for row in pf.rows:
        fields = extract_fields(row, specs)
        locator = row.locator
        native_ref = str(fields.get("native_id") or fields.get("case_id") or
                         fields.get("alert_id") or "").strip()
        fail: list = []

        for m in _missing_required(fields, specs):
            fail.append(f"missing required field {m!r}")

        # timestamps: parse failures append to `fail`, empty stays None
        def _ts(name):
            try:
                return parse_timestamp(fields.get(name))
            except TimestampError as exc:
                fail.append(str(exc))
                return None

        def _reject():
            res.rejected.append(RejectedRow(
                category=pf.category, locator=locator,
                native_id=native_ref or "(none)", reasons=list(fail)))

        rec = None
        if pf.category == "alerts":
            native_id = str(fields.get("native_id") or "").strip()
            if native_id and native_id in seen_native:
                fail.append(f"duplicate native_id {native_id!r} within file")
            if native_id and native_id in existing_natives:
                fail.append(
                    f"native_id {native_id!r} duplicates an already-ingested record")
            created_at = _ts("created_at")
            if "created_at" in [s.name for s in specs if s.required] and created_at is None \
                    and not any("created_at" in f for f in fail):
                if not any("missing required field 'created_at'" in f for f in fail):
                    fail.append("missing/empty required timestamp 'created_at'")
            mapped_sev, sev_ok = map_severity(fields.get("severity"))
            if not sev_ok and fields.get("severity") not in (None, ""):
                res.warnings.append(
                    f"{locator}: unrecognized severity {fields.get('severity')!r} -> 'unknown'")
            if not fail:
                rec = Alert(
                    entity_id=entity_id, assessment_id=assessment_id,
                    native_id=native_id, created_at=created_at,
                    native_severity=str(fields.get("severity") or ""),
                    mapped_severity=mapped_sev,
                    native_category=str(fields.get("category") or ""),
                    mapped_category=str(fields.get("category") or "unknown").strip().lower(),
                    acknowledged_at=_ts("acknowledged_at"),
                    closed_at=_ts("closed_at"),
                )
                case_refs, missing_refs = _resolve_list(
                    _listify(fields.get("case_ids")), case_native_to_id)
                for mr in missing_refs:
                    res.warnings.append(
                        f"{locator}: alert {native_id!r} references unknown case {mr!r}")
                rec.case_refs = case_refs
                asset_refs, missing_assets = _resolve_list(
                    _listify(fields.get("asset_ids")), asset_native_to_id)
                for mr in missing_assets:
                    res.warnings.append(
                        f"{locator}: alert {native_id!r} references unknown asset {mr!r}")
                rec.asset_refs = asset_refs
                if native_id in preassigned:
                    rec.id = preassigned[native_id]
                seen_native.add(native_id)

        elif pf.category == "cases":
            native_id = str(fields.get("native_id") or "").strip()
            if native_id and native_id in seen_native:
                fail.append(f"duplicate native_id {native_id!r} within file")
            if native_id and native_id in existing_natives:
                fail.append(
                    f"native_id {native_id!r} duplicates an already-ingested record")
            opened_at = _ts("opened_at")
            if opened_at is None and not any("opened_at" in f for f in fail):
                fail.append("missing/empty required timestamp 'opened_at'")
            status = str(fields.get("status") or "open").strip().lower()
            if status not in CASE_STATUSES:
                res.warnings.append(
                    f"{locator}: unrecognized case status {status!r} -> 'open'")
                status = "open"
            if not fail:
                rec = Case(
                    entity_id=entity_id, assessment_id=assessment_id,
                    native_id=native_id, opened_at=opened_at,
                    owner_pseudonym=str(fields.get("owner") or ""),
                    status=status, closed_at=_ts("closed_at"),
                    closure_reason=str(fields.get("closure_reason") or ""),
                )
                alert_refs, missing_refs = _resolve_list(
                    _listify(fields.get("alert_ids")), alert_native_to_id)
                for mr in missing_refs:
                    res.warnings.append(
                        f"{locator}: case {native_id!r} references unknown alert {mr!r}")
                rec.alert_refs = alert_refs
                if native_id in preassigned:
                    rec.id = preassigned[native_id]
                seen_native.add(native_id)

        elif pf.category == "investigation_steps":
            case_native = str(fields.get("case_id") or "").strip()
            case_internal = case_native_to_id.get(case_native)
            if case_native and case_internal is None:
                fail.append(f"references unknown case {case_native!r}")
            performed_at = _ts("performed_at")
            if performed_at is None and not any("performed_at" in f for f in fail):
                fail.append("missing/empty required timestamp 'performed_at'")
            seq_raw = fields.get("sequence")
            try:
                sequence = int(float(seq_raw)) if seq_raw not in (None, "") else row.row_number
            except (TypeError, ValueError):
                fail.append(f"invalid sequence {seq_raw!r}")
                sequence = 0
            if not fail:
                rec = InvestigationStep(
                    case_id=case_internal, action_type=str(fields.get("action_type") or "").strip(),
                    performed_at=performed_at, sequence=sequence,
                    analyst_pseudonym=str(fields.get("analyst") or ""),
                    note_text=str(fields.get("note") or ""),
                    evidence_refs=_listify(fields.get("evidence_ids")),
                )

        elif pf.category == "escalations":
            _resolve_warnings: list = []
            alert_ref, case_ref, resolved = _resolve_either(
                fields, alert_native_to_id, case_native_to_id, fail,
                warnings=_resolve_warnings)
            for w in _resolve_warnings:
                res.warnings.append(f"{locator}: {w}")
            occurred_at = _ts("occurred_at")
            if occurred_at is None and not any("occurred_at" in f for f in fail):
                fail.append("missing/empty required timestamp 'occurred_at'")
            if not fail:
                rec = Escalation(
                    entity_id=entity_id, assessment_id=assessment_id,
                    occurred_at=occurred_at, alert_id=alert_ref or None,
                    case_id=case_ref or None,
                    destination_role=str(fields.get("destination_role") or ""),
                    trigger=str(fields.get("trigger") or ""),
                    outcome=str(fields.get("outcome") or ""),
                )

        elif pf.category == "dispositions":
            _resolve_warnings = []
            alert_ref, case_ref, resolved = _resolve_either(
                fields, alert_native_to_id, case_native_to_id, fail,
                warnings=_resolve_warnings)
            for w in _resolve_warnings:
                res.warnings.append(f"{locator}: {w}")
            occurred_at = _ts("occurred_at")
            if occurred_at is None and not any("occurred_at" in f for f in fail):
                fail.append("missing/empty required timestamp 'occurred_at'")
            mapped_cat, cat_ok = map_disposition_category(fields.get("outcome"))
            if not cat_ok and fields.get("outcome") not in (None, ""):
                res.warnings.append(
                    f"{locator}: unrecognized disposition outcome {fields.get('outcome')!r}"
                    " -> 'unknown'")
            if not fail:
                rec = Disposition(
                    entity_id=entity_id, assessment_id=assessment_id,
                    occurred_at=occurred_at, alert_id=alert_ref or None,
                    case_id=case_ref or None, mapped_category=mapped_cat,
                    reason=str(fields.get("reason") or ""),
                    approver_role=str(fields.get("approver_role") or ""),
                )

        elif pf.category == "assets":
            native_id = str(fields.get("native_id") or "").strip()
            if native_id and native_id in seen_native:
                fail.append(f"duplicate native_id {native_id!r} within file")
            if native_id and native_id in existing_natives:
                fail.append(
                    f"native_id {native_id!r} duplicates an already-ingested record")
            crit, crit_ok = map_criticality(fields.get("criticality"))
            if not crit_ok and fields.get("criticality") not in (None, ""):
                res.warnings.append(
                    f"{locator}: unrecognized criticality {fields.get('criticality')!r}"
                    " -> 'unknown'")
            if not fail:
                rec = Asset(
                    entity_id=entity_id, native_id=native_id, criticality=crit,
                    environment=str(fields.get("environment") or ""),
                    control_applicability=_listify(fields.get("controls")),
                )
                if native_id in preassigned:
                    rec.id = preassigned[native_id]
                seen_native.add(native_id)

        # domain-level validation (chronology, cross-field invariants)
        if rec is not None and not fail:
            domain_errors = rec.validate()
            if domain_errors:
                fail.extend(domain_errors)

        if fail or rec is None:
            _reject()
            continue

        sr = SourceRecord(
            submission_id="",  # set by the service once the Submission id exists
            file_digest=pf.file_digest, format=pf.format,
            locator=row.locator, original_record_digest=row.original_digest,
        )
        if hasattr(rec, "source_record_ref"):
            rec.source_record_ref = sr.id
        res.records.append(rec)
        res.source_records.append(sr)
        if pf.category in ("alerts", "cases", "assets"):
            res.accepted_native.append(native_id)

    return res


def _resolve_list(native_ids: list, native_to_id: dict) -> tuple[list, list]:
    resolved, missing = [], []
    for n in native_ids:
        if n in native_to_id:
            resolved.append(native_to_id[n])
        else:
            missing.append(n)
    return resolved, missing


def _resolve_either(fields: dict, alert_map: dict, case_map: dict, fail: list,
                    warnings: Optional[list] = None) -> tuple:
    """Resolve escalation/disposition alert/case native refs; exactly the
    record's own invariant (at least one resolvable ref) gates acceptance.

    A record may carry both an alert_id and a case_id (e.g. an escalation
    whose case_id happens to reference a case that failed its own
    validation for an unrelated reason). Per this module's own documented
    contract ("warnings capture suspected-but-tolerated issues... including
    unresolvable *optional* references"), an unresolvable secondary
    reference must not sink an otherwise-valid record when the other
    reference *does* resolve — that silently drops real evidence (an
    escalation/disposition whose alert_id is perfectly valid) purely
    because of an unrelated rejection elsewhere. Only reject the record
    (append to ``fail``) when *neither* reference resolves; an unresolvable
    reference alongside a resolved one is downgraded to ``warnings`` and
    the unresolved half becomes ``None`` on the constructed record, not a
    rejection reason.
    """
    if warnings is None:
        warnings = []
    alert_native = str(fields.get("alert_id") or "").strip()
    case_native = str(fields.get("case_id") or "").strip()
    if not alert_native and not case_native:
        fail.append("must reference at least one of alert_id/case_id")
        return "", "", False
    alert_ref = alert_map.get(alert_native, "") if alert_native else ""
    case_ref = case_map.get(case_native, "") if case_native else ""
    resolved = bool(alert_ref or case_ref)
    if alert_native and not alert_ref:
        msg = f"references unknown alert {alert_native!r}"
        if resolved:
            warnings.append(msg + " (dropped; case reference still resolved)")
        else:
            fail.append(msg)
    if case_native and not case_ref:
        msg = f"references unknown case {case_native!r}"
        if resolved:
            warnings.append(msg + " (dropped; alert reference still resolved)")
        else:
            fail.append(msg)
    return alert_ref, case_ref, resolved

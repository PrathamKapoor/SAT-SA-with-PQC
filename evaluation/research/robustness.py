"""Controlled imperfect-evidence experiment over the hosted SAT-SA path.

Each catalog scenario fixture is submitted once unperturbed (the paired
control) and once per declared perturbation in five families:
missingness (omitted categories, seeded record omission), duplication
(exact, conflicting and near duplicates), malformation (bad timestamps,
chronology violations, a missing required column), staleness (records
shifted outside the assessment period) and conflict (individually valid
but mutually contradictory records). Every condition runs in its own
scratch SQLite tenant through the production ``SubmissionService``
validation and ``AnalysisExecutionWorker`` so peer baselines and records
never leak between conditions.

The perturbation specification, severity, expected validation outcome
and expected effect are fixed before any submission runs. Expected
outcomes come from the documented validator contract (hosted validation
is all-or-nothing: any rejected row invalidates the version). Staleness
conditions have no declared expectation because no assessment-period or
recency validation is implemented; their outcome is an observation.
Perturbed analyses are compared with their paired control. Catalog-label
metrics on perturbed runs are reported as derived, informative values
only, because those labels describe the unperturbed fixture.
"""

from __future__ import annotations

import copy
import csv
import io
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

EXPERIMENT_NAME = "satsa-evidence-perturbation-v1"
OPTIONAL_CATEGORIES = (
    "cases",
    "investigation_steps",
    "escalations",
    "dispositions",
    "assets",
)
DEFAULT_RATES = (0.10, 0.25, 0.50)
DEFAULT_SEEDS = 5
_CSE_FIELD = {
    "alerts": "alerts",
    "cases": "cases",
    "investigation_steps": "steps",
    "escalations": "escalations",
    "dispositions": "dispositions",
    "assets": "assets",
}
_OUT_OF_PERIOD_SHIFT_SECONDS = 40 * 86400
# Assessment period used for every fixture (satsa.analysis.synth constants).
PERIOD_START = 1735689600.0
PERIOD_END = 1738281600.0
_RISK_IDENTIFIERS = {"entity_id", "run_id", "assessment_id"}


class _WithheldFindingCounter(logging.Handler):
    """Count findings the worker drops because ``Finding.validate()`` failed.

    The worker only logs these; counting them keeps silently withheld
    output visible in the experiment record without changing the product.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.by_worker: dict[str, int] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == "invalid finding withheld":
            worker = str(getattr(record, "worker", "unknown"))
            self.by_worker[worker] = self.by_worker.get(worker, 0) + 1


@dataclass(frozen=True)
class Condition:
    """One declared perturbation and its pre-execution expectation."""

    name: str
    kind: str
    expected_validation: str | None
    parameters: dict[str, Any]
    family: str = "control"
    severity: str = "none"
    expected_effect: str = ""


def _rows(cse, category: str) -> list[dict]:
    return getattr(cse, _CSE_FIELD[category])


def _set_rows(cse, category: str, rows: list[dict]) -> None:
    setattr(cse, _CSE_FIELD[category], rows)


def _dangling_references(cse) -> dict[str, int]:
    """Count rows the documented contract rejects after omission.

    Investigation steps require their case; escalations/dispositions need
    at least one resolvable alert or case reference. Alerts are never
    omitted, so the alert half of a reference always resolves when set.
    """
    case_ids = {str(row["native_id"]) for row in cse.cases}
    alert_ids = {str(row["native_id"]) for row in cse.alerts}
    steps = sum(str(row["case_id"]) not in case_ids for row in cse.steps)
    linked = 0
    for row in [*cse.escalations, *cse.dispositions]:
        alert = str(row.get("alert_id") or "")
        case = str(row.get("case_id") or "")
        if not (alert in alert_ids or case in case_ids):
            linked += 1
    return {"investigation_steps": steps, "escalations_or_dispositions": linked}


def declared_conditions(
    cse, *, rates: tuple[float, ...], seeds: int, base_seed: int
) -> list[tuple[Condition, Any, dict[str, Any]]]:
    """Build every perturbed fixture plus its ground-truth record.

    Returns ``(condition, perturbed_cse, perturbation_ground_truth)`` in a
    fixed order. Nothing here reads SAT-SA output.
    """
    out: list[tuple[Condition, Any, dict[str, Any]]] = []
    out.append(
        (
            Condition(
                "control",
                "control",
                "valid",
                {},
                expected_effect="baseline for paired comparison",
            ),
            copy.deepcopy(cse),
            {"description": "unperturbed catalog fixture"},
        )
    )

    for category in OPTIONAL_CATEGORIES:
        if not _rows(cse, category):
            continue
        perturbed = copy.deepcopy(cse)
        _set_rows(perturbed, category, [])
        dangling = _dangling_references(perturbed)
        out.append(
            (
                Condition(
                    f"omit_category:{category}",
                    "omit_category",
                    "invalid" if any(dangling.values()) else "valid",
                    {"category": category},
                    family="missingness",
                    severity="whole category",
                    expected_effect=_omission_effect(dangling),
                ),
                perturbed,
                {
                    "omitted_category": category,
                    "omitted_records": len(_rows(cse, category)),
                    "dangling_references_after_omission": dangling,
                },
            )
        )

    pool = [
        (category, index)
        for category in OPTIONAL_CATEGORIES
        for index in range(len(_rows(cse, category)))
    ]
    for rate in rates:
        for replicate in range(seeds):
            seed = base_seed + replicate
            rng = random.Random(f"{EXPERIMENT_NAME}:{cse.name}:{rate}:{seed}")
            removed = sorted(rng.sample(pool, round(rate * len(pool))))
            perturbed = copy.deepcopy(cse)
            for category in OPTIONAL_CATEGORIES:
                drop = {index for cat, index in removed if cat == category}
                _set_rows(
                    perturbed,
                    category,
                    [
                        row
                        for index, row in enumerate(_rows(cse, category))
                        if index not in drop
                    ],
                )
            removed_rows = [
                {"category": cat, "row_index": index} for cat, index in removed
            ]
            dangling = _dangling_references(perturbed)
            out.append(
                (
                    Condition(
                        f"omit_records:{rate:.2f}:seed{seed}",
                        "omit_records",
                        "invalid" if any(dangling.values()) else "valid",
                        {"rate": rate, "seed": seed},
                        family="missingness",
                        severity=f"{rate:.0%} of non-alert records",
                        expected_effect=_omission_effect(dangling),
                    ),
                    perturbed,
                    {
                        "eligible_records": len(pool),
                        "removed": removed_rows,
                        "dangling_references_after_omission": dangling,
                    },
                )
            )
            # Same draw, but an omitted case also takes its investigation
            # steps: a referentially consistent partial export.
            cascaded = copy.deepcopy(perturbed)
            cases = {str(row["native_id"]) for row in cascaded.cases}
            dropped_steps = [
                index
                for index, row in enumerate(cascaded.steps)
                if str(row["case_id"]) not in cases
            ]
            cascaded.steps = [
                row for row in cascaded.steps if str(row["case_id"]) in cases
            ]
            dangling = _dangling_references(cascaded)
            out.append(
                (
                    Condition(
                        f"omit_records_cascade:{rate:.2f}:seed{seed}",
                        "omit_records_cascade",
                        "invalid" if any(dangling.values()) else "valid",
                        {"rate": rate, "seed": seed},
                        family="missingness",
                        severity=f"{rate:.0%} of non-alert records plus dependent steps",
                        expected_effect=_omission_effect(dangling),
                    ),
                    cascaded,
                    {
                        "eligible_records": len(pool),
                        "removed": removed_rows,
                        "cascaded_investigation_steps_removed": len(dropped_steps),
                        "dangling_references_after_omission": dangling,
                    },
                )
            )

    out.extend(_single_record_conditions(cse))
    return out


def _omission_effect(dangling: dict[str, int]) -> str:
    if any(dangling.values()):
        return (
            "dependent rows lose their required reference; the all-or-nothing "
            "hosted validator rejects the version"
        )
    return "version remains valid; analytical output may change versus control"


def _not_applicable(
    name: str, family: str, reason: str
) -> tuple[Condition, None, dict[str, Any]]:
    return (
        Condition(name, name.split(":")[0], None, {}, family=family),
        None,
        {"not_applicable": reason},
    )


def _single_record_conditions(cse) -> list[tuple[Condition, Any, dict[str, Any]]]:
    """Duplication, malformation, staleness and conflict conditions.

    Each alters (or adds) one record, one column or one case of an otherwise
    unchanged fixture. Conditions whose prerequisite records are absent are
    reported as not applicable rather than silently skipped.
    """
    out: list[tuple[Condition, Any, dict[str, Any]]] = []
    first = cse.alerts[0]

    def add(condition: Condition, mutate, truth: dict[str, Any]) -> None:
        perturbed = copy.deepcopy(cse)
        mutate(perturbed)
        out.append((condition, perturbed, truth))

    # Duplication. Alerts, cases and assets carry native ids; steps,
    # escalations and dispositions do not, so a non-identical repeat of
    # those is structurally indistinguishable from a new record.
    add(
        Condition(
            "duplicate_exact:alerts",
            "duplicate_exact",
            "invalid",
            {"category": "alerts"},
            family="duplication",
            severity="one record",
            expected_effect="byte-identical row rejected as duplicate record bytes",
        ),
        lambda c: c.alerts.append(dict(first)),
        {"duplicated": first["native_id"], "byte_identical": True},
    )
    other_severity = "low" if first["severity"] != "low" else "critical"
    add(
        Condition(
            "duplicate_conflicting:alerts",
            "duplicate_conflicting",
            "invalid",
            {"category": "alerts", "field": "severity"},
            family="duplication",
            severity="one record",
            expected_effect="second row with the same native_id rejected",
        ),
        lambda c: c.alerts.append({**first, "severity": other_severity}),
        {
            "duplicated": first["native_id"],
            "conflicting_field": "severity",
            "values": [first["severity"], other_severity],
        },
    )
    if cse.cases:
        case = cse.cases[0]
        add(
            Condition(
                "duplicate_exact:cases",
                "duplicate_exact",
                "invalid",
                {"category": "cases"},
                family="duplication",
                severity="one record",
                expected_effect="byte-identical row rejected as duplicate record bytes",
            ),
            lambda c: c.cases.append(copy.deepcopy(case)),
            {"duplicated": case["native_id"], "byte_identical": True},
        )
        add(
            Condition(
                "duplicate_conflicting:cases",
                "duplicate_conflicting",
                "invalid",
                {"category": "cases", "field": "owner"},
                family="duplication",
                severity="one record",
                expected_effect="second row with the same native_id rejected",
            ),
            lambda c: c.cases.append({**copy.deepcopy(case), "owner": "bob"}),
            {"duplicated": case["native_id"], "conflicting_field": "owner"},
        )
    else:
        out.append(_not_applicable("duplicate_exact:cases", "duplication", "no cases"))
    if cse.steps:
        step = cse.steps[0]
        add(
            Condition(
                "duplicate_exact:investigation_steps",
                "duplicate_exact",
                "invalid",
                {"category": "investigation_steps"},
                family="duplication",
                severity="one record",
                expected_effect="byte-identical row rejected as duplicate record bytes",
            ),
            lambda c: c.steps.append(dict(step)),
            {"duplicated_step_of_case": step["case_id"], "byte_identical": True},
        )
        add(
            Condition(
                "duplicate_near:investigation_steps",
                "duplicate_near",
                "valid",
                {"category": "investigation_steps", "changed_field": "sequence"},
                family="duplication",
                severity="one record",
                expected_effect=(
                    "steps carry no native id, so a re-sequenced repeat is "
                    "accepted; observe whether it inflates workflow evidence"
                ),
            ),
            lambda c: c.steps.append({**step, "sequence": int(step["sequence"]) + 100}),
            {"duplicated_step_of_case": step["case_id"], "sequence_offset": 100},
        )
    else:
        out.append(
            _not_applicable(
                "duplicate_exact:investigation_steps", "duplication", "no steps"
            )
        )
    if cse.dispositions:
        disposition = cse.dispositions[0]
        add(
            Condition(
                "duplicate_near:dispositions",
                "duplicate_near",
                "valid",
                {"category": "dispositions", "changed_field": "occurred_at"},
                family="duplication",
                severity="one record",
                expected_effect=(
                    "dispositions carry no native id, so a repeat one second "
                    "later is accepted; observe whether it inflates outcomes"
                ),
            ),
            lambda c: c.dispositions.append(
                {**disposition, "occurred_at": float(disposition["occurred_at"]) + 1}
            ),
            {"duplicated_disposition_of_alert": disposition["alert_id"]},
        )
    else:
        out.append(
            _not_applicable(
                "duplicate_near:dispositions", "duplication", "no dispositions"
            )
        )

    # Malformation.
    def malformed_timestamp(c) -> None:
        c.alerts[0]["created_at"] = "not-a-time"

    def chronology_violation(c) -> None:
        c.alerts[0]["closed_at"] = float(first["ack_at"]) - 10.0

    add(
        Condition(
            "malformed_timestamp",
            "malformed_timestamp",
            "invalid",
            {"category": "alerts", "field": "created_at"},
            family="malformation",
            severity="one record",
            expected_effect="unparseable timestamp rejects the row and the version",
        ),
        malformed_timestamp,
        {"alert": first["native_id"], "field": "created_at"},
    )
    add(
        Condition(
            "chronology_violation",
            "chronology_violation",
            "invalid",
            {"category": "alerts"},
            family="malformation",
            severity="one record",
            expected_effect="domain validation rejects closed_at before ack_at",
        ),
        chronology_violation,
        {"alert": first["native_id"], "violation": "closed_at < ack_at"},
    )
    out.append(
        (
            Condition(
                "missing_required_column",
                "missing_required_column",
                "invalid",
                {"category": "alerts", "column": "created_at"},
                family="malformation",
                severity="whole column",
                expected_effect="schema check rejects the alerts artifact",
            ),
            copy.deepcopy(cse),
            {"category": "alerts", "dropped_column": "created_at"},
        )
    )

    # Staleness. SAT-SA implements no assessment-period or recency
    # validation, so these carry no declared expectation and record
    # current behavior only.
    created = float(first["created_at"])
    for name, severity, shift in (
        (
            "stale:before_period_1d",
            "moderate",
            PERIOD_START - 86400.0 - created,
        ),
        ("stale:before_period_40d", "high", -float(_OUT_OF_PERIOD_SHIFT_SECONDS)),
        ("stale:after_period_1d", "moderate", PERIOD_END + 86400.0 - created),
    ):

        def shifted(c, shift=shift) -> None:
            for field in ("created_at", "ack_at", "closed_at"):
                c.alerts[0][field] = float(first[field]) + shift

        add(
            Condition(
                name,
                "stale",
                None,
                {"shift_seconds": shift},
                family="staleness",
                severity=severity,
                expected_effect=(
                    "no declared expectation: no assessment-period or recency "
                    "validation is implemented"
                ),
            ),
            shifted,
            {"alert": first["native_id"], "shift_seconds": shift},
        )

    # Conflicts between individually valid records.
    if cse.dispositions:
        disposition = cse.dispositions[0]
        opposite = (
            "false_positive"
            if disposition.get("outcome") != "false_positive"
            else "true_positive"
        )
        add(
            Condition(
                "conflict:contradictory_dispositions",
                "conflict",
                "valid",
                {"conflict": "two dispositions with opposite outcomes"},
                family="conflict",
                severity="one record",
                expected_effect=(
                    "no cross-record consistency rule exists; observe analytical "
                    "response"
                ),
            ),
            lambda c: c.dispositions.append(
                {
                    **disposition,
                    "outcome": opposite,
                    "occurred_at": float(disposition["occurred_at"]) + 60,
                }
            ),
            {
                "alert": disposition["alert_id"],
                "outcomes": [disposition.get("outcome"), opposite],
            },
        )
    else:
        out.append(
            _not_applicable(
                "conflict:contradictory_dispositions", "conflict", "no dispositions"
            )
        )

    closed_case = next(
        (row for row in cse.cases if row.get("status") == "closed"), None
    )
    linked_alert = (
        next(
            (
                row
                for row in cse.alerts
                if row.get("case_id") == closed_case["native_id"]
            ),
            None,
        )
        if closed_case is not None
        else None
    )
    if closed_case is not None and linked_alert is not None:
        alert_index = cse.alerts.index(linked_alert)

        def reopen_alert(c, index=alert_index) -> None:
            c.alerts[index]["closed_at"] = ""

        add(
            Condition(
                "conflict:closed_case_open_alert",
                "conflict",
                "valid",
                {"conflict": "case closed while a linked alert has no closure"},
                family="conflict",
                severity="one record",
                expected_effect=(
                    "no cross-record consistency rule exists; observe analytical "
                    "response"
                ),
            ),
            reopen_alert,
            {"case": closed_case["native_id"], "alert": linked_alert["native_id"]},
        )
    else:
        out.append(
            _not_applicable(
                "conflict:closed_case_open_alert",
                "conflict",
                "no closed case with a linked alert",
            )
        )

    escalated = next(
        (
            row
            for row in cse.escalations
            if any(step["case_id"] == row.get("case_id") for step in cse.steps)
        ),
        None,
    )
    if escalated is not None:
        target = escalated["case_id"]

        def drop_case_steps(c, target=target) -> None:
            c.steps = [row for row in c.steps if row["case_id"] != target]

        add(
            Condition(
                "conflict:escalation_without_investigation",
                "conflict",
                "valid",
                {"conflict": "escalated case has no investigation steps"},
                family="conflict",
                severity="one case",
                expected_effect=(
                    "record set stays referentially valid; observe whether "
                    "execution-gap or negative-space workers respond"
                ),
            ),
            drop_case_steps,
            {
                "case": target,
                "removed_steps": sum(row["case_id"] == target for row in cse.steps),
            },
        )
    else:
        out.append(
            _not_applicable(
                "conflict:escalation_without_investigation",
                "conflict",
                "no escalated case with investigation steps",
            )
        )

    if cse.cases:
        case = cse.cases[0]
        closure_time = float(case["opened_at"]) + 3600.0

        def status_conflict(c, closure_time=closure_time) -> None:
            c.cases[0]["status"] = "open"
            c.cases[0]["closed_at"] = closure_time

        add(
            Condition(
                "conflict:case_status_vs_closure_time",
                "conflict",
                "invalid",
                {"conflict": "case status open while closed_at is set"},
                family="conflict",
                severity="one record",
                expected_effect=(
                    "Case domain validation rejects closed_at with a non-closed status"
                ),
            ),
            status_conflict,
            {"case": case["native_id"], "status": "open", "closed_at": closure_time},
        )
    else:
        out.append(
            _not_applicable(
                "conflict:case_status_vs_closure_time", "conflict", "no cases"
            )
        )
    return out


def _category_csv(cse, category: str, condition: Condition) -> bytes | None:
    """Serialize one category with the existing synthetic CSV writer."""
    import tempfile

    from satsa.analysis.synth import _write_cse

    if not _rows(cse, category):
        return None
    with tempfile.TemporaryDirectory(prefix="satsa-robustness-csv-") as temporary:
        directory = Path(temporary)
        _write_cse(cse, directory)
        data = (directory / f"{category}.csv").read_bytes()
    column = condition.parameters.get("column")
    if condition.kind == "missing_required_column" and category == "alerts":
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        fields = [name for name in reader.fieldnames or [] if name != column]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(reader)
        data = buffer.getvalue().encode("utf-8")
    return data


def _families(findings: list[dict]) -> list[str]:
    return sorted(
        {
            str(row.get("rule_or_category") or "")
            for row in findings
            if row.get("state") == "signal"
        }
    )


def _traceability(findings: list[dict], evidence: list[dict]) -> dict[str, Any]:
    source_ids = {row["source_record_id"] for row in evidence}
    refs_total = refs_resolved = findings_resolved = 0
    for finding in findings:
        try:
            refs = json.loads(finding.get("evidence_refs_json") or "[]")
        except (TypeError, ValueError):
            refs = []
        refs = [
            ref for ref in refs if isinstance(ref, str) and ref.startswith("srcrec_")
        ]
        resolved = sum(ref in source_ids for ref in refs)
        refs_total += len(refs)
        refs_resolved += resolved
        if refs and resolved == len(refs):
            findings_resolved += 1
    return {
        "findings": len(findings),
        "findings_with_all_evidence_references_resolved": findings_resolved,
        "evidence_references": refs_total,
        "resolved_evidence_references": refs_resolved,
        "evidence_reference_coverage": (
            refs_resolved / refs_total if refs_total else None
        ),
    }


def _risk_summary(risk: dict | None) -> dict[str, Any] | None:
    if risk is None:
        return None
    profile = risk.get("profile") or {}
    return {
        key: value
        for key, value in sorted(profile.items())
        if key not in _RISK_IDENTIFIERS
        and (isinstance(value, (int, float, str, bool)) or value is None)
    }


def run_condition(scratch: Path, cse, condition: Condition) -> dict[str, Any]:
    """Submit and (if valid) analyze one fixture in an isolated tenant."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.service import AuditService
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )
    from satsa.analysis.synth import PERIOD_END, PERIOD_START
    from satsa.submissions import LocalArtifactStorage, SubmissionService
    from satsa.tenancy import TenantAdministration, TenantRepository

    root = Path(scratch)
    root.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(root / "research-robustness.sqlite3")
    engine.connect()
    MigrationRunner(engine).migrate()
    try:
        admin = TenantAdministration(engine)
        organization_id = admin.create_organization("Research robustness tenant")
        now = time.time()
        engine.execute(
            "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                "research-analyst",
                "human",
                "Research analyst",
                "research",
                "active",
                now,
                now,
            ),
        )
        analyst_id = admin.create_user("research-analyst", "analyst@example.test")
        admin.add_membership(organization_id, analyst_id, "satsa_analyst")
        tenant = TenantRepository(engine, organization_id, analyst_id)
        entity_id = tenant.create_entity(f"Research {cse.name}", sector=cse.sector)
        assessment_id = tenant.create_assessment(entity_id, PERIOD_START, PERIOD_END)
        audit = AuditService(EvidenceLedger(root / "audit.jsonl"), database=engine)
        submissions = SubmissionService(
            engine,
            organization_id,
            analyst_id,
            storage=LocalArtifactStorage(root / "artifacts"),
            audit=audit,
        )
        submission_id = submissions.create_submission(
            assessment_id, idempotency_key="research-robustness-submission"
        )
        version_id = submissions.create_version(
            submission_id, idempotency_key="research-robustness-version"
        )
        uploaded: list[str] = []
        started = perf_counter()
        for category in _CSE_FIELD:
            data = _category_csv(cse, category, condition)
            if data is None:
                continue
            submissions.upload(
                version_id,
                category=category,
                stream=io.BytesIO(data),
                filename=f"{category}.csv",
                content_type="text/csv",
                idempotency_key=f"research-robustness-{category}",
            )
            uploaded.append(category)
        submissions.complete_uploads(version_id)
        report = submissions.validate(version_id)
        validation_seconds = perf_counter() - started
        result: dict[str, Any] = {
            "uploaded_categories": uploaded,
            "validation_status": report["status"],
            "validation_totals": report.get("totals", {}),
            "validation_errors": [
                {
                    key: error.get(key)
                    for key in ("category", "locator", "message", "reasons")
                    if error.get(key) is not None
                }
                for error in report.get("errors", [])
            ],
            "validation_warning_count": len(report.get("warnings", [])),
            "validation_seconds": round(validation_seconds, 6),
        }
        if report["status"] != "valid":
            result["status"] = "rejected_by_validation"
            return result

        service = AnalysisExecutionService(
            engine, organization_id, analyst_id, audit=audit
        )
        run = service.create_run(version_id, idempotency_key="research-robustness-run")
        worker = AnalysisExecutionWorker(
            engine,
            worker_id="research-robustness-worker",
            audit=audit,
            trust_key_dir=str(root / "signing-keys"),
        )
        withheld = _WithheldFindingCounter()
        execution_log = logging.getLogger("qsmlops.satsa.analysis.execution")
        execution_log.addHandler(withheld)
        started = perf_counter()
        try:
            run_status = worker.run_once()
        finally:
            execution_log.removeHandler(withheld)
        result["analysis_seconds"] = round(perf_counter() - started, 6)
        result["run_status"] = run_status
        result["withheld_invalid_findings"] = dict(sorted(withheld.by_worker.items()))
        if run_status not in {"completed", "partial"}:
            result["status"] = "analysis_failed"
            result["failure_reason"] = f"worker returned {run_status!r}"
            return result
        findings = service.list_findings(run["run_id"], limit=500)
        evidence = service.list_evidence(run["run_id"], limit=500)
        recommendations = service.list_recommendations(run["run_id"])
        result.update(
            {
                "status": "completed",
                "emitted_families": _families(findings),
                "finding_count": len(findings),
                "recommendation_count": len(recommendations),
                "risk": _risk_summary(service.get_risk(run["run_id"])),
                "traceability": _traceability(findings, evidence),
            }
        )
        return result
    finally:
        engine.close()


def _paired_delta(
    control: dict[str, Any], row: dict[str, Any]
) -> dict[str, Any] | None:
    if control.get("status") != "completed" or row.get("status") != "completed":
        return None
    base, now = set(control["emitted_families"]), set(row["emitted_families"])
    risk_changes = {}
    for key in sorted(set(control.get("risk") or {}) | set(row.get("risk") or {})):
        before = (control.get("risk") or {}).get(key)
        after = (row.get("risk") or {}).get(key)
        if before != after:
            risk_changes[key] = {"control": before, "perturbed": after}
    return {
        "families_added": sorted(now - base),
        "families_removed": sorted(base - now),
        "family_set_changed": base != now,
        "finding_count_change": row["finding_count"] - control["finding_count"],
        "risk_fields_changed": risk_changes,
    }


def _describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 4),
        "min": min(values),
        "max": max(values),
    }


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = groups.setdefault(
            row[key],
            {
                "conditions": 0,
                "validation_status_counts": {},
                "matches_expected": 0,
                "mismatches_expected": 0,
                "no_declared_expectation": 0,
                "completed_analyses": 0,
                "family_set_changed_vs_control": 0,
                "withheld_invalid_findings": 0,
            },
        )
        entry["conditions"] += 1
        counts = entry["validation_status_counts"]
        counts[row["validation_status"]] = counts.get(row["validation_status"], 0) + 1
        if row["validation_matches_expected"] is None:
            entry["no_declared_expectation"] += 1
        elif row["validation_matches_expected"]:
            entry["matches_expected"] += 1
        else:
            entry["mismatches_expected"] += 1
        entry["completed_analyses"] += row.get("status") == "completed"
        delta = row.get("paired_delta_vs_control")
        entry["family_set_changed_vs_control"] += bool(
            delta and delta["family_set_changed"]
        )
        entry["withheld_invalid_findings"] += sum(
            (row.get("withheld_invalid_findings") or {}).values()
        )
    return groups


def _rate_summary(selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [
        row["paired_delta_vs_control"]
        for row in selected_rows
        if row.get("paired_delta_vs_control") is not None
    ]
    return {
        "replicates": len(selected_rows),
        "rejected_by_validation": sum(
            row["status"] == "rejected_by_validation" for row in selected_rows
        ),
        "completed_analyses": len(deltas),
        "family_set_changed": sum(delta["family_set_changed"] for delta in deltas),
        "families_removed_per_run": _describe(
            [len(delta["families_removed"]) for delta in deltas]
        ),
        "families_added_per_run": _describe(
            [len(delta["families_added"]) for delta in deltas]
        ),
        "interpretation": (
            "descriptive over seeded omission replicates of authored fixtures; "
            "not a confidence interval"
        ),
    }


def run_evidence_robustness_experiment(
    scratch_dir: Path,
    *,
    scenarios: tuple[str, ...] | None = None,
    rates: tuple[float, ...] = DEFAULT_RATES,
    seeds: int = DEFAULT_SEEDS,
    base_seed: int = 0,
) -> dict[str, Any]:
    """Run every declared condition for each selected catalog scenario."""
    from evaluation.controlled_benchmark.runner import scenario_family_metrics
    from satsa.analysis.compval import SCENARIO_MAP
    from satsa.analysis.validate import synthetic_ground_truth

    if seeds < 1:
        raise ValueError("seeds must be at least 1")
    if any(not 0 < rate < 1 for rate in rates):
        raise ValueError("omission rates must be between 0 and 1 (exclusive)")
    selected = tuple(scenarios) if scenarios else tuple(SCENARIO_MAP)
    unknown = [name for name in selected if name not in SCENARIO_MAP]
    if unknown:
        raise ValueError(f"unknown scenarios: {', '.join(unknown)}")
    labels = {case.case_id: case for case in synthetic_ground_truth()}

    root = Path(scratch_dir)
    per_scenario: list[dict[str, Any]] = []
    started = perf_counter()
    for scenario in selected:
        cse, _ = SCENARIO_MAP[scenario]()
        conditions = declared_conditions(
            cse, rates=tuple(rates), seeds=seeds, base_seed=base_seed
        )
        case = labels.get(scenario)
        rows: list[dict[str, Any]] = []
        for index, (condition, fixture, truth) in enumerate(conditions):
            declared = {
                "condition": condition.name,
                "kind": condition.kind,
                "family": condition.family,
                "severity": condition.severity,
                "parameters": condition.parameters,
                "perturbation_ground_truth": truth,
                "expected_validation": condition.expected_validation,
                "expected_effect": condition.expected_effect,
            }
            if fixture is None:
                rows.append(
                    {
                        **declared,
                        "status": "not_applicable",
                        "validation_status": None,
                        "validation_matches_expected": None,
                    }
                )
                continue
            outcome = run_condition(
                root / scenario / f"c{index:03d}", fixture, condition
            )
            matches = (
                None
                if condition.expected_validation is None
                else outcome["validation_status"] == condition.expected_validation
            )
            row = {**declared, "validation_matches_expected": matches, **outcome}
            if case is not None and outcome.get("status") == "completed":
                # Derived and informative only: catalog labels describe the
                # unperturbed fixture and may not hold after perturbation.
                row["catalog_family_metrics"] = {
                    **scenario_family_metrics(
                        list(case.expected_signals), outcome["emitted_families"]
                    ),
                    "labels_apply_to": "unperturbed fixture",
                }
            rows.append(row)
        control = rows[0]
        for row in rows[1:]:
            row["paired_delta_vs_control"] = _paired_delta(control, row)
        control_vs_catalog = (
            scenario_family_metrics(
                list(case.expected_signals), control["emitted_families"]
            )
            if case is not None and control.get("status") == "completed"
            else None
        )
        per_scenario.append(
            {
                "scenario": scenario,
                "declared_labels": {
                    "expected_signals": sorted(case.expected_signals) if case else None,
                    "source": "satsa.analysis.validate.synthetic_ground_truth",
                    "applies_to": "control only",
                },
                "control_vs_catalog": control_vs_catalog,
                "conditions": rows,
            }
        )

    all_rows = [row for item in per_scenario for row in item["conditions"]]
    executed_rows = [row for row in all_rows if row["status"] != "not_applicable"]
    by_kind = _group_summary(executed_rows, "kind")
    by_family = _group_summary(executed_rows, "family")

    by_rate: dict[str, dict[str, Any]] = {}
    for kind in ("omit_records", "omit_records_cascade"):
        for rate in rates:
            by_rate[f"{kind}:{rate:.2f}"] = _rate_summary(
                [
                    row
                    for row in all_rows
                    if row["kind"] == kind and row["parameters"]["rate"] == rate
                ]
            )

    conformance_rows = [
        row for row in executed_rows if row["validation_matches_expected"] is not None
    ]
    return {
        "status": "completed",
        "experiment": EXPERIMENT_NAME,
        "data_origin": "synthetic",
        "metrics": {
            "validation_contract_conformance": {
                "conditions_with_expectation": len(conformance_rows),
                "matches": sum(
                    row["validation_matches_expected"] for row in conformance_rows
                ),
                "by_kind": by_kind,
                "by_family": by_family,
                "not_applicable": sum(
                    row["status"] == "not_applicable" for row in all_rows
                ),
            },
            "record_omission_by_rate": by_rate,
            "per_scenario": per_scenario,
        },
        "performance": {
            "measurement_scope": (
                "local synchronous hosted-path execution with one isolated SQLite "
                "store per condition; not production API/worker/S3 topology"
            ),
            "total_elapsed_seconds": round(perf_counter() - started, 6),
        },
        "limitations": [
            "Fixtures are authored single-entity catalog scenarios; perturbation effects are descriptive mechanism observations, not operational robustness estimates.",
            "Expected validation outcomes come from the documented all-or-nothing hosted validator contract, so conformance tests the implementation against its own specification, not against independent real-world data-quality labels.",
            "Seeded omission replicates vary which records are removed from a fixed fixture; they are not independent datasets and support no inferential statistics.",
            "Staleness conditions have no declared expectation; their outcomes record current behavior only.",
        ],
    }

"""Controlled imperfect-evidence experiment over the hosted SAT-SA path.

Each catalog scenario fixture is submitted once unperturbed (the paired
control) and once per declared perturbation: omitted categories, seeded
record omission, exact and conflicting duplicates, malformed timestamps,
chronology violations, a missing required column and an out-of-period
record. Every condition runs in its own scratch SQLite tenant through the
production ``SubmissionService`` validation and ``AnalysisExecutionWorker``
so peer baselines and records never leak between conditions.

The perturbation specification and the expected validation outcome are
fixed before any submission runs. Expected outcomes come from the
documented validator contract (hosted validation is all-or-nothing: any
rejected row invalidates the version). ``out_of_period`` has no declared
expectation because no assessment-period validation is implemented; its
outcome is an observation. Perturbed analyses are compared with their
paired control, never scored against labels written for unperturbed data.
"""

from __future__ import annotations

import copy
import csv
import io
import json
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
_RISK_IDENTIFIERS = {"entity_id", "run_id", "assessment_id"}


@dataclass(frozen=True)
class Condition:
    """One declared perturbation and its pre-execution expectation."""

    name: str
    kind: str
    expected_validation: str | None
    parameters: dict[str, Any]


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
            Condition("control", "control", "valid", {}),
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

    first = cse.alerts[0]
    perturbed = copy.deepcopy(cse)
    perturbed.alerts.append(dict(first))
    out.append(
        (
            Condition("duplicate_exact", "duplicate_exact", "invalid", {}),
            perturbed,
            {"duplicated_alert": first["native_id"], "byte_identical": True},
        )
    )

    perturbed = copy.deepcopy(cse)
    conflicting = dict(first)
    conflicting["severity"] = "low" if first["severity"] != "low" else "critical"
    perturbed.alerts.append(conflicting)
    out.append(
        (
            Condition("duplicate_conflicting", "duplicate_conflicting", "invalid", {}),
            perturbed,
            {
                "duplicated_alert": first["native_id"],
                "conflicting_field": "severity",
                "values": [first["severity"], conflicting["severity"]],
            },
        )
    )

    perturbed = copy.deepcopy(cse)
    perturbed.alerts[0]["created_at"] = "not-a-time"
    out.append(
        (
            Condition("malformed_timestamp", "malformed_timestamp", "invalid", {}),
            perturbed,
            {"alert": first["native_id"], "field": "created_at"},
        )
    )

    perturbed = copy.deepcopy(cse)
    perturbed.alerts[0]["closed_at"] = float(first["ack_at"]) - 10.0
    out.append(
        (
            Condition("chronology_violation", "chronology_violation", "invalid", {}),
            perturbed,
            {"alert": first["native_id"], "violation": "closed_at < ack_at"},
        )
    )

    out.append(
        (
            Condition(
                "missing_required_column",
                "missing_required_column",
                "invalid",
                {"category": "alerts", "column": "created_at"},
            ),
            copy.deepcopy(cse),
            {"category": "alerts", "dropped_column": "created_at"},
        )
    )

    perturbed = copy.deepcopy(cse)
    for field in ("created_at", "ack_at", "closed_at"):
        perturbed.alerts[0][field] = float(first[field]) - _OUT_OF_PERIOD_SHIFT_SECONDS
    out.append(
        (
            Condition("out_of_period", "out_of_period", None, {}),
            perturbed,
            {
                "alert": first["native_id"],
                "shift_seconds": -_OUT_OF_PERIOD_SHIFT_SECONDS,
                "note": "observational: no assessment-period validation is implemented",
            },
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
        started = perf_counter()
        run_status = worker.run_once()
        result["analysis_seconds"] = round(perf_counter() - started, 6)
        result["run_status"] = run_status
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
        rows: list[dict[str, Any]] = []
        for index, (condition, fixture, truth) in enumerate(conditions):
            outcome = run_condition(
                root / scenario / f"c{index:03d}", fixture, condition
            )
            matches = (
                None
                if condition.expected_validation is None
                else outcome["validation_status"] == condition.expected_validation
            )
            rows.append(
                {
                    "condition": condition.name,
                    "kind": condition.kind,
                    "parameters": condition.parameters,
                    "perturbation_ground_truth": truth,
                    "expected_validation": condition.expected_validation,
                    "validation_matches_expected": matches,
                    **outcome,
                }
            )
        control = rows[0]
        for row in rows[1:]:
            row["paired_delta_vs_control"] = _paired_delta(control, row)
        case = labels.get(scenario)
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
    by_kind: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        entry = by_kind.setdefault(
            row["kind"],
            {
                "conditions": 0,
                "validation_status_counts": {},
                "matches_expected": 0,
                "mismatches_expected": 0,
                "no_declared_expectation": 0,
                "completed_analyses": 0,
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
        row for row in all_rows if row["validation_matches_expected"] is not None
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
            "out_of_period has no declared expectation; its outcome records current behavior only.",
        ],
    }

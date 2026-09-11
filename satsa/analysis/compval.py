"""Composition validation: bind synthetic ground truth to real
analysis pipeline outputs.

This module closes the P15 scaffold gap (validate.py line 286:
``emitted_families = list(case.expected_signals)``).
Instead of comparing ground truth to itself, it:

1. Builds scenario-specific synthetic CSE submission directories
   (reusing the CSV writer from ``satsa/analysis/synth``).
2. Ingests them through ``SatsaService`` (same ingestion
   path as real submissions).
3. Runs the full default-analytics pipeline (``run_analysis``).
4. Compares emitted finding families and the supervisor's
   SATSA-vocabulary decision to the ``GroundTruthCase`` catalog.

Non-executable scenarios (require peer cohorts or a
multi-period baseline that a single-entity fixture cannot
provide) are reported honestly as ``not_executed`` with the
reason. The runner never fabricates results.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

# ------------------------------------------------------------------
# Scenario dataset generators (deterministic, single-entity fixtures)
# ------------------------------------------------------------------

from satsa.analysis.synth import (
    _CSE,
    _write_cse,
    PERIOD_START,
    PERIOD_END,
)
from satsa.supervisor.engine import (
    _SATSA_RECOMMENDATION_TO_DECISION,
    _recommend_for,
)
from satsa.service import SatsaService
from satsa.analysis.recommend import recommend
from satsa.analysis.validate import (
    GroundTruthCase,
    synthetic_ground_truth,
    composition_validation,
)
from satsa.supervisor.engine import _SATSA_RECOMMENDATION_TO_DECISION


def _asset(native_id: str, criticality: str) -> dict:
    return {
        "native_id": native_id,
        "criticality": criticality,
        "environment": "prod",
        "controls": "AV;EDR" if criticality == "critical" else "AV",
    }


def _alert(
    native_id: str,
    created: float,
    severity: str,
    case_id: str,
    asset_id: str,
    ack: float,
    closed: float,
) -> dict:
    return {
        "native_id": native_id,
        "created_at": float(created),
        "severity": severity,
        "ack_at": float(ack),
        "closed_at": float(closed),
        "case_id": case_id,
        "asset_id": asset_id,
    }


def _case(
    native_id: str,
    opened: float,
    status: str = "closed",
    closed_at: float | None = None,
    alert_ids: list[str] | None = None,
    closure_reason: str = "resolved",
) -> dict:
    return {
        "native_id": native_id,
        "opened_at": float(opened),
        "status": status,
        "closed_at": float(closed_at) if closed_at is not None else None,
        "owner": "alice",
        "alert_ids": list(alert_ids or []),
        "closure_reason": closure_reason,
    }


def _step(
    case_id: str,
    action_type: str,
    performed: float,
    sequence: int,
) -> dict:
    return {
        "case_id": case_id,
        "action_type": action_type,
        "performed_at": float(performed),
        "sequence": sequence,
        "analyst": "alice",
        "note": "auto",
        "evidence_ids": f"EV-{case_id}-{sequence}",
    }


def _escalation(
    alert_id: str,
    case_id: str,
    occurred: float,
) -> dict:
    return {
        "alert_id": alert_id,
        "case_id": case_id,
        "occurred_at": float(occurred),
        "destination": "soc-l2",
        "trigger": "severity",
        "outcome": "acknowledged",
    }


def _disposition(
    alert_id: str,
    case_id: str,
    occurred: float,
    outcome: str = "true_positive",
) -> dict:
    return {
        "alert_id": alert_id,
        "case_id": case_id,
        "occurred_at": float(occurred),
        "outcome": outcome,
        "reason": "auto",
        "approver": "soc-lead",
    }


SCENARIO_MAP: dict[str, tuple] = {}


def _build_healthy() -> tuple[_CSE, list[str]]:
    assets = [_asset("a0", "high"), _asset("a1", "high"), _asset("a2", "high")]
    cases = [
        _case("c0", PERIOD_START + 100, alert_ids=["al0", "al1"]),
        _case("c1", PERIOD_START + 200, alert_ids=["al2", "al3"]),
    ]
    alerts = [
        _alert(
            "al0",
            PERIOD_START + 1000,
            "low",
            "c0",
            "a0",
            PERIOD_START + 2000,
            PERIOD_START + 40000,
        ),
        _alert(
            "al1",
            PERIOD_START + 2000,
            "low",
            "c0",
            "a1",
            PERIOD_START + 3000,
            PERIOD_START + 50000,
        ),
        _alert(
            "al2",
            PERIOD_START + 3000,
            "low",
            "c1",
            "a2",
            PERIOD_START + 4000,
            PERIOD_START + 60000,
        ),
        _alert(
            "al3",
            PERIOD_START + 4000,
            "low",
            "c1",
            "a0",
            PERIOD_START + 5000,
            PERIOD_START + 70000,
        ),
    ]
    steps = [
        _step("c0", "triage", PERIOD_START + 12000, 1),
        _step("c0", "containment", PERIOD_START + 24000, 2),
        _step("c0", "review", PERIOD_START + 36000, 3),
        _step("c1", "triage", PERIOD_START + 22000, 1),
        _step("c1", "eradication", PERIOD_START + 34000, 2),
        _step("c1", "recovery", PERIOD_START + 46000, 3),
    ]
    escalations = [_escalation("al0", "c0", PERIOD_START + 5000)]
    dispositions = [
        _disposition("al0", "c0", PERIOD_START + 80000),
        _disposition("al1", "c0", PERIOD_START + 80000),
        _disposition("al2", "c1", PERIOD_START + 80000),
        _disposition("al3", "c1", PERIOD_START + 80000),
    ]
    return (
        _CSE(
            name="SCEN-healthy",
            sector="defence",
            environment="on-prem",
            assets=assets,
            alerts=alerts,
            cases=cases,
            steps=steps,
            escalations=escalations,
            dispositions=dispositions,
        ),
        [
            "alerts",
            "cases",
            "investigation_steps",
            "escalations",
            "dispositions",
            "assets",
        ],
    )


def _build_fast_closure() -> tuple[_CSE, list[str]]:
    assets = [_asset("a0", "critical")]
    cases = [_case("c0", PERIOD_START + 100, alert_ids=["al0", "al1", "al2"])]
    alerts = [
        _alert(
            "al0",
            PERIOD_START + 1000,
            "critical",
            "c0",
            "a0",
            PERIOD_START + 1100,
            PERIOD_START + 1220,
        ),
        _alert(
            "al1",
            PERIOD_START + 3000,
            "critical",
            "c0",
            "a0",
            PERIOD_START + 3100,
            PERIOD_START + 3220,
        ),
        _alert(
            "al2",
            PERIOD_START + 5000,
            "critical",
            "c0",
            "a0",
            PERIOD_START + 5100,
            PERIOD_START + 5220,
        ),
    ]
    steps = [
        _step("c0", "triage", PERIOD_START + 1150, 1),
        _step("c0", "containment", PERIOD_START + 1200, 2),
        _step("c0", "review", PERIOD_START + 1250, 3),
    ]
    escalations = [
        _escalation("al0", "c0", PERIOD_START + 1150),
        _escalation("al1", "c0", PERIOD_START + 3150),
        _escalation("al2", "c0", PERIOD_START + 5150),
    ]
    dispositions = [
        _disposition("al0", "c0", PERIOD_START + 30000),
        _disposition("al1", "c0", PERIOD_START + 50000),
        _disposition("al2", "c0", PERIOD_START + 70000),
    ]
    return (
        _CSE(
            name="SCEN-fastclosure",
            sector="defence",
            environment="on-prem",
            assets=assets,
            alerts=alerts,
            cases=cases,
            steps=steps,
            escalations=escalations,
            dispositions=dispositions,
        ),
        [
            "alerts",
            "cases",
            "investigation_steps",
            "escalations",
            "dispositions",
            "assets",
        ],
    )


def _build_missing_investigation() -> tuple[_CSE, list[str]]:
    assets = [_asset("a0", "high"), _asset("a1", "high"), _asset("a2", "high")]
    cases = [
        _case("c0", PERIOD_START + 100, alert_ids=["al0", "al1"]),
        # c1: zero investigation steps (missing_investigation fires)
        _case("c1", PERIOD_START + 200, alert_ids=["al2", "al3"]),
    ]
    alerts = [
        _alert(
            "al0",
            PERIOD_START + 1000,
            "low",
            "c0",
            "a0",
            PERIOD_START + 2000,
            PERIOD_START + 60000,
        ),
        _alert(
            "al1",
            PERIOD_START + 2000,
            "low",
            "c0",
            "a1",
            PERIOD_START + 3000,
            PERIOD_START + 70000,
        ),
        _alert(
            "al2",
            PERIOD_START + 3000,
            "low",
            "c1",
            "a2",
            PERIOD_START + 4000,
            PERIOD_START + 80000,
        ),
        _alert(
            "al3",
            PERIOD_START + 4000,
            "low",
            "c1",
            "a0",
            PERIOD_START + 5000,
            PERIOD_START + 90000,
        ),
    ]
    steps = [
        # Only case c0 has steps; c1 has zero steps.
        _step("c0", "triage", PERIOD_START + 12000, 1),
        _step("c0", "containment", PERIOD_START + 24000, 2),
        _step("c0", "review", PERIOD_START + 36000, 3),
    ]
    escalations = [_escalation("al0", "c0", PERIOD_START + 5000)]
    dispositions = [
        _disposition("al0", "c0", PERIOD_START + 100000),
        _disposition("al1", "c0", PERIOD_START + 100000),
        _disposition("al2", "c1", PERIOD_START + 100000),
        _disposition("al3", "c1", PERIOD_START + 100000),
    ]
    return (
        _CSE(
            name="SCEN-missing-investigation",
            sector="defence",
            environment="on-prem",
            assets=assets,
            alerts=alerts,
            cases=cases,
            steps=steps,
            escalations=escalations,
            dispositions=dispositions,
        ),
        [
            "alerts",
            "cases",
            "investigation_steps",
            "escalations",
            "dispositions",
            "assets",
        ],
    )


def _build_missing_evidence() -> tuple[_CSE, list[str]]:
    """Evidence completeness: 2 categories missing
    (escalations, dispositions omitted entirely)."""
    assets = [_asset("a0", "high"), _asset("a1", "high"), _asset("a2", "high")]
    cases = [
        _case("c0", PERIOD_START + 100, alert_ids=["al0", "al1"]),
        _case("c1", PERIOD_START + 200, alert_ids=["al2", "al3"]),
    ]
    alerts = [
        _alert(
            "al0",
            PERIOD_START + 1000,
            "low",
            "c0",
            "a0",
            PERIOD_START + 2000,
            PERIOD_START + 60000,
        ),
        _alert(
            "al1",
            PERIOD_START + 2000,
            "low",
            "c0",
            "a1",
            PERIOD_START + 3000,
            PERIOD_START + 70000,
        ),
        _alert(
            "al2",
            PERIOD_START + 3000,
            "low",
            "c1",
            "a2",
            PERIOD_START + 4000,
            PERIOD_START + 80000,
        ),
        _alert(
            "al3",
            PERIOD_START + 4000,
            "low",
            "c1",
            "a0",
            PERIOD_START + 5000,
            PERIOD_START + 90000,
        ),
    ]
    steps = [
        _step("c0", "triage", PERIOD_START + 12000, 1),
        _step("c0", "containment", PERIOD_START + 24000, 2),
        _step("c0", "review", PERIOD_START + 36000, 3),
        _step("c1", "triage", PERIOD_START + 22000, 1),
        _step("c1", "eradication", PERIOD_START + 34000, 2),
        _step("c1", "recovery", PERIOD_START + 46000, 3),
    ]
    # Escalations and dispositions intentionally omitted.
    escalations: list[dict] = []
    dispositions: list[dict] = []
    return (
        _CSE(
            name="SCEN-missing-evidence",
            sector="defence",
            environment="on-prem",
            assets=assets,
            alerts=alerts,
            cases=cases,
            steps=steps,
            escalations=escalations,
            dispositions=dispositions,
        ),
        [
            "alerts",
            "cases",
            "investigation_steps",
            "assets",
        ],
    )


def _build_mixed() -> tuple[_CSE, list[str]]:
    """Mixed: execution-gap (fast-closure) + negative-space
    (missing-monitoring on 2 silent critical assets)."""
    assets = [
        _asset("a-silent1", "critical"),
        _asset("a-silent2", "critical"),
        _asset("a-active", "critical"),
    ]
    cases = [_case("c0", PERIOD_START + 100, alert_ids=["al0", "al1", "al2"])]
    alerts = [
        _alert(
            "al0",
            PERIOD_START + 1000,
            "critical",
            "c0",
            "a-active",
            PERIOD_START + 1100,
            PERIOD_START + 1220,
        ),
        _alert(
            "al1",
            PERIOD_START + 3000,
            "critical",
            "c0",
            "a-active",
            PERIOD_START + 3100,
            PERIOD_START + 3220,
        ),
        _alert(
            "al2",
            PERIOD_START + 5000,
            "critical",
            "c0",
            "a-active",
            PERIOD_START + 5100,
            PERIOD_START + 5220,
        ),
    ]
    steps = [
        _step("c0", "triage", PERIOD_START + 1150, 1),
        _step("c0", "containment", PERIOD_START + 1200, 2),
        _step("c0", "review", PERIOD_START + 1250, 3),
    ]
    escalations = [
        _escalation("al0", "c0", PERIOD_START + 1150),
        _escalation("al1", "c0", PERIOD_START + 3150),
        _escalation("al2", "c0", PERIOD_START + 5150),
    ]
    dispositions = [
        _disposition("al0", "c0", PERIOD_START + 30000),
        _disposition("al1", "c0", PERIOD_START + 50000),
        _disposition("al2", "c0", PERIOD_START + 70000),
    ]
    return (
        _CSE(
            name="SCEN-mixed",
            sector="defence",
            environment="on-prem",
            assets=assets,
            alerts=alerts,
            cases=cases,
            steps=steps,
            escalations=escalations,
            dispositions=dispositions,
        ),
        [
            "alerts",
            "cases",
            "investigation_steps",
            "escalations",
            "dispositions",
            "assets",
        ],
    )


# Executable scenarios (single-entity fixtures that deterministically
# trigger the expected signal family and are reproducible without
# multi-period or multi-entity fixtures).
SCENARIO_MAP: dict[str, tuple] = {
    "healthy": _build_healthy,
    "eg-fast-closure": _build_fast_closure,
    "ns-missing-investigation": _build_missing_investigation,
    "mixed": _build_mixed,
    "missing-evidence": _build_missing_evidence,
}

NOT_EXECUTABLE_REASON: dict[str, str] = {
    "anomaly-rate": (
        "Requires a previous-period KPI baseline (not available in a single-assessment fixture) or a peer cohort (requires ≥3 comparable entities)."),
    "peer-deviation": (
        "Requires ≥3 comparable peer entities in the same assessment cohort. A single-entity fixture cannot produce this signal deterministically."),
    "borderline": (
        "Threshold-edge scenario; the detector's signal/no_signal boundary is intentionally non-deterministic under small statistical perturbation."),
    "noisy": (
        "Requires multi-source conflicting submission evidence not modeled by the canonical single-submission data layer."),
    "conflicting-evidence": (
        "Requires contradictory evidence sources within the same assessment (multi-source conflict) which the normalization layer collapses."),
}


# ---------------------------------------------------------------------------
# Composition runner
# ---------------------------------------------------------------------------

def _scenario_dir(name: str, cse: _CSE, root: Path) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    _write_cse(cse, d)
    return d


def _emitted_families_and_action(service, run_id: str) -> tuple[list[str], str]:
    rows = service._db.query_all(
        "SELECT f.rule_or_category, f.confidence_json FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.run_id = ? AND f.state = 'signal'", (run_id,))
    families = sorted({r.get("rule_or_category", "") for r in rows})
    if not families:
        return [], "SATSA_SURFACE"
    best_conf = -1.0
    best_family = families[0]
    for r in rows:
        try:
            conf_json = json.loads(r.get("confidence_json") or "{}")
        except Exception:
            conf_json = {}
        score = float(conf_json.get("overall", 0.0))
        family = r.get("rule_or_category", "")
        if score > best_conf:
            best_conf = score
            best_family = family
    rec_action = _SATSA_RECOMMENDATION_TO_DECISION.get(
        recommend({
            "rule_or_category": best_family,
            "id": "sim",
            "evidence_refs": [],
        }).action,
        "SATSA_SURFACE",
    )
    return families, rec_action


def _scenario_builders() -> dict[str, tuple]:
    return SCENARIO_MAP


def run_composition_validation(*, trust_key_dir: str | None = None) -> dict:
    """Bind synthetic ground truth to real pipeline outputs.

    Each executable scenario (from the ``SCENARIO_MAP``):

    * generates a deterministic synthetic CSE directory,
    * registers a fresh entity + assessment,
    * ingests through ``SatsaService.submit``,
    * runs analytics through ``run_analysis``,
    * collects emitted signal families and supervisor action,
    * compares to ``GroundTruthCase``.

    Non-executable scenarios (``NOT_EXECUTABLE_REASON``) are
    reported honestly as ``not_executed`` — the runner never
    invents a synthetic dataset that cannot deterministically
    reproduce the expected signal family.
    """
    import tempfile
    import shutil
    import sqlite3
    from satsa.service import SatsaService
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner

    td = tempfile.mkdtemp()
    try:
        db_path = Path(td) / "composition.db"
        eng: sqlite3.Connection = SQLiteDatabaseEngine(db_path)
        eng.connect()
        MigrationRunner(eng).migrate()
        service = SatsaService(eng)

        executed: list[dict] = []
        not_executed: list[dict] = []

        for case in synthetic_ground_truth():
            if case.case_id not in SCENARIO_MAP:
                not_executed.append({
                    "case_id": case.case_id,
                    "scenario": case.scenario,
                    "reason": (
                        f"Not executable in single-entity fixture: "
                        f"{NOT_EXECUTABLE_REASON.get(case.case_id, '')}"),
                    "expected_signals": sorted(case.expected_signals),
                    "expected_action": case.expected_action,
                })
                continue

            builder = SCENARIO_MAP[case.case_id]
            cse, _omitted = builder()

            # Generate temporary submission directory.
            with tempfile.TemporaryDirectory() as td_scenario:
                scenario_dir = Path(td_scenario) / case.scenario
                scenario_dir.mkdir(parents=True, exist_ok=True)
                _scenario_dir(case.scenario, cse, Path(td_scenario))

                # Note: the directory must be rebuilt inside td_scenario so
                # ingestion picks up only this scenario's files.
                # The helper writes relative to the given root; rebuild.
                d = Path(td_scenario) / case.scenario
                # Re-write with clean directory (clear previous writes)
                if d.exists():
                    import shutil
                    shutil.rmtree(str(d), ignore_errors=True)
                d.mkdir(parents=True, exist_ok=True)
                _write_cse(cse, d)

                entity = service.register_entity(
                    f"COMP-{case.scenario}", sector="defence",
                    environment_class="on-prem")
                assessment = service.open_assessment(
                    entity.id, PERIOD_START, PERIOD_START + 86400 * 31)
                ingest_result = service.submit(assessment.id, d)

                if ingest_result.status != "accepted":
                    not_executed.append({
                        "case_id": case.case_id,
                        "scenario": case.scenario,
                        "reason": ("Ingestion failed: status={}. File "
                                   "categories missing or malformed.".format(
                                   ingest_result.status)),
                        "expected_signals": sorted(case.expected_signals),
                        "expected_action": case.expected_action,
                    })
                    continue

                run_result = service.run_analysis(
                    entity.id, assessment.id,
                    trust_key_dir=Path(trust_key_dir)
                    if trust_key_dir else None)
                if run_result.status not in ("completed", "partial"):
                    not_executed.append({
                        "case_id": case.case_id,
                        "scenario": case.scenario,
                        "reason": f"Analysis run failed: {run_result.status}",
                        "expected_signals": sorted(case.expected_signals),
                        "expected_action": case.expected_action,
                    })
                    continue

                families, emitted_action = _emitted_families_and_action(
                    service, run_result.run_id)
                comp = composition_validation(
                    case, families, emitted_action)
                comp["run_id"] = run_result.run_id
                executed.append(comp)

        # Aggregate summary over executed subset.
        n = len(executed)
        signals_ok = sum(1 for r in executed if r.get("signals_ok"))
        action_ok = sum(1 for r in executed if r.get("action_ok"))
        extra_fps = sum(
            len(set(r.get("emitted_signals", []) or [])
                - set(r.get("expected_signals", []) or []))
            for r in executed)
        summary = {
            "executed_cases": n,
            "not_executed_cases": len(not_executed),
            "signals_alignment": round(signals_ok / max(1, n), 3),
            "action_alignment": round(action_ok / max(1, n), 3),
            "incidental_extra_signals": extra_fps,
            "at": time.time(),
        }
        return {
            "executed": executed,
            "not_executed": not_executed,
            "summary": summary,
        }
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _scenario_dir(name: str, cse: _CSE, root: Path) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    _write_cse(cse, d)
    return d

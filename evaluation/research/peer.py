"""Controlled peer-cohort sensitivity experiment using real SAT-SA runs."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any


def _run_case(
    service,
    root: Path,
    *,
    cohort_id: str,
    peer_closures: list[int],
    subject_closure: int,
) -> dict[str, Any]:
    from satsa.analysis.repository import FindingStore
    from satsa.analysis.synth import PERIOD_END, PERIOD_START
    from satsa.analysis.workers.peer_benchmark import compute_peer_baseline

    entity_ids: list[str] = []
    for index, closure in enumerate(peer_closures):
        entity = service.register_entity(
            f"Research peer {cohort_id}-{index}",
            sector=f"research-{cohort_id}",
            environment_class="controlled-synthetic",
        )
        assessment = service.open_assessment(entity.id, PERIOD_START, PERIOD_END)
        _submit_single_alert(
            service, root, cohort_id, f"peer-{index}", entity, assessment, closure
        )
        service.run_analysis(entity.id, assessment.id)
        entity_ids.append(entity.id)

    subject = service.register_entity(
        f"Research subject {cohort_id}",
        sector=f"research-{cohort_id}",
        environment_class="controlled-synthetic",
    )
    assessment = service.open_assessment(subject.id, PERIOD_START, PERIOD_END)
    _submit_single_alert(
        service, root, cohort_id, "subject", subject, assessment, subject_closure
    )
    run = service.run_analysis(subject.id, assessment.id)
    findings = FindingStore(service._db).list_for_run(run.run_id)
    peer_findings = [
        row
        for row in findings
        if str(row.get("rule_or_category", "")).startswith("peer_benchmark.")
    ]
    baseline = compute_peer_baseline(service._db, subject.id, min_peers=3)
    return {
        "cohort_id": cohort_id,
        "peer_count": baseline.peer_count,
        "subject_closure_seconds": subject_closure,
        "peer_closure_seconds": peer_closures,
        "peer_median_seconds": baseline.metrics.get(
            "critical_closure_median_seconds", {}
        ).get("median"),
        "peer_mad_seconds": baseline.metrics.get(
            "critical_closure_median_seconds", {}
        ).get("mad"),
        "finding_emitted": bool(peer_findings),
        "findings": [
            {
                "family": row["rule_or_category"],
                "statistic": row.get("statistic"),
                "threshold": row.get("threshold"),
                "effect": row.get("effect"),
            }
            for row in peer_findings
        ],
        "analysis_run_id": run.run_id,
    }


def _submit_single_alert(
    service, root: Path, cohort_id: str, suffix: str, entity, assessment, closure: int
) -> None:
    from satsa.analysis.synth import _CSE, PERIOD_START, _write_cse

    alert = {
        "native_id": f"{cohort_id}-{suffix}-alert",
        "created_at": PERIOD_START,
        "severity": "critical",
        "ack_at": PERIOD_START + 10,
        "closed_at": PERIOD_START + 10 + closure,
        "case_id": "",
        "asset_id": "",
    }
    cse = _CSE(
        name=f"{cohort_id}-{suffix}",
        sector="defence",
        environment="prod",
        assets=[],
        alerts=[alert],
        cases=[],
        steps=[],
        escalations=[],
        dispositions=[],
    )
    with tempfile.TemporaryDirectory(prefix="peer-eval-", dir=Path(root)) as temporary:
        source = Path(temporary) / "submission"
        _write_cse(cse, source)
        accepted = service.submit(assessment.id, source)
        if accepted.status != "accepted":
            raise RuntimeError(
                f"peer research input rejected: {cohort_id}/{suffix} ({accepted.status})"
            )


def run_peer_sensitivity_experiment(scratch_dir: Path) -> dict[str, Any]:
    """Measure peer minimum-size and deviation sensitivity in scratch SQLite.

    All entities are synthetic and share only an explicit research cohort in
    the isolated local database; production tenants are never queried.
    """
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService

    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(root / "peer-research.sqlite3")
    engine.connect()
    MigrationRunner(engine).migrate()
    service = SatsaService(engine)
    started = time.perf_counter()
    try:
        peer_size_results = [
            _run_case(
                service,
                root,
                cohort_id=f"size-{count}",
                peer_closures=[300, 600, 900, 1200][:count],
                subject_closure=30,
            )
            for count in (2, 3, 4)
        ]
        magnitude_results = [
            _run_case(
                service,
                root,
                cohort_id=f"magnitude-{closure}",
                peer_closures=[300, 600, 900, 1200],
                subject_closure=closure,
            )
            for closure in (30, 400, 750)
        ]
        return {
            "status": "completed",
            "experiment": "peer-cohort-sensitivity-v1",
            "data_origin": "synthetic",
            "production_or_cross_tenant_data_used": False,
            "policy": {
                "cohort": "exact synthetic sector and environment class",
                "minimum_peers": 3,
                "deviation_threshold_mad_units": 2.0,
                "ground_truth": (
                    "peer count and closure times assigned by this controlled generator before analysis"
                ),
            },
            "cohort_size_sweep": peer_size_results,
            "outlier_magnitude_sweep": magnitude_results,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "limitations": [
                "Synthetic one-alert entities test only critical-closure peer behavior, not other peer metrics.",
                "This is a small mechanism sensitivity experiment, not real CSE validation or cross-tenant production analysis.",
                "Each cohort shares a local isolated research database under an explicit synthetic cohort policy.",
            ],
        }
    finally:
        engine.close()

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
        "subject_entity_id": subject.id,
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


SWEEP_EXPERIMENT = "peer-cohort-sweep-v1"
SWEEP_COHORT_SIZES = (2, 3, 4, 5, 6, 8)
SWEEP_SUBJECT_CLOSURES = (30, 150, 300, 450, 600, 900, 1500, 3000)
# Peer closure times are evenly spaced around a 600 s centre; "tight" and
# "wide" differ only in spread, so the MAD changes while the median holds.
SWEEP_PEER_SPREADS = {"tight": (540, 660), "wide": (150, 1050)}


def _evenly_spaced(low: int, high: int, count: int) -> list[int]:
    if count == 1:
        return [round((low + high) / 2)]
    step = (high - low) / (count - 1)
    return [round(low + step * index) for index in range(count)]


def _sweep_cell(
    root: Path, *, cohort_id: str, peers: list[int], subject: int
) -> dict[str, Any]:
    """One cohort in its own scratch database, so risk and priority rank
    are computed over exactly this cohort."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.prioritize import prioritize_entities
    from satsa.analysis.risk import compute_entity_risk
    from satsa.service import SatsaService

    cell_root = root / cohort_id
    cell_root.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(cell_root / "peer-cell.sqlite3")
    engine.connect()
    try:
        MigrationRunner(engine).migrate()
        row = _run_case(
            SatsaService(engine),
            cell_root,
            cohort_id=cohort_id,
            peer_closures=peers,
            subject_closure=subject,
        )
        subject_id = row["subject_entity_id"]
        risk = compute_entity_risk(engine, subject_id)
        ranking = prioritize_entities(engine)
        rank = next(
            (i for i, item in enumerate(ranking, 1) if item.entity_id == subject_id),
            None,
        )
        tied_at_top = sum(
            1 for item in ranking if item.priority_score == ranking[0].priority_score
        )
        row.update(
            {
                "peer_distribution": {
                    "values_seconds": peers,
                    "min": min(peers),
                    "max": max(peers),
                },
                "deviation_mad_units": (
                    row["findings"][0]["effect"] if row["findings"] else None
                ),
                "subject_risk_total_score": round(risk.total_score, 4),
                "subject_risk_confidence_bucket": risk.confidence_bucket,
                "subject_priority_rank": rank,
                "cohort_entities_ranked": len(ranking),
                "entities_tied_at_top_priority": tied_at_top,
            }
        )
        return row
    finally:
        engine.close()


def run_peer_sweep_experiment(
    scratch_dir: Path,
    *,
    cohort_sizes: tuple[int, ...] = SWEEP_COHORT_SIZES,
    subject_closures: tuple[int, ...] = SWEEP_SUBJECT_CLOSURES,
    spreads: dict[str, tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """Full factorial peer sweep: cohort size x peer spread x subject value.

    Every cell holds unrelated conditions fixed (one critical alert per
    entity, 10 s acknowledgement, same period) and runs in its own
    scratch database with an explicit synthetic cohort label.
    """
    spreads = spreads or dict(SWEEP_PEER_SPREADS)
    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cells = []
    for spread_name, (low, high) in spreads.items():
        for size in cohort_sizes:
            peers = _evenly_spaced(low, high, size)
            for subject in subject_closures:
                cell = _sweep_cell(
                    root,
                    cohort_id=f"{spread_name}-n{size}-s{subject}",
                    peers=peers,
                    subject=subject,
                )
                cell.update(
                    {
                        "spread": spread_name,
                        "cohort_size": size,
                        "subject_value": subject,
                    }
                )
                cells.append(cell)
    matrix = [
        {
            "spread": cell["spread"],
            "cohort_size": cell["cohort_size"],
            "subject_closure_seconds": cell["subject_value"],
            "peer_count_used": cell["peer_count"],
            "peer_median_seconds": cell["peer_median_seconds"],
            "peer_mad_seconds": cell["peer_mad_seconds"],
            "deviation_mad_units": cell["deviation_mad_units"],
            "finding_emitted": cell["finding_emitted"],
            "subject_risk_total_score": cell["subject_risk_total_score"],
            "subject_priority_rank": cell["subject_priority_rank"],
            "cohort_entities_ranked": cell["cohort_entities_ranked"],
        }
        for cell in cells
    ]
    emitted_by_size = {
        f"{spread}:{size}": sum(
            row["finding_emitted"]
            for row in matrix
            if row["spread"] == spread and row["cohort_size"] == size
        )
        for spread in spreads
        for size in cohort_sizes
    }
    return {
        "status": "completed",
        "experiment": SWEEP_EXPERIMENT,
        "data_origin": "synthetic",
        "production_or_cross_tenant_data_used": False,
        "metrics": {
            "design": {
                "cohort_sizes": list(cohort_sizes),
                "subject_closure_seconds": list(subject_closures),
                "peer_spreads": {k: list(v) for k, v in spreads.items()},
                "peer_values": "evenly spaced between the spread bounds",
                "measured_value": "worker compares creation-to-close time, i.e. the configured "
                "closure value plus the 10 s acknowledgement",
                "fixed": "one critical alert per entity, 10 s acknowledgement, "
                "same assessment period, same sector/environment cohort label",
                "cells": len(matrix),
                "unit": "synthetic cohort (one subject plus its peers)",
            },
            "policy": {"minimum_peers": 3, "deviation_threshold_mad_units": 2.0},
            "findings_emitted_per_spread_and_size": emitted_by_size,
            "matrix": matrix,
            "cells": cells,
        },
        "performance": {
            "measurement_scope": "local synchronous legacy SQLite path",
            "total_elapsed_seconds": round(time.perf_counter() - started, 6),
        },
        "limitations": [
            (
                "Deterministic engineered cohorts; each cell is a mechanism "
                "observation, not a sample from a field distribution."
            ),
            "Only the critical-closure peer metric is exercised; other peer metrics are untouched.",
            "Priority rank is computed within the cell's own cohort only.",
        ],
    }

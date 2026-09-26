"""Component ablation at scenario and population level.

Full default worker set versus exactly one worker removed, with every
other configuration fixed, using ``RunService.run(workers=...)`` exactly
as ``evaluation.ablation.runner`` does. Two views:

* scenario level — the five executable catalog scenarios, each in its own
  scratch database, scored against the declared catalog labels (micro
  family precision/recall/F1), plus finding counts and risk;
* population level — independently seeded synthetic populations; after
  re-running every entity without one worker, the entity ranking is
  rescored against generator labels (precision/recall/NDCG at top-k).

Differences are reported as observed effects of removing a worker from
these inputs. They do not establish that a component is necessary in
general.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from evaluation.research.statistics import describe, paired_comparison

EXPERIMENT_NAME = "satsa-component-ablation-v1"


def _difference(full: float | None, ablated: float | None) -> dict[str, Any]:
    if full is None or ablated is None:
        return {"absolute": None, "relative": None}
    absolute = ablated - full
    return {
        "absolute": round(absolute, 6),
        "relative": round(absolute / full, 6) if full else None,
    }


def _worker_names() -> list[str]:
    from satsa.analysis.run import DEFAULT_FAST_CLOSURE_POLICY, _default_workers

    return [worker.name for worker in _default_workers(DEFAULT_FAST_CLOSURE_POLICY)]


def _workers_without(excluded: str | None):
    from satsa.analysis.run import DEFAULT_FAST_CLOSURE_POLICY, _default_workers

    return [
        worker
        for worker in _default_workers(DEFAULT_FAST_CLOSURE_POLICY)
        if worker.name != excluded
    ]


def _scenario_level(root: Path) -> dict[str, Any]:
    from evaluation.ablation.runner import _emitted_families
    from evaluation.controlled_benchmark.runner import (
        corpus_micro_metrics,
        scenario_family_metrics,
    )
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.compval import SCENARIO_MAP
    from satsa.analysis.risk import compute_entity_risk
    from satsa.analysis.run import RunService
    from satsa.analysis.synth import PERIOD_END, PERIOD_START, _write_cse
    from satsa.analysis.validate import synthetic_ground_truth
    from satsa.service import SatsaService

    labels = {case.case_id: case for case in synthetic_ground_truth()}
    configurations = [None, *_worker_names()]
    per_config: dict[str, list[dict[str, Any]]] = {
        str(name): [] for name in configurations
    }
    for scenario, builder in SCENARIO_MAP.items():
        engine = SQLiteDatabaseEngine(root / f"scenario-{scenario}.sqlite3")
        engine.connect()
        try:
            MigrationRunner(engine).migrate()
            service = SatsaService(engine)
            cse, _ = builder()
            with tempfile.TemporaryDirectory(dir=root) as temporary:
                source = Path(temporary) / scenario
                _write_cse(cse, source)
                entity = service.register_entity(
                    f"ABL-{scenario}", sector="defence", environment_class="on-prem"
                )
                assessment = service.open_assessment(
                    entity.id, PERIOD_START, PERIOD_END
                )
                service.submit(assessment.id, source)
            runs = RunService(engine)
            for excluded in configurations:
                run = runs.run(
                    entity.id, assessment.id, workers=_workers_without(excluded)
                )
                families = sorted(_emitted_families(engine, run.run_id))
                count = engine.query_one(
                    "SELECT COUNT(*) AS n FROM satsa_findings WHERE state='signal'"
                    " AND observation_id IN (SELECT id FROM satsa_observations"
                    " WHERE run_id=?)",
                    (run.run_id,),
                )["n"]
                risk = compute_entity_risk(engine, entity.id, run_id=run.run_id)
                per_config[str(excluded)].append(
                    {
                        "scenario": scenario,
                        "families": families,
                        "signal_findings": count,
                        "risk_total_score": round(risk.total_score, 4),
                        "metrics": scenario_family_metrics(
                            list(labels[scenario].expected_signals), families
                        ),
                    }
                )
        finally:
            engine.close()

    full_rows = per_config["None"]
    full_micro = corpus_micro_metrics(full_rows)
    workers: list[dict[str, Any]] = []
    for name in configurations[1:]:
        rows = per_config[name]
        micro = corpus_micro_metrics(rows)
        lost = {
            full["scenario"]: sorted(set(full["families"]) - set(row["families"]))
            for full, row in zip(full_rows, rows)
            if set(full["families"]) - set(row["families"])
        }
        workers.append(
            {
                "worker_removed": name,
                "micro": micro,
                "difference_vs_full": {
                    metric: _difference(full_micro[metric], micro[metric])
                    for metric in ("precision", "recall", "f1")
                },
                "lost_families_by_scenario": lost,
                "signal_findings_change": sum(r["signal_findings"] for r in rows)
                - sum(r["signal_findings"] for r in full_rows),
                "risk_total_change_by_scenario": {
                    full["scenario"]: round(
                        row["risk_total_score"] - full["risk_total_score"], 4
                    )
                    for full, row in zip(full_rows, rows)
                },
            }
        )
    return {
        "unit": "catalog scenario (five executable fixtures)",
        "full": {"micro": full_micro, "per_scenario": full_rows},
        "workers": workers,
    }


def _population_level(
    root: Path,
    *,
    seeds: int,
    base_seed: int,
    n_entities: int,
    n_pathological: int,
    k_percent: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    from evaluation.research.prioritization import ranking_metrics
    from evaluation.workload import build_population
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.prioritize import prioritize_entities
    from satsa.analysis.run import RunService

    configurations = [None, *_worker_names()]
    scores: dict[str, dict[str, list[float]]] = {
        str(name): {"precision": [], "recall": [], "ndcg": []}
        for name in configurations
    }
    for index in range(seeds):
        seed = base_seed + index
        keys = root / f"population-{seed}" / "keys"
        keys.mkdir(parents=True, exist_ok=True)
        engine = SQLiteDatabaseEngine(keys / "population.sqlite3")
        engine.connect()
        try:
            MigrationRunner(engine).migrate()
            population = build_population(
                engine,
                n_entities=n_entities,
                n_pathological=n_pathological,
                seed=seed,
                trust_key_dir=keys,
            )
            scopes = {
                row["entity_id"]: row["id"]
                for row in engine.query_all(
                    "SELECT id,entity_id FROM satsa_assessments", ()
                )
            }
            universe = set(population.entity_ids)
            runs = RunService(engine)
            for excluded in configurations:
                # Re-run every entity so the ranking reflects this worker set
                # (prioritize_entities uses each entity's latest run).
                for entity_id in population.entity_ids:
                    runs.run(
                        entity_id,
                        scopes[entity_id],
                        workers=_workers_without(excluded),
                    )
                order = [
                    item.entity_id
                    for item in prioritize_entities(engine)
                    if item.entity_id in universe
                ]
                metrics = ranking_metrics(
                    order,
                    set(population.pathological_entity_ids),
                    k_percentages=(k_percent,),
                )[str(k_percent)]
                for metric in ("precision", "recall", "ndcg"):
                    scores[str(excluded)][metric].append(metrics[metric])
        finally:
            engine.close()

    full = scores["None"]
    workers = []
    for name in configurations[1:]:
        workers.append(
            {
                "worker_removed": name,
                "comparisons": {
                    f"{metric}@{k_percent}%": paired_comparison(
                        full[metric],
                        scores[name][metric],
                        unit=metric,
                        pairing="same population seed; only the worker set differs",
                        seed=bootstrap_seed,
                    )
                    for metric in ("precision", "recall", "ndcg")
                },
            }
        )
    return {
        "unit": "generated population (seed)",
        "seeds": [base_seed + i for i in range(seeds)],
        "n_entities": n_entities,
        "n_pathological": n_pathological,
        "k_percent": k_percent,
        "full": {
            f"{metric}@{k_percent}%": describe(full[metric], unit=metric)
            for metric in full
        },
        "workers": workers,
    }


def run_ablation_experiment(
    scratch_dir: Path,
    *,
    seeds: int = 5,
    base_seed: int = 300,
    n_entities: int = 20,
    n_pathological: int = 5,
    k_percent: int = 20,
    bootstrap_seed: int = 0,
    include_population: bool = True,
) -> dict[str, Any]:
    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    metrics: dict[str, Any] = {
        "design": {
            "comparison": "full default worker set vs exactly one worker removed",
            "fixed": "same ingested data, thresholds and code; only the worker set differs",
            "workers": _worker_names(),
        },
        "scenario_level": _scenario_level(root),
    }
    if include_population:
        metrics["population_level"] = _population_level(
            root,
            seeds=seeds,
            base_seed=base_seed,
            n_entities=n_entities,
            n_pathological=n_pathological,
            k_percent=k_percent,
            bootstrap_seed=bootstrap_seed,
        )
    return {
        "status": "completed",
        "experiment": EXPERIMENT_NAME,
        "data_origin": "synthetic",
        "metrics": metrics,
        "performance": {
            "measurement_scope": "local synchronous legacy SQLite path",
            "total_elapsed_seconds": round(time.perf_counter() - started, 6),
        },
        "limitations": [
            (
                "Five authored scenarios and a few generated populations; a removed "
                "worker's effect is specific to these inputs and says nothing about "
                "its general necessity."
            ),
            (
                "Workers can overlap; removing one may be masked by another, so a "
                "zero difference does not mean zero contribution."
            ),
        ],
    }

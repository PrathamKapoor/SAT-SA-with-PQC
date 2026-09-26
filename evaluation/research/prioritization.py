"""Seed-replicated prioritization comparison with matched baselines.

Each replicate is an independently generated synthetic population
(``evaluation.workload.build_population``) in its own scratch database;
the population seed is the independent unit of analysis. Within a
replicate every method ranks exactly the same entity universe and is
scored against the same generator-assigned labels with the same top-k
budget:

* ``satsa`` — ``satsa.analysis.prioritize.prioritize_entities``;
* ``random`` — the mean over seeded random permutations (its expectation);
* ``critical_alert_volume`` — most critical/high alerts first;
* ``fastest_median_closure`` — shortest median alert close time first.

The two heuristics read only the canonical alert records every method
receives; they never read SAT-SA findings, risk or priority. Ties are
broken by a seeded shuffle recorded in the result. Labels come from the
generator configuration before any analysis runs.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from pathlib import Path
from typing import Any

from evaluation.research.statistics import describe, paired_comparison

EXPERIMENT_NAME = "satsa-prioritization-replicated-v1"
DEFAULT_K_PERCENTAGES = (10, 20, 30)
HEURISTICS = ("critical_alert_volume", "fastest_median_closure")


def _top_n(n: int, k_percent: int) -> int:
    return max(1, round(n * k_percent / 100))


def ranking_metrics(
    ordered: list[str], relevant: set[str], *, k_percentages: tuple[int, ...]
) -> dict[str, Any]:
    """precision@k, recall@k, NDCG@k (binary relevance) and review volume."""
    n = len(ordered)
    out: dict[str, Any] = {}
    for k in k_percentages:
        top = _top_n(n, k)
        hits = [1 if entity in relevant else 0 for entity in ordered[:top]]
        dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
        ideal = sum(1 / math.log2(rank + 2) for rank in range(min(top, len(relevant))))
        out[str(k)] = {
            "top_n": top,
            "precision": sum(hits) / top,
            "recall": sum(hits) / len(relevant) if relevant else None,
            "ndcg": dcg / ideal if ideal else None,
        }
    last = max(
        (index for index, entity in enumerate(ordered, 1) if entity in relevant),
        default=0,
    )
    out["review_volume_to_find_all"] = last
    return out


def _heuristic_orders(
    engine, entity_ids: list[str], rng: random.Random
) -> dict[str, list[str]]:
    features: dict[str, dict[str, float]] = {}
    for entity_id in entity_ids:
        rows = engine.query_all(
            "SELECT mapped_severity,created_at,closed_at FROM satsa_alerts"
            " WHERE entity_id=?",
            (entity_id,),
        )
        closes = [
            float(row["closed_at"]) - float(row["created_at"])
            for row in rows
            if row["closed_at"] is not None
        ]
        features[entity_id] = {
            "critical_alert_volume": sum(
                row["mapped_severity"] in {"critical", "high"} for row in rows
            ),
            "median_close": statistics.median(closes) if closes else math.inf,
        }
    tiebreak = list(entity_ids)
    rng.shuffle(tiebreak)
    position = {entity: index for index, entity in enumerate(tiebreak)}
    return {
        "critical_alert_volume": sorted(
            entity_ids,
            key=lambda e: (-features[e]["critical_alert_volume"], position[e]),
        ),
        "fastest_median_closure": sorted(
            entity_ids, key=lambda e: (features[e]["median_close"], position[e])
        ),
    }


def _mean_random_metrics(
    entity_ids: list[str],
    relevant: set[str],
    *,
    k_percentages: tuple[int, ...],
    trials: int,
    rng: random.Random,
) -> dict[str, Any]:
    samples = []
    for _ in range(trials):
        order = list(entity_ids)
        rng.shuffle(order)
        samples.append(ranking_metrics(order, relevant, k_percentages=k_percentages))
    out: dict[str, Any] = {}
    for k in k_percentages:
        key = str(k)
        out[key] = {"top_n": samples[0][key]["top_n"]}
        for metric in ("precision", "recall", "ndcg"):
            values = [s[key][metric] for s in samples if s[key][metric] is not None]
            out[key][metric] = statistics.fmean(values) if values else None
    out["review_volume_to_find_all"] = statistics.fmean(
        s["review_volume_to_find_all"] for s in samples
    )
    return out


def _replicate(
    root: Path,
    *,
    seed: int,
    n_entities: int,
    n_pathological: int,
    k_percentages: tuple[int, ...],
    random_trials: int,
) -> dict[str, Any]:
    from evaluation.workload import build_population
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.prioritize import prioritize_entities

    keys = root / f"seed-{seed}" / "keys"
    keys.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(keys / "population.sqlite3")
    engine.connect()
    try:
        MigrationRunner(engine).migrate()
        started = time.perf_counter()
        population = build_population(
            engine,
            n_entities=n_entities,
            n_pathological=n_pathological,
            seed=seed,
            trust_key_dir=keys,
        )
        universe = list(population.entity_ids)
        relevant = set(population.pathological_entity_ids)
        satsa_order = [
            item.entity_id
            for item in prioritize_entities(engine)
            if item.entity_id in set(universe)
        ]
        if set(satsa_order) != set(universe):
            raise AssertionError("prioritize_entities did not rank the full universe")
        rng = random.Random(f"{EXPERIMENT_NAME}:{seed}")
        orders = {"satsa": satsa_order, **_heuristic_orders(engine, universe, rng)}
        methods = {
            name: ranking_metrics(order, relevant, k_percentages=k_percentages)
            for name, order in orders.items()
        }
        methods["random"] = _mean_random_metrics(
            universe,
            relevant,
            k_percentages=k_percentages,
            trials=random_trials,
            rng=rng,
        )
        return {
            "seed": seed,
            "n_entities": n_entities,
            "n_pathological": n_pathological,
            "label_source": "generator configuration assigned before analysis",
            "methods": methods,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }
    finally:
        engine.close()


def run_prioritization_experiment(
    scratch_dir: Path,
    *,
    seeds: int = 20,
    base_seed: int = 100,
    n_entities: int = 20,
    n_pathological: int = 5,
    k_percentages: tuple[int, ...] = DEFAULT_K_PERCENTAGES,
    random_trials: int = 200,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    """Run ``seeds`` independent populations and compare methods pairwise."""
    if seeds < 1 or n_entities < 1 or not 0 < n_pathological < n_entities:
        raise ValueError("need seeds >= 1 and 0 < n_pathological < n_entities")
    smallest_top = min(_top_n(n_entities, k) for k in k_percentages)
    root = Path(scratch_dir)
    started = time.perf_counter()
    replicates = [
        _replicate(
            root,
            seed=base_seed + index,
            n_entities=n_entities,
            n_pathological=n_pathological,
            k_percentages=k_percentages,
            random_trials=random_trials,
        )
        for index in range(seeds)
    ]
    methods = ("satsa", "random", *HEURISTICS)

    def series(method: str, k: int, metric: str) -> list[float]:
        return [r["methods"][method][str(k)][metric] for r in replicates]

    summary: dict[str, Any] = {}
    comparisons: dict[str, Any] = {}
    for k in k_percentages:
        for metric in ("precision", "recall", "ndcg"):
            key = f"{metric}@{k}%"
            summary[key] = {
                method: describe(series(method, k, metric), unit=metric)
                for method in methods
            }
            for baseline in ("random", *HEURISTICS):
                comparisons[f"satsa_vs_{baseline}:{key}"] = paired_comparison(
                    series(baseline, k, metric),
                    series("satsa", k, metric),
                    unit=metric,
                    pairing="same population seed, entity universe, labels and top-k",
                    seed=bootstrap_seed,
                )
    volume = {
        method: describe(
            [r["methods"][method]["review_volume_to_find_all"] for r in replicates],
            unit="entities reviewed",
        )
        for method in methods
    }
    return {
        "status": "completed",
        "experiment": EXPERIMENT_NAME,
        "data_origin": "synthetic",
        "metrics": {
            "design": {
                "replicates": seeds,
                "seed_policy": f"population seed = {base_seed} + replicate index",
                "independent_unit": "generated population (seed)",
                "n_entities": n_entities,
                "n_pathological": n_pathological,
                "k_percentages": list(k_percentages),
                "smallest_top_n": smallest_top,
                "random_trials_per_replicate": random_trials,
                "confidence_level": 0.95,
                "tie_policy": "heuristic ties broken by a seeded shuffle",
                "coarseness_note": (
                    f"with {n_entities} entities, top-k budgets are small integers "
                    "(smallest top_n shown above); per-replicate estimates are coarse"
                ),
            },
            "summary": summary,
            "review_volume_to_find_all": volume,
            "comparisons": comparisons,
            "replicates": replicates,
        },
        "performance": {
            "measurement_scope": "local synchronous legacy SQLite path",
            "total_elapsed_seconds": round(time.perf_counter() - started, 6),
        },
        "limitations": [
            (
                "Populations come from SAT-SA's own synthetic generator with two "
                "profiles (pathological/clean); detectors were written for the "
                "behaviors those profiles inject, so separation may be optimistic."
            ),
            (
                "Several metrics and baselines are compared; intervals are "
                "descriptive and uncorrected, and no significance claim is made."
            ),
        ],
    }

from __future__ import annotations

import math

import pytest

from evaluation.research.ablation import run_ablation_experiment
from evaluation.research.prioritization import (
    ranking_metrics,
    run_prioritization_experiment,
)


def test_ranking_metrics_match_hand_computed_values():
    order = ["a", "x", "b", "y", "z"]
    metrics = ranking_metrics(order, {"a", "b"}, k_percentages=(40, 60))
    assert metrics["40"]["top_n"] == 2
    assert metrics["40"]["precision"] == 0.5
    assert metrics["40"]["recall"] == 0.5
    ideal = 1 + 1 / math.log2(3)
    assert metrics["40"]["ndcg"] == pytest.approx(1 / ideal)
    assert metrics["60"]["recall"] == 1.0
    assert metrics["review_volume_to_find_all"] == 3


def test_prioritization_compares_methods_on_the_same_universe(tmp_path):
    result = run_prioritization_experiment(
        tmp_path, seeds=1, n_entities=8, n_pathological=2, random_trials=20
    )
    replicate = result["metrics"]["replicates"][0]
    assert set(replicate["methods"]) == {
        "satsa",
        "random",
        "critical_alert_volume",
        "fastest_median_closure",
    }
    budgets = {m["20"]["top_n"] for m in replicate["methods"].values()}
    assert budgets == {2}
    comparison = result["metrics"]["comparisons"]["satsa_vs_random:recall@20%"]
    assert comparison["n_pairs"] == 1
    assert comparison["adequacy"].startswith("exploratory")


def test_ablation_scores_each_removed_worker_against_catalog(tmp_path):
    result = run_ablation_experiment(tmp_path, include_population=False)
    scenario = result["metrics"]["scenario_level"]
    workers = {row["worker_removed"]: row for row in scenario["workers"]}
    assert set(workers) == set(result["metrics"]["design"]["workers"])
    assert scenario["full"]["micro"]["recall"] == 1.0
    fast = workers["fast-closure"]
    assert (
        "execution_gap.fast_closure"
        in fast["lost_families_by_scenario"]["eg-fast-closure"]
    )
    assert fast["difference_vs_full"]["recall"]["absolute"] < 0

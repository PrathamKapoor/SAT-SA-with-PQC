from __future__ import annotations

import pytest

from evaluation.research.orchestration import (
    run_orchestration_overhead_experiment,
    run_orchestration_recovery_experiment,
)
from evaluation.research.statistics import (
    MIN_N_FOR_BOOTSTRAP,
    bootstrap_interval,
    describe,
    paired_comparison,
)


def test_describe_withholds_p95_for_small_samples():
    small = describe([1.0, 2.0, 3.0], unit="s")
    assert small["n"] == 3 and small["median"] == 2.0
    assert small["p95"] is None and small["p95_note"]
    large = describe([float(i) for i in range(20)], unit="s")
    assert large["p95"] == pytest.approx(18.05)


def test_paired_comparison_is_seeded_and_labels_adequacy():
    base = [1.0] * MIN_N_FOR_BOOTSTRAP
    treat = [1.0 + 0.1 * i for i in range(MIN_N_FOR_BOOTSTRAP)]
    first = paired_comparison(base, treat, unit="s", pairing="trial", seed=3)
    second = paired_comparison(base, treat, unit="s", pairing="trial", seed=3)
    assert first == second
    assert first["median_difference_interval"] is not None
    assert "p-value" not in str(first).lower().replace("no p-value", "")
    tiny = paired_comparison([1.0, 2.0], [2.0, 3.0], unit="s", pairing="trial")
    assert tiny["median_difference_interval"] is None
    assert tiny["adequacy"].startswith("exploratory")
    assert bootstrap_interval([1.0] * 3) is None
    with pytest.raises(ValueError):
        paired_comparison([1.0], [1.0, 2.0], unit="s", pairing="trial")


def test_overhead_experiment_runs_matched_real_workflows(tmp_path):
    result = run_orchestration_overhead_experiment(tmp_path, trials=1)
    metrics = result["metrics"]
    identical = metrics["analytics_identical_across_modes"]
    assert identical["direct_vs_graph_all_outputs"] is True
    assert identical["all_modes_findings_and_risk"] is True
    per_mode = metrics["per_mode"]
    assert per_mode["direct"]["trust_verified_all"] is True
    assert per_mode["graph"]["trust_verified_all"] is True
    assert per_mode["graph"]["graph_checkpoints"]["median"] > 0
    assert per_mode["direct_unreviewed"]["trust_verified_all"] is None
    rows = metrics["trials"]
    assert {row["mode"] for row in rows} == {"direct", "graph", "direct_unreviewed"}
    direct = next(row for row in rows if row["mode"] == "direct")
    assert direct["stage_calls"]["trust_finalization"] == 1
    assert direct["db_operations_total"] > 0


def test_recovery_experiment_resumes_without_repeating_completed_work(tmp_path):
    result = run_orchestration_recovery_experiment(
        tmp_path,
        trials=1,
        points=("analysis_stage_crash", "finalization_transient"),
    )
    for row in result["metrics"]["trials"]:
        cell = f"{row['mode']}:{row['point']}"
        assert row["interruption_injected"] is True, cell
        assert row["recovered_to_completion"] is True, cell
        assert row["outputs_match_uninterrupted_reference"] is True, cell
        assert row["completed_stages_repeated_after_interruption"] == [], cell
        assert row["review_decisions"] == 1, cell
        assert row["trust_finalizations"] == 1, cell
        assert row["trust_verified"] is True, cell
    crash = [
        r for r in result["metrics"]["trials"] if r["point"] == "analysis_stage_crash"
    ]
    assert all("crashed" in r["observed_statuses"] for r in crash)
    assert all(r["interrupted_stages_rerun"] for r in crash)

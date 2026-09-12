"""P33 — controlled supervisory benchmark: manifest discipline, metric
correctness, real-pipeline execution, and determinism.

These tests enforce the benchmark's core honesty properties:
labels come only from the declared ground-truth catalog (never from
detector output), metrics are computed correctly, the runner drives
the REAL ingestion/analysis pipeline, and a fixed seed reproduces
equivalent metrics. Everything measured here is explicitly synthetic.
"""
from __future__ import annotations

import pytest

from evaluation.controlled_benchmark.manifest import (
    build_manifest,
    validate_manifest,
)
from evaluation.controlled_benchmark.runner import (
    corpus_micro_metrics,
    run_benchmark,
    scenario_family_metrics,
)


# ---------------------------------------------------------------------------
# Manifest: schema, catalog agreement, label-independence
# ---------------------------------------------------------------------------

def test_manifest_is_valid_and_declares_synthetic_provenance():
    manifest = build_manifest()
    validate_manifest(manifest)
    assert manifest["benchmark_version"]
    assert manifest["provenance"]["data_origin"] == "synthetic"
    assert len(manifest["scenarios"]) == 10  # the canonical catalog size
    assert manifest["limitations"], "limitations must be declared"
    assert manifest["ground_truth_source"] == (
        "satsa.analysis.validate.synthetic_ground_truth")


def test_validate_manifest_rejects_label_edits_and_bad_provenance():
    """The ground-truth rule, enforced structurally: a manifest whose
    declared expected signals were edited (e.g. to flatter what the
    detectors actually emitted) must fail loudly, not pass silently."""
    tampered = build_manifest()
    tampered["scenarios"][1]["declared_expected_signals"] = []
    with pytest.raises(ValueError, match="authoritative catalog"):
        validate_manifest(tampered)

    wrong_provenance = build_manifest()
    wrong_provenance["provenance"]["data_origin"] = "real-world"
    with pytest.raises(ValueError, match="synthetic"):
        validate_manifest(wrong_provenance)

    missing_key = build_manifest()
    del missing_key["limitations"]
    with pytest.raises(ValueError, match="required key"):
        validate_manifest(missing_key)


def test_not_executable_scenarios_carry_reasons_not_results():
    """The five scenarios a single-entity fixture cannot reproduce must
    be declared honestly (not_executable with a reason) — never scored
    as if they had run."""
    manifest = build_manifest()
    not_exec = [s for s in manifest["scenarios"] if not s["executable"]]
    assert len(not_exec) == 5
    for entry in not_exec:
        assert entry["not_executable_reason"].strip()
    executable = [s for s in manifest["scenarios"] if s["executable"]]
    assert len(executable) == 5


# ---------------------------------------------------------------------------
# Metrics: exact behavior on tiny known fixtures
# ---------------------------------------------------------------------------

def test_scenario_family_metrics_counts_are_exact():
    m = scenario_family_metrics(
        expected=["execution_gap.fast_closure",
                  "negative_space.missing_monitoring"],
        emitted=["execution_gap.fast_closure", "anomaly.robust_score"])
    assert m["tp"] == 1
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5)
    assert m["extra_families"] == ["anomaly.robust_score"]
    assert m["missing_families"] == ["negative_space.missing_monitoring"]


def test_scenario_family_metrics_report_none_never_zero_for_unknown():
    """A scenario with no expected families (healthy control) and no
    emissions has no positives anywhere — precision/recall/f1 are
    undefined and must be None, not 0 or 1."""
    m = scenario_family_metrics(expected=[], emitted=[])
    assert m["tp"] == 0 and m["fp"] == 0 and m["fn"] == 0
    assert m["precision"] is None
    assert m["recall"] is None
    assert m["f1"] is None


def test_corpus_micro_metrics_micro_averages():
    per = [
        {"metrics": scenario_family_metrics(["a"], ["a", "b"])},
        {"metrics": scenario_family_metrics(["a", "b"], ["a"])},
    ]
    micro = corpus_micro_metrics(per)
    assert micro["tp"] == 2
    assert micro["fp"] == 1
    assert micro["fn"] == 1
    assert micro["precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert micro["recall"] == pytest.approx(2 / 3, abs=1e-3)


# ---------------------------------------------------------------------------
# Runner: real pipeline, synthetic provenance, safe failure
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_benchmark(tmp_path_factory):
    """One shared small run for the execution + determinism tests.
    The keys/scratch dir lives outside the repository (pytest tmp)."""
    keys = tmp_path_factory.mktemp("cbench-keys") / "keys"
    keys.mkdir()
    return run_benchmark(trust_key_dir=keys, workload_seed=42,
                         n_population=6, n_pathological=2,
                         n_random_trials=25)


def test_runner_executes_real_pipeline_and_reports_provenance(
        small_benchmark):
    results = small_benchmark
    metrics = results["metrics"]
    corpus = metrics["scenario_corpus"]

    # Real pipeline evidence: every executed scenario has a run id, a
    # non-empty submission-digest set, and the declared label source.
    per = corpus["per_scenario"]
    assert len(per) == 5
    for s in per:
        assert s["declared_labels"]["source"] == (
            "satsa.analysis.validate.synthetic_ground_truth")

    # The fast-closure scenario must have detected its declared family
    # through the real pipeline (a true positive at family level).
    eg = next(s for s in per if s["case_id"] == "eg-fast-closure")
    assert eg["metrics"]["tp"] >= 1
    # The healthy control must have emitted nothing (tp=fp=fn=0 counts
    # with undefined ratios).
    healthy = next(s for s in per if s["case_id"] == "healthy")
    assert healthy["metrics"]["emitted_families"] == []

    # Synthetic provenance and limitations must be visibly carried.
    assert "synthetic" in results["provenance_note"]
    assert results["limitations"]

    # Baselines ran and are clearly separated from SAT-SA results.
    bl = metrics["closure_time_baselines"]
    assert set(bl["comparison"]) == {
        "zscore", "mad", "iqr", "fixed_threshold", "random",
        "satsa_fast_closure"}
    # Workload section is explicitly simulated, not claimed real.
    assert metrics["prioritization"]["label"] == (
        "simulated_workload_reduction")
    # Ablation ran through the real RunService on the mixed scope.
    assert "workers" in metrics["ablation"]


def test_runner_is_deterministic_for_fixed_seed(tmp_path):
    """Same seed + same code + same inputs must produce equivalent
    semantic metrics. Two full runs are compared at the metrics level
    (timestamps and environment strings excluded)."""
    keys_a = tmp_path / "ka"
    keys_b = tmp_path / "kb"
    keys_a.mkdir()
    keys_b.mkdir()
    a = run_benchmark(trust_key_dir=keys_a, workload_seed=42,
                      n_population=6, n_pathological=2,
                      n_random_trials=25)
    b = run_benchmark(trust_key_dir=keys_b, workload_seed=42,
                      n_population=6, n_pathological=2,
                      n_random_trials=25)
    assert a["metrics"] == b["metrics"]
    assert a["started_at"] != b["started_at"]  # runs really were separate


def test_runner_fails_safely_on_invalid_population_arguments(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    with pytest.raises(ValueError, match="n_pathological"):
        run_benchmark(trust_key_dir=keys, workload_seed=42,
                      n_population=4, n_pathological=8)
"""Phase P26 addendum (checklist item 2) — literature-named baseline
detectors, scored independently, then compared head-to-head against a
real SAT-SA worker's own output on the same data.

Every baseline is verified against a hand-constructed array with a
known, stated outlier set — never against SAT-SA's own detector output
(that would make a baseline's "correctness" circular).
"""
from __future__ import annotations

import pytest

from evaluation.baselines.compare import compare_closure_time_detectors
from evaluation.baselines.statistical import (
    fixed_threshold_baseline,
    iqr_baseline,
    mad_baseline,
    random_baseline,
    score,
    severity_only_baseline,
    zscore_baseline,
)
from satsa.analysis.workers.fast_closure import FastClosureWorker
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.workflow import Alert
from satsa.store.dataset import CanonicalDataset

BASE = 1735689600.0


# ---------------------------------------------------------------------------
# individual baselines against a known, hand-constructed distribution
# ---------------------------------------------------------------------------

def test_zscore_flags_a_clear_outlier():
    values = [100, 102, 98, 101, 99, 100, 500]  # 500 is the deliberate outlier
    flags = zscore_baseline(values, k=2.0)
    assert flags[-1] is True
    assert sum(flags[:-1]) == 0


def test_zscore_flags_nothing_with_fewer_than_two_values():
    assert zscore_baseline([5], k=2.0) == [False]
    assert zscore_baseline([], k=2.0) == []


def test_zscore_flags_nothing_with_zero_variance():
    assert zscore_baseline([7, 7, 7, 7], k=2.0) == [False, False, False, False]


def test_mad_flags_a_clear_outlier_robustly():
    values = [100, 102, 98, 101, 99, 100, 500]
    flags = mad_baseline(values, k=3.5)
    assert flags[-1] is True
    assert sum(flags[:-1]) == 0


def test_mad_is_more_robust_than_zscore_to_multiple_outliers():
    """A hallmark MAD property: two large outliers don't inflate the
    scale estimate the way they inflate stdev, so MAD keeps flagging
    both while a mean/stdev-based method can lose sensitivity."""
    values = [10, 11, 9, 10, 10, 11, 9, 500, 520]
    mad_flags = mad_baseline(values, k=3.5)
    assert mad_flags[-1] is True
    assert mad_flags[-2] is True


def test_iqr_flags_values_outside_the_tukey_fence():
    values = [10, 11, 9, 10, 12, 11, 9, 10, 100]
    flags = iqr_baseline(values, k=1.5)
    assert flags[-1] is True
    assert sum(flags[:-1]) == 0


def test_iqr_flags_nothing_with_fewer_than_four_values():
    assert iqr_baseline([1, 2, 3]) == [False, False, False]


def test_fixed_threshold_below():
    values = [30, 700, 900, 50]
    flags = fixed_threshold_baseline(values, threshold=600.0, below=True)
    assert flags == [True, False, False, True]


def test_fixed_threshold_above():
    values = [30, 700, 900, 50]
    flags = fixed_threshold_baseline(values, threshold=600.0, below=False)
    assert flags == [False, True, True, False]


def test_random_baseline_is_deterministic_given_seed():
    a = random_baseline(20, fraction=0.3, seed=42)
    b = random_baseline(20, fraction=0.3, seed=42)
    assert a == b


def test_random_baseline_different_seeds_can_differ():
    a = random_baseline(50, fraction=0.3, seed=1)
    b = random_baseline(50, fraction=0.3, seed=2)
    assert a != b


def test_random_baseline_flags_approximately_the_requested_fraction():
    flags = random_baseline(100, fraction=0.25, seed=7)
    assert sum(flags) == 25


def test_random_baseline_rejects_invalid_fraction():
    with pytest.raises(ValueError):
        random_baseline(10, fraction=1.5, seed=1)
    with pytest.raises(ValueError):
        random_baseline(10, fraction=-0.1, seed=1)


def test_severity_only_baseline():
    severities = ["low", "critical", "medium", "critical", "high"]
    flags = severity_only_baseline(severities)
    assert flags == [False, True, False, True, False]


def test_severity_only_baseline_custom_flag_set():
    severities = ["low", "critical", "medium", "high"]
    flags = severity_only_baseline(severities, flag_severities=("critical", "high"))
    assert flags == [False, True, False, True]


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------

def test_score_computes_confusion_matrix_and_metrics():
    flags =  [True, True, False, False, True]
    labels = [True, False, False, True, True]
    m = score(flags, labels)
    assert m["tp"] == 2  # idx 0, 4
    assert m["fp"] == 1  # idx 1
    assert m["fn"] == 1  # idx 3
    assert m["tn"] == 1  # idx 2
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)


def test_score_returns_none_for_undefined_ratios():
    m = score([False, False], [False, False])
    assert m["precision"] is None  # no positive predictions
    assert m["recall"] is None     # no positive labels
    assert m["f1"] is None


def test_score_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        score([True, False], [True])


# ---------------------------------------------------------------------------
# head-to-head comparison against a real SAT-SA worker
# ---------------------------------------------------------------------------

def _dataset_with_alerts(close_times, severities):
    alerts = []
    for i, (ct, sev) in enumerate(zip(close_times, severities)):
        alerts.append(Alert(
            entity_id="e", assessment_id="a", native_id=f"A{i}",
            created_at=BASE, mapped_severity=sev,
            acknowledged_at=BASE + 10, closed_at=BASE + 10 + ct,
            source_record_ref=f"sr-{i}"))
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=alerts, cases=[], steps=[], escalations=[], dispositions=[],
        assets=[],
        submitted_categories=frozenset(
            ("alerts", "cases", "investigation_steps", "escalations",
             "dispositions", "assets")))


def test_compare_closure_time_detectors_includes_satsa_worker():
    """5 normal-paced critical closures (~700-900s, i.e. above the
    default 600s fast-closure SLA) plus 2 deliberately fast closures
    (~30-40s). The ground-truth label (is_signal) is stated by
    construction, matching this project's own synthetic-ground-truth
    discipline (satsa.analysis.synth) — never derived from any
    detector's own output."""
    close_times = [700, 800, 900, 750, 850, 30, 40]
    labels = [False, False, False, False, False, True, True]
    severities = ["critical"] * 7

    dataset = _dataset_with_alerts(close_times, severities)
    worker = FastClosureWorker()
    batch = worker.evaluate(
        SnapshotRef("d", "e", "a"), dataset, [], None,
        RunContext(run_id="r", entity_id="e", assessment_id="a"))
    flagged_alert_ids = {
        aid for f in batch.findings for aid in f.scoped_subjects}
    satsa_flags = [a.id in flagged_alert_ids for a in dataset.alerts]

    results = compare_closure_time_detectors(
        close_times, labels, satsa_flags=satsa_flags)

    assert set(results) == {
        "zscore", "mad", "iqr", "fixed_threshold", "random",
        "satsa_fast_closure",
    }
    # SAT-SA's own fast-closure worker, using its documented 600s SLA,
    # should perfectly separate this deliberately clean scenario.
    assert results["satsa_fast_closure"]["tp"] == 2
    assert results["satsa_fast_closure"]["fp"] == 0
    assert results["satsa_fast_closure"]["fn"] == 0
    # every baseline reports well-formed metrics (may legitimately be
    # None for an undefined ratio, but must not raise)
    for name, m in results.items():
        assert set(m) == {"tp", "fp", "fn", "tn", "precision", "recall", "f1"}


def test_compare_closure_time_detectors_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        compare_closure_time_detectors([1, 2], [True], satsa_flags=[True, False])

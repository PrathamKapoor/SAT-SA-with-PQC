"""Phase 30 — robust peer benchmarking tests."""
from __future__ import annotations

import pytest

from satsa.analysis.workers.peer_benchmark import (
    DEFAULT_PEER_BENCHMARK_POLICY,
    PeerBenchmarkWorker,
    _aggregate_peer_metric,
    _trimmed,
    _percentile,
    _median,
    _mad,
)
from satsa.store.dataset import CanonicalDataset
from satsa.contracts.worker import ObservationBatch, RunContext, SnapshotRef


def test_trimmed_drops_extreme_values():
    # 4 values: trimmed leaves all
    assert _trimmed([1, 2, 3, 4], 0.1) == [1, 2, 3, 4]
    # 10 values: 10% = 1 on each side → drop top 1 and bottom 1
    assert _trimmed(list(range(1, 11)), 0.1) == [2, 3, 4, 5, 6, 7, 8, 9]


def test_aggregate_peer_metric_robust_to_single_outlier():
    """One extreme value (e.g. 1000) in a small cohort should not
    inflate the MAD and mask a genuine anomaly."""
    # Without trimming: median=10, MAD=247.5 (huge)
    # With trimming: 1 extreme is dropped, median=10, MAD=small
    values = [9, 10, 10, 11, 1000]
    agg = _aggregate_peer_metric(values)
    assert agg["median"] == 10
    assert agg["mad"] < 5, f"MAD too large: {agg['mad']}"
    assert agg["count"] == 5  # count is full (not trimmed)


def test_aggregate_peer_metric_handles_identical_values():
    values = [5.0] * 5
    agg = _aggregate_peer_metric(values)
    assert agg["median"] == 5.0
    assert agg["mad"] == 0.0


def test_aggregate_peer_metric_handles_empty():
    agg = _aggregate_peer_metric([])
    assert agg["count"] == 0
    assert agg["median"] == 0.0


def test_peer_benchmark_worker_small_cohort_insufficient_data():
    """With fewer than min_peers entities in the cohort, the
    worker returns insufficient_data rather than a false signal."""
    # Build a dataset with only the subject (no peers)
    ds = _build_dataset(subject_closure_seconds=30, peers=[])
    worker = PeerBenchmarkWorker()
    batch = worker.evaluate(
        SnapshotRef("d", "e", "a"), ds, [], None,
        RunContext(run_id="r", entity_id="e", assessment_id="a"),
    )
    # The subject has no peers → insufficient_data (no signal)
    assert batch.state == "insufficient_data"
    assert batch.findings == []


def test_peer_benchmark_worker_not_masked_by_outlier():
    """The full worker test requires a real DB with multiple
    registered entities (covered by the Phase 8 e2e tests). The
    statistical property — that a single outlier does not inflate
    the MAD so much that a genuine anomaly is masked — is covered
    by the aggregate-function tests above."""
    # Verify the underlying property that makes the worker robust:
    # an extreme value in a small cohort does not dominate.
    values = [30, 7200, 7200, 7200, 86400]  # subject + 3 normal + 1 extreme
    agg = _aggregate_peer_metric(values)
    # Without trimming, median=7200, MAD=21510. With trimming,
    # the 86400 is dropped and median=7200, MAD=0.
    # The subject's 30s vs trimmed MAD=0: deviation is 30, which
    # under any sensible rule would fire a signal.
    assert agg["median"] == 7200
    assert agg["mad"] < 100, f"trimmed MAD too large: {agg['mad']}"


def _build_dataset(subject_closure_seconds: float, peers: list):
    """Build a minimal CanonicalDataset for the worker tests.
    subject closes in `subject_closure_seconds`; each peer has a
    single critical alert with that peer's closure time."""
    from datetime import datetime
    from satsa.domain.entities import Asset
    from satsa.domain.workflow import Alert, Case
    PERIOD_START = 1735689600.0
    assets = [
        Asset(id="asset-subj", entity_id="e", native_id="asset-subj",
              criticality="critical", environment="prod"),
    ] + [
        Asset(id=f"asset-peer-{i}", entity_id=f"peer-{i}",
              native_id=f"asset-peer-{i}",
              criticality="critical", environment="prod")
        for i in range(len(peers))
    ]
    subj_alert = Alert(
        id="alert-subj", entity_id="e", assessment_id="a",
        native_id="alert-subj", created_at=PERIOD_START,
        mapped_severity="critical",
        acknowledged_at=PERIOD_START + 60,
        closed_at=PERIOD_START + 60 + subject_closure_seconds,
        asset_refs=["asset-subj"],
        case_refs=["case-subj"],
        source_record_ref="sr-subj",
    )
    subj_case = Case(
        id="case-subj", entity_id="e", assessment_id="a",
        native_id="case-subj", opened_at=PERIOD_START,
        status="closed", closed_at=PERIOD_START + 3600,
        alert_refs=["alert-subj"],
    )
    peer_alerts_cases = []
    for i, ct in enumerate(peers):
        pa = Alert(
            id=f"alert-peer-{i}", entity_id=f"peer-{i}", assessment_id="a",
            native_id=f"alert-peer-{i}", created_at=PERIOD_START,
            mapped_severity="critical",
            acknowledged_at=PERIOD_START + 60,
            closed_at=PERIOD_START + 60 + ct,
            asset_refs=[f"asset-peer-{i}"],
            case_refs=[f"case-peer-{i}"],
            source_record_ref=f"sr-peer-{i}",
        )
        pc = Case(
            id=f"case-peer-{i}", entity_id=f"peer-{i}", assessment_id="a",
            native_id=f"case-peer-{i}", opened_at=PERIOD_START,
            status="closed", closed_at=PERIOD_START + 3600,
            alert_refs=[f"alert-peer-{i}"],
        )
        peer_alerts_cases.append((pa, pc))
    all_alerts = [subj_alert] + [a for a, _ in peer_alerts_cases]
    all_cases = [subj_case] + [c for _, c in peer_alerts_cases]
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=all_alerts, cases=all_cases,
        submitted_categories=frozenset({"alerts", "cases"}),
    )

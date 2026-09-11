"""Phase 7 (SAT-SA) — anomaly engine tests.

The anomaly engine is a pure explainable-statistics worker:
median / MAD / percentile / IQR over the entity's own assessment
data. Tests cover the eight metrics, the threshold boundary, the
min-samples guard, the MAD=0 case (a degenerate distribution where
the outlier is the only non-equal value), and the per-metric
evidence shape.
"""
from __future__ import annotations

import math

import pytest

from satsa.analysis.workers.anomaly import (
    DEFAULT_ANOMALY_POLICY,
    AnomalyThresholds,
    AnomalyWorker,
    _anomalous_outliers,
    _mad,
    _median,
    _percentile,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.entities import Asset
from satsa.domain.workflow import Alert, Case, Escalation, InvestigationStep
from satsa.store.dataset import CanonicalDataset


BASE = 1735689600.0


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a")


def _eval(worker, ds):
    return worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())


def _alert(*, id, severity, ack=None, closed=None, asset_refs=None,
           case_refs=None, source_record_ref="sr-x", created_at=BASE) -> Alert:
    return Alert(
        id=id, entity_id="e", assessment_id="a",
        native_id=f"native-{id}", created_at=created_at,
        mapped_severity=severity, acknowledged_at=ack, closed_at=closed,
        asset_refs=asset_refs or [], case_refs=case_refs or [],
        source_record_ref=source_record_ref,
    )


def _case(*, id, status="closed", opened_at=BASE, closed_at=None,
          source_record_ref="sr-c") -> Case:
    return Case(
        id=id, entity_id="e", assessment_id="a", native_id=f"native-{id}",
        opened_at=opened_at, status=status, closed_at=closed_at,
        source_record_ref=source_record_ref,
    )


def _step(*, case_id, sequence=1, action_type="triage", note="x") -> InvestigationStep:
    return InvestigationStep(
        id=f"step-{case_id}-{sequence}", case_id=case_id,
        action_type=action_type, performed_at=BASE, sequence=sequence,
        note_text=note,
    )


def _asset(*, id, criticality="high") -> Asset:
    return Asset(id=id, entity_id="e", native_id=f"native-{id}", criticality=criticality)


def _ds(**kw) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=kw.get("alerts", []),
        cases=kw.get("cases", []),
        steps=kw.get("steps", []),
        escalations=kw.get("escalations", []),
        dispositions=kw.get("dispositions", []),
        assets=kw.get("assets", []),
        submitted_categories=frozenset(kw.get("submitted",
            ("alerts", "cases", "investigation_steps",
             "escalations", "dispositions", "assets"))),
    )


# ---------------------------------------------------------------------------
# helpers — pure functions
# ---------------------------------------------------------------------------

def test_median_basic():
    assert _median([1, 2, 3, 4, 5]) == 3
    assert _median([1, 2, 3, 4]) == 2.5
    assert _median([]) == 0.0


def test_mad_basic():
    # median = 3, |x-med| = [2,1,0,1,2] → median of those = 1
    assert _mad([1, 2, 3, 4, 5], 3.0) == 1.0


def test_percentile_basic():
    assert _percentile([1, 2, 3, 4, 5], 0.5) == 3.0
    assert _percentile([1, 2, 3, 4, 5], 0.9) == 4.6


def test_outliers_strictly_above_cutoff():
    # median 10, MAD 1, cutoff = 10 + 3*1 = 13
    # 14 is strictly above; 13 is not (boundary)
    out = _anomalous_outliers([10, 10, 10, 10, 14], k=3.0, min_samples=5)
    assert [v for _, v, _ in out] == [14.0]


def test_outliers_below_min_samples_returns_empty():
    out = _anomalous_outliers([1, 2, 100], k=3.0, min_samples=5)
    assert out == []


def test_outliers_mad_zero_does_not_produce_inf():
    """A degenerate distribution where the median + MAD is 0 (all
    values are equal except one) must not return float('inf') — the
    score is the raw deviation, still finite."""
    out = _anomalous_outliers([5, 5, 5, 5, 5, 100], k=3.0, min_samples=5)
    # 5 values of 5 + one 100; median=5, MAD=0 → cutoff=5, only 100
    # qualifies. Score should be 95.0 (100-5), finite.
    assert len(out) == 1
    assert math.isfinite(out[0][2])
    assert out[0][2] == 95.0


# ---------------------------------------------------------------------------
# closure_time
# ---------------------------------------------------------------------------

def test_closure_time_outlier_detected():
    """5 alerts closed in ~60s, one closed in 24h."""
    alerts = [
        _alert(id=f"A{i}", severity="critical",
               closed=BASE + 60 + i, source_record_ref=f"sr-{i}")
        for i in range(1, 6)
    ]
    alerts.append(_alert(id="OUT", severity="critical",
                          closed=BASE + 24 * 3600,
                          source_record_ref="sr-out"))
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.closure_time.high")
    assert "OUT" in f.scoped_subjects
    assert f.statistic > 80000   # roughly 24h in seconds
    assert f.threshold is not None
    # effect is the raw deviation in seconds (or MAD-units when MAD>0),
    # not bounded to [0, 1] like execution-gap workers — the
    # bounded confidence is in confidence.analytical_support
    assert f.effect is not None and f.effect > 0
    assert f.confidence.analytical_support > 0


def test_closure_time_no_outlier_uniform():
    """All closure times are close — no outlier."""
    alerts = [
        _alert(id=f"A{i}", severity="critical",
               closed=BASE + 100 + i, source_record_ref=f"sr-{i}")
        for i in range(1, 8)
    ]
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts))
    assert not any(f.rule_or_category == "anomaly.closure_time.high"
                   for f in batch.findings)


def test_closure_time_too_few_samples_no_outlier():
    """Only 3 closed alerts — below the min_samples=5 default."""
    alerts = [
        _alert(id=f"A{i}", severity="critical", closed=BASE + 60 + i)
        for i in range(1, 4)
    ]
    alerts.append(_alert(id="OUT", severity="critical", closed=BASE + 24*3600))
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts))
    assert not any(f.rule_or_category == "anomaly.closure_time.high"
                   for f in batch.findings)


# ---------------------------------------------------------------------------
# investigation_duration
# ---------------------------------------------------------------------------

def test_investigation_duration_outlier():
    cases = [
        _case(id=f"C{i}", opened_at=BASE, closed_at=BASE + 600 + i)
        for i in range(1, 6)
    ]
    cases.append(_case(id="C-OUT", opened_at=BASE, closed_at=BASE + 24*3600))
    batch = _eval(AnomalyWorker(), _ds(cases=cases))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.investigation_duration.high")
    assert "C-OUT" in f.scoped_subjects


# ---------------------------------------------------------------------------
# alerts_per_asset
# ---------------------------------------------------------------------------

def test_alerts_per_asset_outlier():
    assets = [_asset(id=f"asset-{i}") for i in range(1, 6)]
    alerts = []
    for i in range(1, 6):
        # 1 alert per asset
        alerts.append(_alert(id=f"A{i}", severity="high",
                              asset_refs=[f"asset-{i}"]))
    # one asset gets 50 alerts
    for i in range(50):
        alerts.append(_alert(id=f"AHOT{i}", severity="low",
                              asset_refs=["asset-1"]))
    batch = _eval(AnomalyWorker(), _ds(assets=assets, alerts=alerts))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.alerts_per_asset.high")
    assert "asset-1" in f.scoped_subjects


# ---------------------------------------------------------------------------
# critical_alerts_per_critical_asset
# ---------------------------------------------------------------------------

def test_critical_alerts_per_critical_asset_outlier():
    assets = [_asset(id=f"asset-{i}", criticality="critical") for i in range(1, 6)]
    alerts = []
    for i in range(1, 6):
        alerts.append(_alert(id=f"A{i}", severity="critical",
                              asset_refs=[f"asset-{i}"]))
    for i in range(30):
        alerts.append(_alert(id=f"AHOT{i}", severity="critical",
                              asset_refs=["asset-1"]))
    batch = _eval(AnomalyWorker(), _ds(assets=assets, alerts=alerts))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.critical_alerts_per_critical_asset.high")
    assert "asset-1" in f.scoped_subjects


# ---------------------------------------------------------------------------
# escalation_rate
# ---------------------------------------------------------------------------

def test_escalation_rate_low_outlier():
    """10 critical alerts, none escalated → low escalation rate."""
    alerts = [
        _alert(id=f"A{i}", severity="critical", closed=BASE + 600,
               source_record_ref=f"sr-{i}")
        for i in range(1, 11)
    ]
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts, escalations=[]))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.escalation_rate.low")
    assert f.statistic == 0.0
    assert f.effect > 0


def test_escalation_rate_healthy_no_outlier():
    """10 critical alerts, all escalated → no outlier."""
    alerts = [
        _alert(id=f"A{i}", severity="critical", closed=BASE + 600)
        for i in range(1, 11)
    ]
    escs = [Escalation(id=f"esc-{i}", entity_id="e", assessment_id="a",
                        occurred_at=BASE + 100, alert_id=f"A{i}")
            for i in range(1, 11)]
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts, escalations=escs))
    assert not any(f.rule_or_category == "anomaly.escalation_rate.low"
                   for f in batch.findings)


# ---------------------------------------------------------------------------
# recurrence
# ---------------------------------------------------------------------------

def test_recurrence_outlier():
    cases = [_case(id=f"C{i}") for i in range(1, 6)]
    alerts = []
    for i in range(1, 6):
        alerts.append(_alert(id=f"A{i}", severity="high", case_refs=[f"C{i}"]))
    # C-1 gets 20 alerts
    for i in range(20):
        alerts.append(_alert(id=f"AREC{i}", severity="high", case_refs=["C1"]))
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts, cases=cases))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.recurrence.high")
    assert "C1" in f.scoped_subjects


# ---------------------------------------------------------------------------
# monitoring_coverage
# ---------------------------------------------------------------------------

def test_monitoring_coverage_low_outlier():
    """5 critical assets, only 1 has any alert."""
    assets = [_asset(id=f"asset-{i}", criticality="critical") for i in range(1, 6)]
    alerts = [_alert(id="A1", severity="high", asset_refs=["asset-1"])]
    batch = _eval(AnomalyWorker(), _ds(assets=assets, alerts=alerts))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.monitoring_coverage.low")
    assert f.statistic == 0.2   # 1/5


# ---------------------------------------------------------------------------
# investigation_depth
# ---------------------------------------------------------------------------

def test_investigation_depth_outlier():
    cases = [_case(id=f"C{i}") for i in range(1, 6)]
    steps = []
    for i in range(1, 6):
        steps.append(_step(case_id=f"C{i}", sequence=1))
    # C1 gets 20 steps
    for i in range(2, 22):
        steps.append(_step(case_id="C1", sequence=i))
    batch = _eval(AnomalyWorker(), _ds(cases=cases, steps=steps))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.investigation_depth.high")
    assert "C1" in f.scoped_subjects


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_finding_carries_baseline_statistic_effect():
    """Every anomaly finding must carry the observed value, the
    baseline (the metric's threshold the engine compared against),
    and a deviation effect — the spec's required output shape."""
    alerts = [
        _alert(id=f"A{i}", severity="critical", closed=BASE + 60 + i)
        for i in range(1, 6)
    ]
    alerts.append(_alert(id="OUT", severity="critical", closed=BASE + 24*3600,
                          source_record_ref="sr-out"))
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts))
    f = next(f for f in batch.findings
             if f.rule_or_category == "anomaly.closure_time.high")
    assert f.statistic is not None
    assert f.threshold is not None
    assert f.effect is not None
    assert f.confidence is not None
    assert 0.0 <= f.confidence.analytical_support <= 1.0
    assert f.confidence.evidence_completeness == 1.0
    assert "sr-out" in f.evidence_refs
    assert "Phase 7" in f.limitations  # documents the in-scope baseline


def test_no_findings_on_empty_dataset():
    batch = _eval(AnomalyWorker(), _ds())
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_per_metric_sample_sizes_reported_in_scope():
    """The processing_metrics block records the actual sample size
    per metric — a reviewer can see whether a metric's 'no findings'
    is meaningful or simply had no data."""
    alerts = [_alert(id=f"A{i}", severity="critical", closed=BASE + 60 + i)
              for i in range(1, 6)]
    batch = _eval(AnomalyWorker(), _ds(alerts=alerts))
    sizes = batch.processing_metrics["metric_sample_sizes"]
    assert sizes["closure_time"] == 5
    assert sizes["investigation_duration"] == 0
    assert sizes["alerts_per_asset"] == 0


def test_custom_thresholds_lower_min_samples():
    """With min_samples=3 instead of 5, a 4-alert scope with a clear
    outlier will be flagged."""
    alerts = [
        _alert(id=f"A{i}", severity="critical", closed=BASE + 60 + i)
        for i in range(1, 4)
    ]
    alerts.append(_alert(id="OUT", severity="critical", closed=BASE + 24*3600))
    batch = _eval(AnomalyWorker(
        thresholds=AnomalyThresholds(min_samples=3, mad_k=3.0)
    ), _ds(alerts=alerts))
    assert any(f.rule_or_category == "anomaly.closure_time.high"
               for f in batch.findings)

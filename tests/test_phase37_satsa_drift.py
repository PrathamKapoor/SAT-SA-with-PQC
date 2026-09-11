"""Phase 37 — supervisory drift tests."""
from __future__ import annotations

import pytest

from satsa.analysis.drift import (
    DRIFT_METRICS, DriftFinding, compute_drift,
)


def test_drift_emits_nothing_when_below_threshold():
    prev = {"critical_closure_rate": 0.9, "escalation_rate": 0.8}
    curr = {"critical_closure_rate": 0.91, "escalation_rate": 0.79}
    findings = compute_drift("e1", prev, curr, relative_threshold=0.2)
    assert findings == []


def test_drift_emits_finding_when_above_threshold():
    prev = {"critical_closure_rate": 0.5, "escalation_rate": 0.8}
    curr = {"critical_closure_rate": 0.9, "escalation_rate": 0.5}
    findings = compute_drift("e1", prev, curr, relative_threshold=0.2)
    assert len(findings) == 2
    by_metric = {f.metric: f for f in findings}
    assert by_metric["critical_closure_rate"].direction == "increased"
    assert by_metric["escalation_rate"].direction == "decreased"
    assert by_metric["critical_closure_rate"].delta == pytest.approx(0.4)


def test_drift_excludes_metrics_not_in_both_periods():
    prev = {"critical_closure_rate": 0.5, "escalation_rate": 0.8}
    curr = {"critical_closure_rate": 0.9}  # no escalation_rate
    findings = compute_drift("e1", prev, curr, relative_threshold=0.0)
    assert len(findings) == 1
    assert findings[0].metric == "critical_closure_rate"


def test_drift_handles_zero_previous():
    """When the previous value is 0 and the current is not,
    the relative delta is capped at 1.0 — a real change but not
    'infinite'."""
    findings = compute_drift("e1",
                             {"monitoring_coverage": 0.0},
                             {"monitoring_coverage": 0.5},
                             relative_threshold=0.2)
    assert len(findings) == 1
    assert findings[0].relative_delta == 1.0
    assert findings[0].direction == "increased"


def test_drift_returns_empty_when_no_data():
    assert compute_drift("e1", {}, {"a": 1.0}) == []
    assert compute_drift("e1", {"a": 1.0}, {}) == []
    assert compute_drift("e1", {}, {}) == []


def test_drift_includes_limitations_note():
    findings = compute_drift("e1",
                             {"critical_closure_rate": 0.5},
                             {"critical_closure_rate": 0.9},
                             relative_threshold=0.1)
    assert findings[0].limitations
    assert "two data points" in findings[0].limitations.lower()


def test_drift_finding_to_dict_is_serializable():
    import json
    f = DriftFinding(entity_id="e1", metric="m", previous=0.5, current=0.9,
                     delta=0.4, relative_delta=0.8, direction="increased",
                     limitations="test")
    json.dumps(f.to_dict())


def test_drift_metrics_constant_set():
    """The tracked metrics are a fixed, documented set — no
    ad-hoc metric names."""
    assert DRIFT_METRICS == (
        "critical_closure_rate",
        "critical_closure_median_seconds",
        "escalation_rate",
        "investigation_depth_median",
        "recurrence_median",
        "monitoring_coverage",
    )


def test_drift_only_emits_known_metrics():
    """If a previous metric is not in the known set, it is
    ignored — we never invent drift findings for unknown metrics."""
    findings = compute_drift("e1",
                             {"critical_closure_rate": 0.5,
                              "unknown_metric": 0.9},
                             {"critical_closure_rate": 0.9,
                              "unknown_metric": 0.1},
                             relative_threshold=0.0)
    metrics = {f.metric for f in findings}
    assert "unknown_metric" not in metrics
    assert "critical_closure_rate" in metrics

"""Phase 33 — explicit recommendation engine tests."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from satsa.analysis.recommend import (
    RECOMMEND_CHECK_ESCALATION_PATH,
    RECOMMEND_COMPARE_WITH_PEERS,
    RECOMMEND_INSPECT_INVESTIGATION,
    RECOMMEND_INSPECT_ROOT_CAUSE,
    RECOMMEND_VERIFY_MONITORING,
    recommend,
)


def _fake_finding(rule, fid="f-1", refs=("sr1", "sr2")):
    return SimpleNamespace(id=fid, rule_or_category=rule, evidence_refs=list(refs))


def test_recommend_fast_closure():
    f = _fake_finding("execution_gap.fast_closure")
    r = recommend(f)
    assert r.action == RECOMMEND_INSPECT_INVESTIGATION
    assert r.finding_id == "f-1"
    assert r.evidence_refs == ["sr1", "sr2"]


def test_recommend_critical_without_escalation():
    r = recommend(_fake_finding("execution_gap.critical_without_escalation"))
    assert r.action == RECOMMEND_CHECK_ESCALATION_PATH


def test_recommend_metric_gaming():
    r = recommend(_fake_finding("execution_gap.potential_metric_gaming"))
    assert r.action == RECOMMEND_INSPECT_ROOT_CAUSE


def test_recommend_repeated_pattern():
    r = recommend(_fake_finding("execution_gap.repeated_investigation_pattern"))
    assert r.action == RECOMMEND_INSPECT_ROOT_CAUSE


def test_recommend_recurring_without_remediation():
    r = recommend(_fake_finding("execution_gap.recurring_without_remediation"))
    assert r.action == RECOMMEND_INSPECT_ROOT_CAUSE


def test_recommend_missing_monitoring():
    r = recommend(_fake_finding("negative_space.missing_monitoring"))
    assert r.action == RECOMMEND_VERIFY_MONITORING


def test_recommend_missing_escalation():
    r = recommend(_fake_finding("negative_space.missing_escalation"))
    assert r.action == RECOMMEND_CHECK_ESCALATION_PATH


def test_recommend_missing_investigation():
    r = recommend(_fake_finding("negative_space.missing_investigation"))
    assert r.action == RECOMMEND_INSPECT_INVESTIGATION


def test_recommend_missing_file():
    r = recommend(_fake_finding("negative_space.missing_file.alerts"))
    assert r.action == "REQUEST_MISSING_EVIDENCE"


def test_recommend_peer_benchmark():
    r = recommend(_fake_finding("peer_benchmark.escalation_rate.deviation"))
    assert r.action == RECOMMEND_COMPARE_WITH_PEERS


def test_recommend_anomaly():
    r = recommend(_fake_finding("anomaly.closure_time.high"))
    assert r.action == RECOMMEND_COMPARE_WITH_PEERS


def test_recommend_unknown_rule_falls_back_to_generic_review():
    r = recommend(_fake_finding("unknown.rule.family"))
    assert r.action == "REVIEW"
    assert r.finding_id == "f-1"


def test_recommend_includes_evidence_refs():
    f = _fake_finding("execution_gap.fast_closure", refs=("sr-A", "sr-B", "sr-C"))
    r = recommend(f)
    assert r.evidence_refs == ["sr-A", "sr-B", "sr-C"]


def test_recommend_includes_limitations():
    f = _fake_finding("execution_gap.fast_closure")
    r = recommend(f)
    assert "Recommendation is a hint" in r.limitations
    assert "examiner remains responsible" in r.limitations


def test_recommend_to_dict_is_serializable():
    import json
    f = _fake_finding("execution_gap.fast_closure", refs=("sr1",))
    r = recommend(f)
    d = r.to_dict()
    # Should be JSON-serializable
    json.dumps(d)
    assert d["action"] == RECOMMEND_INSPECT_INVESTIGATION
    assert d["finding_id"] == "f-1"
    assert d["evidence_refs"] == ["sr1"]


def test_recommend_handles_finding_dict():
    """The recommender must work with both dataclass-like objects and
    plain dicts (since the test fixtures may use either)."""
    f = {"id": "f-2", "rule_or_category": "execution_gap.fast_closure",
         "evidence_refs": ["sr-A"]}
    r = recommend(f)
    assert r.action == RECOMMEND_INSPECT_INVESTIGATION
    assert r.finding_id == "f-2"

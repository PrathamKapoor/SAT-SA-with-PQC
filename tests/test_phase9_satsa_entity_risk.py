"""Phase 9 (SAT-SA) — entity risk engine tests.

The risk engine aggregates a run's findings into a per-entity
profile: per-dimension scores, a total (capped at 100), a
confidence bucket, and a tree-shaped decomposition. Tests cover
*every* weight case, the cap behaviour, the no-findings case, the
confidence bucketing, the documented rationale, and the
end-to-end computation from a real AnalysisRun.
"""
from __future__ import annotations

import json

import pytest

from satsa.analysis.risk import (
    DIMENSION_WEIGHTS,
    TOTAL_WEIGHT,
    _confidence_bucket,
    _confidence_overall,
    _dimension_for,
    compute_entity_risk,
)
from satsa.analysis.run import RunService
from satsa.domain.entities import Submission
from satsa.domain.workflow import Alert
from satsa.store.repositories import AlertStore, SubmissionStore


BASE = 1735689600.0


@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner

    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


@pytest.fixture()
def service(engine):
    from satsa.service import SatsaService
    return SatsaService(engine)


def _open_scope(service, name):
    entity = service.register_entity(name, sector="defence",
                                       environment_class="on-prem")
    a = service.open_assessment(entity.id, BASE, BASE + 30 * 86400)
    return entity, a


def _ingest_alerts(service, engine, entity, assessment, rows, sub_id=None):
    import time
    sub_id = sub_id or f"sub-{entity.id}"
    SubmissionStore(engine).insert(
        Submission(id=sub_id, assessment_id=assessment.id, source_system="unit",
                   declared_period_start=BASE, declared_period_end=BASE + 30 * 86400,
                   file_digests={"x": "d"}, declared_counts={"alerts": len(rows)},
                   received_at=time.time(), signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest=f"snap-{entity.id}", created_at=time.time())
    for r in rows:
        a = Alert(entity_id=entity.id, assessment_id=assessment.id,
                  native_id=r["native_id"], created_at=r["created"],
                  mapped_severity=r["severity"],
                  acknowledged_at=r.get("ack"),
                  closed_at=r.get("closed"),
                  source_record_ref=f"sr-{r['native_id']}")
        AlertStore(engine).insert(a, submission_id=sub_id)


# ---------------------------------------------------------------------------
# pure-function tests
# ---------------------------------------------------------------------------

def test_dimension_weights_sum_to_100():
    assert TOTAL_WEIGHT == 100
    assert sum(DIMENSION_WEIGHTS.values()) == 100


def test_dimension_for_known_rule_prefixes():
    assert _dimension_for("execution_gap.fast_closure") == "execution_gap"
    assert _dimension_for("execution_gap.ack_without_investigation") == "execution_gap"
    assert _dimension_for("peer_benchmark.critical_closure_median_seconds.deviation") == "peer_deviation"
    assert _dimension_for("negative_space.missing_escalation") == "negative_space"
    assert _dimension_for("negative_space.missing_file.alerts") == "negative_space"
    assert _dimension_for("anomaly.closure_time.high") == "anomaly"
    assert _dimension_for("detection_gap.foo") == "detection_gap"
    assert _dimension_for("monitoring.bar") == "detection_gap"
    assert _dimension_for("escalation.baz") == "escalation_discipline"
    assert _dimension_for("investigation.qux") == "investigation_quality"
    assert _dimension_for("metric_gaming.x") == "investigation_quality"
    assert _dimension_for("recurrence.x") == "investigation_quality"
    assert _dimension_for("unknown.rule") == "anomaly"  # catch-all


def test_confidence_overall_uses_overall_field():
    f = {"confidence_json": json.dumps({"overall": 0.7, "analytical_support": 0.9})}
    assert _confidence_overall(f) == 0.7


def test_confidence_overall_handles_missing_field():
    f = {"confidence_json": json.dumps({"analytical_support": 0.9})}
    # when 'overall' is missing, fall back to 0.5
    assert _confidence_overall(f) == 0.5


def test_confidence_overall_handles_no_confidence():
    assert _confidence_overall({}) == 0.5
    assert _confidence_overall({"confidence_json": "not json"}) == 0.5


def test_confidence_buckets():
    assert _confidence_bucket(0.0) == "very_low"
    assert _confidence_bucket(0.2) == "very_low"
    assert _confidence_bucket(0.3) == "low"
    assert _confidence_bucket(0.49) == "low"
    assert _confidence_bucket(0.5) == "medium"  # boundary inclusive
    assert _confidence_bucket(0.6) == "medium"
    assert _confidence_bucket(0.75) == "high"  # boundary inclusive
    assert _confidence_bucket(0.9) == "high"


# ---------------------------------------------------------------------------
# integration tests through a real run
# ---------------------------------------------------------------------------

def test_risk_profile_no_runs_returns_zero(service):
    entity, _ = _open_scope(service, "CSE-EMPTY")
    profile = service.compute_risk(entity.id)
    assert profile.total_score == 0.0
    assert profile.confidence_bucket == "very_low"
    assert profile.run_id is None
    assert profile.dimensions == []


def test_risk_profile_aggregates_execution_gap_findings(service, engine):
    """A scope that produces only execution-gap findings should put
    all the score into the execution_gap dimension (weight 25)."""
    entity, a = _open_scope(service, "CSE-FAST")
    # One fast-closing critical alert → fast-closure (execution_gap)
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    # dimensions present
    by_name = {d.name: d for d in profile.dimensions}
    assert "execution_gap" in by_name
    assert by_name["execution_gap"].score > 0
    assert by_name["execution_gap"].weight == 25
    # every other dimension is 0
    for d in profile.dimensions:
        if d.name != "execution_gap":
            assert d.score == 0.0


def test_risk_profile_includes_peer_deviation_dimension(service, engine):
    """Build 4 peers and 1 subject. The subject's peer_deviation
    findings should produce a non-zero peer_deviation dimension."""
    for i, t in enumerate([300, 600, 900, 1200]):
        e, a = _open_scope(service, f"PEER-{i+1}")
        _ingest_alerts(service, engine, e, a, [{
            "native_id": f"P{i}-1", "created": BASE, "severity": "critical",
            "ack": BASE + 60, "closed": BASE + t,
        }])
    e_sub, a_sub = _open_scope(service, "SUBJECT")
    _ingest_alerts(service, engine, e_sub, a_sub, [{
        "native_id": "S1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 30,
    }])
    RunService(engine).run(e_sub.id, a_sub.id)
    profile = service.compute_risk(e_sub.id)
    by_name = {d.name: d for d in profile.dimensions}
    assert "peer_deviation" in by_name
    assert by_name["peer_deviation"].score > 0


def test_risk_profile_total_capped_at_100(service, engine):
    """Even with many findings the total cannot exceed 100."""
    entity, a = _open_scope(service, "CSE-MAX")
    rows = [
        {"native_id": f"A{i}", "created": BASE + i, "severity": "critical",
         "ack": BASE + 60, "closed": BASE + 30}    # all fast-closed
        for i in range(1, 11)
    ]
    _ingest_alerts(service, engine, entity, a, rows)
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    assert 0 <= profile.total_score <= 100


def test_risk_profile_decomposition_is_tree_shaped(service, engine):
    """decomposition() returns total → dimensions → finding_ids."""
    entity, a = _open_scope(service, "CSE-DECOMP")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    dec = profile.decomposition()
    assert "total" in dec
    assert "dimensions" in dec
    assert "execution_gap" in dec["dimensions"]
    assert "finding_ids" in dec["dimensions"]["execution_gap"]


def test_risk_profile_each_dimension_links_to_findings(service, engine):
    entity, a = _open_scope(service, "CSE-LINKS")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    exec_dim = next(d for d in profile.dimensions if d.name == "execution_gap")
    assert exec_dim.finding_ids, "execution_gap dimension must link to findings"
    # every linked finding is a real row
    rows = engine.query_all(
        "SELECT id, rule_or_category FROM satsa_findings WHERE id IN ({})".format(
            ",".join("?" * len(exec_dim.finding_ids))),
        exec_dim.finding_ids)
    assert len(rows) == len(exec_dim.finding_ids)
    for r in rows:
        assert r["rule_or_category"].startswith("execution_gap.")


def test_risk_profile_uses_specific_run_id(service, engine):
    entity, a = _open_scope(service, "CSE-RUNID")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    r1 = RunService(engine).run(entity.id, a.id)
    profile1 = service.compute_risk(entity.id, run_id=r1.run_id)
    assert profile1.run_id == r1.run_id
    assert profile1.total_score > 0


def test_risk_profile_does_not_invent_weights(service, engine):
    """The persisted profile carries the weights it was computed
    with; no hidden multipliers."""
    entity, a = _open_scope(service, "CSE-WEIGHTS")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    assert profile.weights == DIMENSION_WEIGHTS
    # every dimension listed has its documented weight
    for d in profile.dimensions:
        assert d.weight == DIMENSION_WEIGHTS[d.name]


def test_risk_profile_rationale_per_dimension(service, engine):
    entity, a = _open_scope(service, "CSE-RAT")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    for d in profile.dimensions:
        assert d.rationale, f"dimension {d.name} has no rationale"
        # dimensions with no findings get an explicit "no findings"
        if not d.finding_ids:
            assert "no findings" in d.rationale.lower()


def test_risk_profile_confidence_bucket_for_real_run(service, engine):
    entity, a = _open_scope(service, "CSE-CONF")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    assert profile.confidence_bucket in {"very_low", "low", "medium", "high"}

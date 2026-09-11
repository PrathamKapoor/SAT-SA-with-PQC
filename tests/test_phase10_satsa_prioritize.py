"""Phase 10 (SAT-SA) — review prioritization tests.

Prioritization turns Phase 9's risk profile + confidence + recency
+ signal severity into two ranked lists:

* ``prioritize_entities`` — across the whole deployment, which
  entity is most worth looking at first?
* ``prioritize_findings`` — within a single run, which signal
  finding is most worth looking at first?

Every priority entry has an *evidence-backed* rationale that
quotes real numbers (risk, confidence, top dimensions) — no
fabricated reasons.
"""
from __future__ import annotations

import time

import pytest

from satsa.analysis.prioritize import (
    _severity_of,
    prioritize_entities,
    prioritize_findings,
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
# severity bucketing
# ---------------------------------------------------------------------------

def test_severity_of_execution_gap_is_medium():
    assert _severity_of("execution_gap.fast_closure") == "medium"
    assert _severity_of("execution_gap.critical_without_escalation") == "medium"


def test_severity_of_peer_benchmark_is_high():
    assert _severity_of("peer_benchmark.critical_closure_median_seconds.deviation") == "high"
    assert _severity_of("execution_gap.potential_metric_gaming") == "high"


def test_severity_of_negative_space_is_low():
    assert _severity_of("negative_space.missing_file.alerts") == "low"
    assert _severity_of("negative_space.missing_escalation") == "low"


def test_severity_of_anomaly_is_medium():
    assert _severity_of("anomaly.closure_time.high") == "medium"


# ---------------------------------------------------------------------------
# entity prioritization
# ---------------------------------------------------------------------------

def test_prioritize_entities_empty_when_no_runs(service):
    assert service.prioritize_entities() == []


def test_prioritize_entities_returns_ranked_list(service, engine):
    """Two entities, one with findings and one without → the one
    with findings ranks first."""
    e_quiet, a_quiet = _open_scope(service, "CSE-QUIET")
    _ingest_alerts(service, engine, e_quiet, a_quiet, [{
        "native_id": "A1", "created": BASE, "severity": "low",
        "ack": BASE + 60, "closed": BASE + 24*3600,
    }])
    RunService(engine).run(e_quiet.id, a_quiet.id)

    e_hot, a_hot = _open_scope(service, "CSE-HOT")
    _ingest_alerts(service, engine, e_hot, a_hot, [{
        "native_id": "B1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,   # fast close → signal
    }])
    RunService(engine).run(e_hot.id, a_hot.id)

    ranking = service.prioritize_entities()
    assert len(ranking) == 2
    # the entity with the fast-closure signal ranks first
    assert ranking[0].entity_id == e_hot.id
    assert ranking[0].risk_score > ranking[1].risk_score


def test_prioritize_entities_includes_evidence_backed_rationale(service, engine):
    e, a = _open_scope(service, "CSE-RATIONALE")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(e.id, a.id)
    ranking = service.prioritize_entities()
    p = ranking[0]
    # rationale must contain real numbers and the top dimensions
    assert "risk" in p.rationale
    assert "confidence" in p.rationale
    # at least one dimension name appears
    assert any(d in p.rationale for d in p.top_dimensions)


def test_prioritize_entities_records_high_signal_count(service, engine):
    """A peer-deviation finding should bump the priority's
    high_signal_count and pull the entity up the ranking."""
    # 4 peers
    for i, t in enumerate([300, 600, 900, 1200]):
        e, a = _open_scope(service, f"PEER-{i+1}")
        _ingest_alerts(service, engine, e, a, [{
            "native_id": f"P{i}-1", "created": BASE, "severity": "critical",
            "ack": BASE + 60, "closed": BASE + t,
        }])
    # subject
    e, a = _open_scope(service, "SUBJECT")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "S1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 30,
    }])
    RunService(engine).run(e.id, a.id)
    p = next(p for p in service.prioritize_entities() if p.entity_id == e.id)
    assert p.high_signal_count >= 1   # at least one peer-deviation


# ---------------------------------------------------------------------------
# finding prioritization
# ---------------------------------------------------------------------------

def test_prioritize_findings_empty_for_unknown_run(service):
    assert service.prioritize_findings("run-unknown") == []


def test_prioritize_findings_runs_only_includes_signals(service, engine):
    e, a = _open_scope(service, "CSE-PF")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    prio = service.prioritize_findings(result.run_id)
    assert prio
    # every entry is a 'signal' (non-signal findings are not returned)
    assert all(p.state == "signal" for p in prio)


def test_prioritize_findings_returns_evidence_backed_rationale(service, engine):
    e, a = _open_scope(service, "CSE-PF2")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    prio = service.prioritize_findings(result.run_id)
    p = prio[0]
    # the rationale quotes the dimension + the original finding's rationale
    assert p.rationale
    assert "(" in p.rationale and "severity" in p.rationale


def test_prioritize_findings_orders_higher_severity_first(service, engine):
    """A scope with both a peer-deviation (high) and a negative-space
    (low) signal puts the peer-deviation first."""
    # 4 peers to give the subject a peer_deviation
    for i, t in enumerate([300, 600, 900, 1200]):
        ep, ap = _open_scope(service, f"PR-{i+1}")
        _ingest_alerts(service, engine, ep, ap, [{
            "native_id": f"P{i}-1", "created": BASE, "severity": "critical",
            "ack": BASE + 60, "closed": BASE + t,
        }])
    e, a = _open_scope(service, "SUBJECT2")
    # ingest only the alerts file (no cases / steps) → triggers
    # negative_space.missing_file.* and peer-deviation
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "S1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 30,
    }])
    result = RunService(engine).run(e.id, a.id)
    prio = service.prioritize_findings(result.run_id)
    # at least one high-severity (peer_benchmark) finding exists
    assert any(p.severity == "high" for p in prio)
    # and the first finding is the high-severity one
    assert prio[0].severity == "high"


def test_prioritize_findings_to_dict_roundtrip(service, engine):
    e, a = _open_scope(service, "CSE-PF3")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    prio = service.prioritize_findings(result.run_id)
    d = prio[0].to_dict()
    assert d["finding_id"]
    assert d["rule_or_category"]
    assert d["priority_score"] >= 0
    assert d["state"] == "signal"

"""Phase 12 (SAT-SA) — human review workflow tests.

The review service records an authenticated examiner's
confirm / dismiss / escalate / annotate / request_review action
on a finding, with a full audit trail. Tests cover:

* domain validation (action must be one of the five),
* recording against a real finding (with its live content_digest),
* decision chain (corrections reference previous_revision_id),
* audit query (chronological, complete),
* integrity: the captured finding_content_digest is exactly the
  live digest at decision time (a later tamper of the finding
  makes the digest mismatch visible to a verifier).
"""
from __future__ import annotations

import time

import pytest

from satsa.analysis.review import ReviewService
from satsa.analysis.run import RunService
from satsa.domain.evidence import REVIEW_ACTIONS
from satsa.domain.entities import Submission
from satsa.domain.workflow import Alert
from satsa.store.repositories import (
    AlertStore, SubmissionStore,
)


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
# 1. domain validation
# ---------------------------------------------------------------------------

def test_record_rejects_unknown_action(service, engine):
    e, a = _open_scope(service, "CSE-REV")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    with pytest.raises(ValueError, match="invalid review decision"):
        service.record_review(
            finding_id=fid, principal_identity_id="identity-1",
            action="not-a-real-action", finding_content_digest="x" * 64,
        )


def test_record_accepts_every_documented_action(service, engine):
    """Every action in REVIEW_ACTIONS is valid."""
    e, a = _open_scope(service, "CSE-ALL-ACTIONS")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    for action in REVIEW_ACTIONS:
        # each decision references the previous one
        prev = None
        history = service.review_history(fid)
        if history:
            prev = history[-1].id
        service.record_review(
            finding_id=fid, principal_identity_id="identity-1",
            action=action, reason=f"test {action}",
            finding_content_digest="x" * 64,
            previous_revision_id=prev,
        )
    # every action was recorded
    hist = service.review_history(fid)
    assert [h.action for h in hist] == list(REVIEW_ACTIONS)


# ---------------------------------------------------------------------------
# 2. recording against a real finding
# ---------------------------------------------------------------------------

def test_record_persists_into_table(service, engine):
    e, a = _open_scope(service, "CSE-PERSIST")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    entry = service.record_review(
        finding_id=fid, principal_identity_id="identity-007",
        action="confirm", reason="reviewed and validated",
        finding_content_digest="abc" * 20,
    )
    rows = engine.query_all(
        "SELECT * FROM satsa_review_decisions WHERE id=?", (entry.id,))
    assert len(rows) == 1
    assert rows[0]["principal_identity_id"] == "identity-007"
    assert rows[0]["action"] == "confirm"
    assert rows[0]["reason"] == "reviewed and validated"


def test_record_captures_finding_content_digest(service, engine):
    e, a = _open_scope(service, "CSE-DIGEST")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    # the live digest of the finding
    from satsa.analysis.run import RunService as _RS
    finding_row = engine.query_one(
        "SELECT * FROM satsa_findings WHERE id=?", (fid,))
    live = _RS._live_digest_for_finding(finding_row)
    entry = service.record_review(
        finding_id=fid, principal_identity_id="identity-1",
        action="escalate", reason="need second-pair-of-eyes",
        finding_content_digest=live,
    )
    assert entry.finding_content_digest == live


def test_record_chain_via_previous_revision_id(service, engine):
    """A correction is a new decision referencing the previous one."""
    e, a = _open_scope(service, "CSE-CHAIN")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    e1 = service.record_review(
        finding_id=fid, principal_identity_id="alice",
        action="dismiss", reason="false positive",
        finding_content_digest="d1")
    e2 = service.record_review(
        finding_id=fid, principal_identity_id="bob",
        action="confirm", reason="I disagree with alice",
        finding_content_digest="d1",
        previous_revision_id=e1.id)
    assert e2.previous_revision_id == e1.id


# ---------------------------------------------------------------------------
# 3. audit query
# ---------------------------------------------------------------------------

def test_history_returns_chronological_decisions(service, engine):
    e, a = _open_scope(service, "CSE-HIST")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    for i, action in enumerate(("annotate", "escalate", "confirm")):
        service.record_review(
            finding_id=fid, principal_identity_id=f"identity-{i}",
            action=action, reason=f"step {i}",
            finding_content_digest="d",
            occurred_at=BASE + i)
    hist = service.review_history(fid)
    assert [h.action for h in hist] == ["annotate", "escalate", "confirm"]


def test_history_empty_for_unreviewed_finding(service, engine):
    e, a = _open_scope(service, "CSE-EMPTY")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    assert service.review_history(fid) == []


# ---------------------------------------------------------------------------
# 4. integrity (decision bound to a specific finding version)
# ---------------------------------------------------------------------------

def test_decision_digest_does_not_match_after_finding_tamper(service, engine):
    """A later tampering of the finding makes the decision's
    captured digest no longer match the live one — a verifier can
    see the audit row was made on a different version of the
    record than what exists now."""
    e, a = _open_scope(service, "CSE-INTEG")
    _ingest_alerts(service, engine, e, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    result = RunService(engine).run(e.id, a.id)
    fid = result.finding_ids[0]
    from satsa.analysis.run import RunService as _RS
    finding_row = engine.query_one(
        "SELECT * FROM satsa_findings WHERE id=?", (fid,))
    live_at_decision = _RS._live_digest_for_finding(finding_row)
    entry = service.record_review(
        finding_id=fid, principal_identity_id="alice",
        action="confirm", reason="ok",
        finding_content_digest=live_at_decision,
    )
    # tamper: change the rationale
    engine.execute(
        "UPDATE satsa_findings SET rationale=? WHERE id=?",
        ("tampered", fid))
    # the decision's captured digest is unchanged; the live one
    # is now different
    new_live = _RS._live_digest_for_finding(
        engine.query_one("SELECT * FROM satsa_findings WHERE id=?", (fid,)))
    assert entry.finding_content_digest != new_live
    # an auditor comparing the two sees the mismatch
    audit = service.review_history(fid)[0]
    assert audit.finding_content_digest == live_at_decision
    assert audit.finding_content_digest != new_live

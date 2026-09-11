"""Phase 35 — human review aggregate statistics tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.service import SatsaService
from satsa.analysis.run import RunService
from satsa.domain.entities import Submission
from satsa.domain.workflow import Alert
from satsa.store.repositories import AlertStore, SubmissionStore
from satsa.analysis.review import ReviewService


BASE = 1735689600.0
END = 1738281600.0


def _seed(engine, n_alerts=3):
    svc = SatsaService(engine)
    e = svc.register_entity("CSE-AGG", sector="defence",
                             environment_class="on-prem")
    a = svc.open_assessment(e.id, BASE, END)
    sub = SubmissionStore(engine)
    sub.insert(Submission(id="s1", assessment_id=a.id, source_system="t",
                          declared_period_start=BASE, declared_period_end=END,
                          file_digests={}, declared_counts={},
                          received_at=BASE, signature_status="unsigned"),
                entity_id=e.id, ingest_status="accepted", ingest_report={},
                snapshot_digest="snap", created_at=BASE)
    for i in range(n_alerts):
        AlertStore(engine).insert(
            Alert(entity_id=e.id, assessment_id=a.id,
                  native_id=f"a-{i}", created_at=BASE,
                  mapped_severity="critical", acknowledged_at=BASE + 60,
                  closed_at=BASE + 100,  # very fast closure → signal
                  source_record_ref=f"sr-{i}"),
            submission_id="s1")
    RunService(engine).run(e.id, a.id)
    return svc, e


def test_aggregate_stats_empty():
    td = Path(tempfile.mkdtemp())
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        stats = ReviewService(eng).aggregate_stats()
        assert stats["total"] == 0
        assert stats["by_action"] == {}
        assert stats["by_actor"] == {}
        assert stats["distinct_findings_reviewed"] == 0
        eng.close()
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_aggregate_stats_counts_per_action():
    td = Path(tempfile.mkdtemp())
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        svc, e = _seed(eng)
        # get signal findings
        rows = eng.query_all(
            "SELECT id FROM satsa_findings WHERE state='signal'")
        assert rows, "no signal findings produced"
        fids = [r["id"] for r in rows]
        # record different actions
        svc.record_review(finding_id=fids[0], principal_identity_id="alice",
                          action="confirm", reason="ok",
                          finding_content_digest="x" * 64)
        svc.record_review(finding_id=fids[0], principal_identity_id="bob",
                          action="confirm", reason="agreed",
                          finding_content_digest="x" * 64)
        svc.record_review(finding_id=fids[1], principal_identity_id="alice",
                          action="dismiss", reason="fp",
                          finding_content_digest="x" * 64)
        svc.record_review(finding_id=fids[2], principal_identity_id="carol",
                          action="escalate", reason="needs review",
                          finding_content_digest="x" * 64)
        stats = ReviewService(eng).aggregate_stats()
        assert stats["total"] == 4
        assert stats["by_action"]["confirm"] == 2
        assert stats["by_action"]["dismiss"] == 1
        assert stats["by_action"]["escalate"] == 1
        assert stats["by_actor"]["alice"] == 2
        assert stats["by_actor"]["bob"] == 1
        assert stats["by_actor"]["carol"] == 1
        assert stats["distinct_findings_reviewed"] == 3
        eng.close()
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_aggregate_stats_does_not_invent_accuracy():
    """The spec says: 'Do not call these "model accuracy" unless
    the review semantics actually support that conclusion.' Verify
    the aggregate_stats does NOT include any accuracy / precision
    / recall field."""
    td = Path(tempfile.mkdtemp())
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        stats = ReviewService(eng).aggregate_stats()
        for k in stats:
            assert "accuracy" not in k.lower()
            assert "precision" not in k.lower()
            assert "recall" not in k.lower()
        eng.close()
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)

"""Phase P25 (agent expansion) — Supervisory Audit & Compliance
(Meta-Audit) Agent (N14).

A database-wide sweep, distinct from the single-run
``RunService.verify_run``: every run, every signal finding, every
review-decision binding currently persisted gets checked, not just
one run's worth. Reuses ``TrustService.verify_subject`` and
``ReviewService.verify_binding`` directly — no new verification
logic, only the exhaustive sweep over them.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def _setup():
    td = Path(tempfile.mkdtemp())
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(td / "x.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    return eng, td


def _seeded_run(eng, td):
    from satsa.service import SatsaService
    from satsa.analysis.run import RunService
    from satsa.domain.entities import Submission
    from satsa.domain.workflow import Alert
    from satsa.store.repositories import AlertStore, SubmissionStore

    svc = SatsaService(eng)
    e = svc.register_entity("CSE-AUDIT", sector="defence", environment_class="on-prem")
    a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
    sub_id = "sub-1"
    SubmissionStore(eng).insert(Submission(
        id=sub_id, assessment_id=a.id, source_system="t",
        declared_period_start=1735689600.0, declared_period_end=1738281600.0,
        file_digests={}, declared_counts={},
        received_at=1735689600.0, signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap", created_at=1735689600.0)
    AlertStore(eng).insert(Alert(
        entity_id=e.id, assessment_id=a.id, native_id="a1",
        created_at=1735689600.0, mapped_severity="medium",
        acknowledged_at=1735689600.0 + 60, closed_at=1735689600.0 + 600,
        source_record_ref="sr-1"), submission_id=sub_id)
    key_dir = td / "keys"
    result = RunService(eng).run(e.id, a.id, trust_key_dir=key_dir)
    return svc, e.id, result, key_dir


def test_clean_database_is_fully_compliant():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        from satsa.analysis.meta_audit import run_meta_audit
        report = run_meta_audit(eng, key_dir)
        assert report.fully_compliant is True
        assert report.runs_checked >= 1
        assert report.findings_checked >= 1
        assert report.runs_failed == []
        assert report.findings_failed == []
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_is_caught_by_the_sweep():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        fid = result.finding_ids[0]
        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            ("TAMPERED", fid))
        from satsa.analysis.meta_audit import run_meta_audit
        report = run_meta_audit(eng, key_dir)
        assert report.fully_compliant is False
        assert any(f["finding_id"] == fid for f in report.findings_failed)
        assert report.finding_coverage is not None
        assert report.finding_coverage < 1.0
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_review_decision_binding_is_swept():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        fid = result.finding_ids[0]
        f_row = eng.query_one("SELECT * FROM satsa_findings WHERE id=?", (fid,))
        from satsa.analysis.run import RunService
        live = RunService._live_digest_for_finding(dict(f_row))
        svc.record_review(
            finding_id=fid, principal_identity_id="examiner-1",
            action="confirm", reason="ok", finding_content_digest=live,
            trust_key_dir=key_dir)

        from satsa.analysis.meta_audit import run_meta_audit
        report = run_meta_audit(eng, key_dir)
        assert report.reviews_checked == 1
        assert report.reviews_ok == 1
        assert report.review_coverage == pytest.approx(1.0)
        assert report.ledger_integrity["fully_consistent"] is True
        assert report.fully_compliant is True

        # Tamper the finding AFTER the review — the binding must fail.
        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            ("TAMPERED-POST-REVIEW", fid))
        report2 = run_meta_audit(eng, key_dir)
        assert report2.reviews_ok == 0
        assert len(report2.reviews_failed) == 1
        assert report2.fully_compliant is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_empty_database_has_nothing_to_check_and_is_compliant():
    eng, td = _setup()
    try:
        from satsa.analysis.meta_audit import run_meta_audit
        report = run_meta_audit(eng, td / "keys")
        assert report.findings_checked == 0
        assert report.finding_coverage is None
        assert report.ledger_integrity["fully_consistent"] is True
        assert report.fully_compliant is True
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_agent_is_registered_in_the_roster():
    from satsa.supervisor import list_agents
    ids = {a.agent_id for a in list_agents()}
    assert "satsa.meta_audit" in ids
    assert "satsa.report_generation" in ids


def test_cli_audit_command_reports_compliant_exit_code(tmp_path):
    from satsa import cli as satsa_cli
    import io
    import contextlib

    db = tmp_path / "x.db"
    keys = tmp_path / "keys"
    rc = satsa_cli.main(["--db", str(db), "--trust-key-dir", str(keys), "demo"])
    assert rc == 0

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = satsa_cli.main(["--db", str(db), "--trust-key-dir", str(keys), "audit"])
    out = buf.getvalue()
    assert rc == 0
    assert '"fully_compliant": true' in out

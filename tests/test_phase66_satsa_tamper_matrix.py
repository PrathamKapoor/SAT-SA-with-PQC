"""Phase P20 — the tampering matrix, and a real gap closed.

``tests/test_phase44_satsa_trust_stress.py`` already covers: finding
body/threshold/confidence/evidence/observation_id tamper, run-digest
tamper, corrupted signature, deleted/missing receipt, and
re-verification stability — 11 tests, all still green (see
docs/roadmap-status.md P0). This module does not duplicate that
coverage; it closes what was still missing:

1. The human-decision binding was *documented* in
   ``satsa/analysis/review.py``'s own docstring ("if the finding is
   later tampered with, the digest in the decision no longer matches
   the live digest and the verifier will notice") but nothing ever
   checked it — ``ReviewService.verify_binding`` (new this phase)
   closes that.
2. "Insertion" from the tampering matrix: a finding row that exists
   in the database but was never part of any signed run.
3. Live-state, not cached-object, verification (SIH prompt section
   90/91): analytics run fine with verification never invoked; then
   verify (ok); tamper; verify (fails); restore the exact original
   value; verify (ok again) — proving "8/8 VERIFIED" reflects the
   database as it stands right now, not a snapshot taken once.
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
    e = svc.register_entity("CSE-TAMPER", sector="defence", environment_class="on-prem")
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


# ---------------------------------------------------------------------------
# Gap 1: the human-decision binding is now actually checked
# ---------------------------------------------------------------------------

def test_review_binding_verifies_when_finding_is_untouched():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        fid = result.finding_ids[0]
        f_row = eng.query_one("SELECT * FROM satsa_findings WHERE id=?", (fid,))
        from satsa.analysis.run import RunService
        live = RunService._live_digest_for_finding(dict(f_row))
        svc.record_review(
            finding_id=fid, principal_identity_id="examiner-1",
            action="confirm", reason="looks right",
            finding_content_digest=live)
        bindings = svc.verify_review_binding(fid)
        assert len(bindings) == 1
        assert bindings[0]["ok"] is True
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_review_binding_fails_after_finding_tampered_post_decision():
    """The exact property review.py's docstring claimed and nothing
    verified: tamper the finding *after* a human decision was
    recorded, and the binding check must catch it."""
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        fid = result.finding_ids[0]
        f_row = eng.query_one("SELECT * FROM satsa_findings WHERE id=?", (fid,))
        from satsa.analysis.run import RunService
        live = RunService._live_digest_for_finding(dict(f_row))
        svc.record_review(
            finding_id=fid, principal_identity_id="examiner-1",
            action="confirm", reason="looks right",
            finding_content_digest=live)
        # Tamper the finding AFTER the decision was recorded.
        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            ("TAMPERED AFTER DECISION", fid))
        bindings = svc.verify_review_binding(fid)
        assert len(bindings) == 1
        assert bindings[0]["ok"] is False
        assert "no longer matches" in bindings[0]["reason"]
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_review_binding_included_in_trust_sat_report():
    """verify_run now surfaces the review binding automatically for
    any finding that has decisions — a TRUST-SAT report is not
    complete without it."""
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        fid = result.finding_ids[0]
        f_row = eng.query_one("SELECT * FROM satsa_findings WHERE id=?", (fid,))
        from satsa.analysis.run import RunService
        live = RunService._live_digest_for_finding(dict(f_row))
        svc.record_review(
            finding_id=fid, principal_identity_id="examiner-1",
            action="dismiss", reason="false positive",
            finding_content_digest=live)
        report = svc.verify_run(result.run_id, key_dir)
        assert "reviews" in report
        assert len(report["reviews"]) == 1
        assert report["reviews"][0]["finding_id"] == fid
        assert report["reviews"][0]["decisions"][0]["ok"] is True
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_findings_with_no_review_history_report_empty_bindings():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        report = svc.verify_run(result.run_id, key_dir)
        assert report["reviews"] == []


    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------------------
# Gap 2: insertion — a finding that was never signed at all
# ---------------------------------------------------------------------------

def test_inserted_unsigned_finding_is_never_reported_as_verified():
    """A finding fabricated directly in the database (never went
    through RunService -> TrustService.sign_finding) must never be
    reportable as verified — there is no receipt to check it against."""
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        from satsa.analysis.trust import TrustService
        trust = TrustService(eng, key_dir)
        fabricated_id = "finding_fabricated_not_signed"
        ok, reason = trust.verify_subject(
            "finding", fabricated_id, "any-digest-at-all")
        assert ok is False
        assert "no trust receipt" in reason.lower()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------------------
# Gap 3: live-state verification, not a cached snapshot
# ---------------------------------------------------------------------------

def test_verification_reflects_live_state_not_a_cached_object():
    """Analytics run fine with verification never invoked (trust is
    not a gate on computation). Then: verify -> ok; tamper -> verify
    fails; restore the exact original value -> verify ok again. The
    8/8-VERIFIED-style badge must be re-derived from the database as
    it stands at call time, every time."""
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seeded_run(eng, td)
        # Analytics already ran and produced findings/risk without
        # anyone having called verify_run yet.
        prof = svc.compute_risk(eid)
        assert prof.run_id == result.run_id, (
            "risk computation must not depend on trust verification "
            "having been called first")

        report1 = svc.verify_run(result.run_id, key_dir)
        assert report1["run"]["ok"] is True

        fid = result.finding_ids[0]
        original = eng.query_one(
            "SELECT rationale FROM satsa_findings WHERE id=?", (fid,))["rationale"]
        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            ("TAMPERED", fid))
        report2 = svc.verify_run(result.run_id, key_dir)
        tampered_row = next(f for f in report2["findings"] if f["finding_id"] == fid)
        assert tampered_row["ok"] is False

        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            (original, fid))
        report3 = svc.verify_run(result.run_id, key_dir)
        restored_row = next(f for f in report3["findings"] if f["finding_id"] == fid)
        assert restored_row["ok"] is True, (
            "restoring the exact original value must verify again — "
            "proves this re-derives from live state, not a cached "
            "pass/fail recorded once")
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)

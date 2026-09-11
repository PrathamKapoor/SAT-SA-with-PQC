"""Phase 44 — cryptographic trust stress tests.

Every trust mutation must either be correctly rejected
(by verify_subject) or explicitly classified as outside the
trust boundary. No silent success.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from satsa.service import SatsaService
from satsa.analysis.run import RunService
from satsa.analysis.trust import TrustService
from satsa.analysis.canonical import live_finding_digest


def _setup():
    td = Path(tempfile.mkdtemp())
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
    MigrationRunner(eng).migrate()
    return eng, td


def _seed_one_finding(eng, td):
    svc = SatsaService(eng)
    e = svc.register_entity("CSE-A", sector="defence",
                             environment_class="on-prem")
    a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
    from satsa.domain.entities import Submission
    from satsa.domain.workflow import Alert
    from satsa.store.repositories import AlertStore, SubmissionStore
    sub_id = "sub-1"
    SubmissionStore(eng).insert(Submission(
        id=sub_id, assessment_id=a.id, source_system="t",
        declared_period_start=1735689600.0, declared_period_end=1738281600.0,
        file_digests={}, declared_counts={},
        received_at=1735689600.0, signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap", created_at=1735689600.0)
    AlertStore(eng).insert(Alert(entity_id=e.id, assessment_id=a.id,
                                native_id="a1", created_at=1735689600.0,
                                mapped_severity="medium",
                                acknowledged_at=1735689600.0 + 60,
                                closed_at=1735689600.0 + 600,
                                source_record_ref="sr-1"),
                      submission_id=sub_id)
    key_dir = td / "keys"
    result = RunService(eng).run(e.id, a.id, trust_key_dir=key_dir)
    return svc, e.id, result, key_dir


def test_valid_signature_verifies():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        report = svc.verify_run(result.run_id, key_dir)
        assert report["run"]["ok"] is True
        for f in report["findings"]:
            assert f["ok"] is True, f["reason"]
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_rationale_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        fid = result.finding_ids[0]
        eng.execute(
            "UPDATE satsa_findings SET rationale=? WHERE id=?",
            ("TAMPERED RATIONALE", fid))
        report = svc.verify_run(result.run_id, key_dir)
        for f in report["findings"]:
            if f["finding_id"] == fid:
                assert f["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_threshold_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        fid = result.finding_ids[0]
        eng.execute(
            "UPDATE satsa_findings SET threshold=999.0 WHERE id=?", (fid,))
        report = svc.verify_run(result.run_id, key_dir)
        for f in report["findings"]:
            if f["finding_id"] == fid:
                assert f["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_confidence_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        fid = result.finding_ids[0]
        eng.execute(
            "UPDATE satsa_findings SET confidence_json=? WHERE id=?",
            ('{"analytical_support":0.1,"evidence_completeness":0.1,'
             '"overall":0.1,"peer_confidence":null}', fid))
        report = svc.verify_run(result.run_id, key_dir)
        for f in report["findings"]:
            if f["finding_id"] == fid:
                assert f["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_evidence_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        fid = result.finding_ids[0]
        eng.execute(
            "UPDATE satsa_findings SET evidence_refs_json=? WHERE id=?",
            ('["TAMPERED-SR"]', fid))
        report = svc.verify_run(result.run_id, key_dir)
        for f in report["findings"]:
            if f["finding_id"] == fid:
                assert f["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_finding_observation_id_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        fid = result.finding_ids[0]
        # The finding has a FK on observation_id. We need to point
        # it to a real observation. Find the other observation created
        # by the run (there are 14: one per worker).
        rows = eng.query_all(
            "SELECT id FROM satsa_observations WHERE id != "
            "(SELECT observation_id FROM satsa_findings WHERE id=?)",
            (fid,))
        other_obs = rows[0]["id"]
        eng.execute(
            "UPDATE satsa_findings SET observation_id=? WHERE id=?",
            (other_obs, fid))
        report = svc.verify_run(result.run_id, key_dir)
        for f in report["findings"]:
            if f["finding_id"] == fid:
                assert f["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_tampered_run_digest_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        # The receipt's content_digest is the value at sign time.
        # If we tamper the row's content_digest, the receipt's
        # content_digest (which is the original value) won't match
        # the live digest computed from the tampered row.
        eng.execute(
            "UPDATE satsa_runs SET content_digest=? WHERE id=?",
            ("0" * 64, result.run_id))
        report = svc.verify_run(result.run_id, key_dir)
        # The run signature should fail because the receipt's stored
        # content_digest differs from the live (tampered) digest.
        assert report["run"]["ok"] is False, f"unexpected: {report['run']}"
        assert "mismatch" in report["run"]["reason"].lower()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_corrupted_signature_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        # Corrupt the signature in the receipt
        eng.execute(
            "UPDATE satsa_trust_receipts SET signature=? WHERE subject_id=?",
            (b"\x00" * 64, result.run_id))
        report = svc.verify_run(result.run_id, key_dir)
        assert report["run"]["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_deleted_receipt_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        eng.execute(
            "DELETE FROM satsa_trust_receipts WHERE subject_id=?",
            (result.run_id,))
        report = svc.verify_run(result.run_id, key_dir)
        assert report["run"]["ok"] is False
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_missing_receipt_fails_verification():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        eng.execute(
            "DELETE FROM satsa_trust_receipts WHERE subject_id=?",
            (result.run_id,))
        report = svc.verify_run(result.run_id, key_dir)
        assert report["run"]["ok"] is False
        assert "no trust receipt" in report["run"]["reason"].lower()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_re_verification_after_no_change_succeeds():
    eng, td = _setup()
    try:
        svc, eid, result, key_dir = _seed_one_finding(eng, td)
        r1 = svc.verify_run(result.run_id, key_dir)
        r2 = svc.verify_run(result.run_id, key_dir)
        assert r1["run"]["ok"] is True
        assert r2["run"]["ok"] is True
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)

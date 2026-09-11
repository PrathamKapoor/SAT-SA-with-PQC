"""Phase P26 addendum (checklist item 8) — review-decision ledger
integrity: closes the documented gap in docs/TRUST_MODEL.md ("Record
deletion from satsa_review_decisions / reordering — not detected").

``ReviewService.verify_binding`` (existing, P20) already catches a
decision row whose *content* was edited in place, by comparing the
finding's live digest against the digest captured at decision time.
It cannot catch a row being deleted outright, or a forged row
inserted directly via SQL bypassing ``record()``. This phase mirrors
every recorded decision into an independent, hash-chained
``EvidenceLedger`` (the same class already used for identity audit)
and cross-checks the DB table against it in both directions.
"""
from __future__ import annotations

import time

import pytest

from satsa.analysis.review import ReviewService, build_review_decision_ledger


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
def ledger_dir(tmp_path):
    return tmp_path / "keys"


@pytest.fixture()
def review_service(engine, ledger_dir):
    ledger = build_review_decision_ledger(ledger_dir)
    return ReviewService(engine, decision_ledger=ledger)


def _record(svc, finding_id="f1", **overrides):
    kwargs = dict(
        finding_id=finding_id, principal_identity_id="examiner-1",
        action="confirm", reason="ok", finding_content_digest="digest-a",
    )
    kwargs.update(overrides)
    return svc.record(**kwargs)


def test_verify_ledger_integrity_requires_a_ledger(engine):
    svc = ReviewService(engine)  # no decision_ledger
    with pytest.raises(ValueError):
        svc.verify_ledger_integrity()


def test_clean_recording_is_fully_consistent(review_service):
    _record(review_service)
    _record(review_service, finding_id="f2")
    report = review_service.verify_ledger_integrity()
    assert report["chain_ok"] is True
    assert report["ledger_entries"] == 2
    assert report["db_rows"] == 2
    assert report["missing_from_db"] == []
    assert report["missing_from_ledger"] == []
    assert report["fully_consistent"] is True


def test_deleting_a_decision_row_is_detected(review_service, engine):
    """A decision recorded, then deleted straight from the DB table —
    the exact threat docs/TRUST_MODEL.md flagged as undetected."""
    entry = _record(review_service)
    engine.execute("DELETE FROM satsa_review_decisions WHERE id=?", (entry.id,))
    report = review_service.verify_ledger_integrity()
    assert report["chain_ok"] is True  # the ledger itself is untouched
    assert entry.id in report["missing_from_db"]
    assert report["fully_consistent"] is False


def test_inserting_a_row_outside_record_is_detected(review_service, engine):
    """A forged decision row inserted directly via SQL, never going
    through ``record()`` (so it was never mirrored to the ledger)."""
    from qsmlops.crypto.hashing import digest_document
    from satsa.domain.evidence import ReviewDecision
    forged = ReviewDecision(
        finding_id="f1", principal_identity_id="attacker",
        action="dismiss", reason="forged", occurred_at=time.time())
    digest = digest_document(forged.to_dict())
    engine.execute(
        "INSERT INTO satsa_review_decisions (id, finding_id,"
        " principal_identity_id, action, reason, occurred_at,"
        " previous_revision_id, finding_content_digest, content_digest,"
        " created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("forged-1", "f1", "attacker", "dismiss", "forged",
         time.time(), None, "digest-a", digest, time.time()))
    report = review_service.verify_ledger_integrity()
    assert "forged-1" in report["missing_from_ledger"]
    assert report["fully_consistent"] is False


def test_ledger_chain_tamper_is_detected(review_service, ledger_dir):
    """Directly editing the ledger file (not the DB) must fail
    verify_chain(), the same tamper-evidence property the identity
    audit ledger already relies on (same EvidenceLedger class)."""
    _record(review_service)
    ledger_path = ledger_dir / "review_decision_ledger.jsonl"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    import json
    entry = json.loads(lines[0])
    entry["record"]["action"] = "dismiss"  # tamper the recorded action
    ledger_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    report = review_service.verify_ledger_integrity()
    assert report["chain_ok"] is False
    assert report["chain_error"]
    assert report["fully_consistent"] is False


def test_empty_state_is_fully_consistent(review_service):
    report = review_service.verify_ledger_integrity()
    assert report["ledger_entries"] == 0
    assert report["db_rows"] == 0
    assert report["fully_consistent"] is True


def test_record_without_ledger_is_unaffected(engine):
    """Constructing ReviewService without a decision_ledger (every
    pre-P26 call site) must behave exactly as before — no ledger
    file, no mirroring, no error."""
    svc = ReviewService(engine)
    entry = svc.record(
        finding_id="f1", principal_identity_id="examiner-1",
        action="confirm", reason="ok", finding_content_digest="digest-a")
    assert entry.id
    history = svc.history("f1")
    assert len(history) == 1


def test_service_layer_wiring(tmp_path):
    """SatsaService.record_review(trust_key_dir=...) actually wires
    the ledger through; omitting trust_key_dir behaves as before."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService

    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    key_dir = tmp_path / "keys"

    svc.record_review(
        finding_id="f1", principal_identity_id="examiner-1",
        action="confirm", reason="ok", finding_content_digest="digest-a",
        trust_key_dir=key_dir)
    report = svc.verify_review_ledger_integrity(key_dir)
    assert report["fully_consistent"] is True
    assert report["db_rows"] == 1
    assert report["ledger_entries"] == 1

    # A decision recorded without trust_key_dir never reaches the
    # ledger — checkable, not silently assumed consistent.
    svc.record_review(
        finding_id="f2", principal_identity_id="examiner-1",
        action="confirm", reason="ok", finding_content_digest="digest-b")
    report2 = svc.verify_review_ledger_integrity(key_dir)
    assert report2["fully_consistent"] is False
    assert "f2" not in report2["missing_from_ledger"]  # ids are review ids, not finding ids
    assert report2["db_rows"] == 2
    assert report2["ledger_entries"] == 1

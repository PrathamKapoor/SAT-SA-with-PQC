"""TRUST-SAT tampering through the hosted API verify endpoint.

tests/test_phase5_trust_finalization.py covers field-level mutations at the
service. These tests add the attacker moves that combine rows (reviewer swap,
cross-run receipt, re-signing with an attacker key, ledger reordering or
truncation, deleted records) and check the HTTP result an operator sees:
"inconsistent", never "verified", never a 500.
"""

import json

import pytest
from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def finalized_run(api, key):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    version = api.get("_version")
    if version is None:
        version = api["_version"] = dataset(api)[3]["id"]
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key=key),
        json={"submission_version_id": version, "execution_mode": "standard"},
    ).json()["id"]
    worker = AnalysisExecutionWorker(
        api["db"], worker_id=key, audit=api["audit"], trust_key_dir=str(api["keys"])
    )
    assert worker.run_once() == "awaiting_review"
    decided = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Reviewed"},
    )
    assert decided.status_code == 201, decided.text
    assert worker.run_once() in {"completed", "partial"}
    assert verify(api, run) == "verified"
    return run


def verify(api, run):
    response = api["client"].post(f"/api/v1/runs/{run}/verify", headers=headers(api))
    assert response.status_code == 200, response.text
    return response.json()["status"]


def ledger_lines(api):
    path = api["audit"]._ledger.path
    return path, path.read_text(encoding="utf-8").splitlines()


def resign_with_attacker_key(api, run):
    from qsmlops.crypto import SIGNATURE_PROVIDERS

    db = api["db"]
    final = db.query_one("SELECT * FROM satsa_trust_finalizations WHERE run_id=?", (run,))
    receipt = db.query_one("SELECT * FROM satsa_trust_receipts WHERE id=?", (final["receipt_id"],))
    provider = SIGNATURE_PROVIDERS[receipt["algorithm_id"]]
    attacker = provider.generate_keypair()
    signature = provider.sign(attacker.secret_key, receipt["content_digest"].encode("utf-8"))
    db.execute(
        "UPDATE satsa_trust_receipts SET public_key=?, signature=? WHERE id=?",
        (attacker.public_key, signature, receipt["id"]),
    )


def mutate(api, run, other, mutation):
    db = api["db"]
    if mutation == "reviewer_identity":
        outsider = db.query_one(
            "SELECT identity_id FROM satsa_users u JOIN satsa_memberships m ON m.user_id=u.id"
            " WHERE m.role='satsa_viewer'"
        )["identity_id"]
        db.execute(
            "UPDATE satsa_run_review_decisions SET principal_identity_id=? WHERE run_id=?",
            (outsider, run),
        )
    elif mutation == "reviewer_user":
        viewer = db.query_one(
            "SELECT user_id FROM satsa_memberships WHERE role='satsa_viewer'"
        )["user_id"]
        db.execute("UPDATE satsa_run_review_decisions SET user_id=? WHERE run_id=?", (viewer, run))
    elif mutation == "decision_moved_to_other_run":
        db.execute("DELETE FROM satsa_run_review_decisions WHERE run_id=?", (other,))
        db.execute("UPDATE satsa_run_review_decisions SET run_id=? WHERE run_id=?", (other, run))
    elif mutation == "receipt_from_other_run":
        foreign = db.query_one(
            "SELECT receipt_id FROM satsa_trust_finalizations WHERE run_id=?", (other,)
        )["receipt_id"]
        db.execute(
            "UPDATE satsa_trust_finalizations SET receipt_id=? WHERE run_id=?", (foreign, run)
        )
    elif mutation == "attacker_key":
        resign_with_attacker_key(api, run)
    elif mutation == "algorithm":
        db.execute(
            "UPDATE satsa_trust_receipts SET algorithm_id='none'"
            " WHERE subject_type='supervisory_finalization'"
        )
    elif mutation == "receipt_deleted":
        final = db.query_one("SELECT receipt_id FROM satsa_trust_finalizations WHERE run_id=?", (run,))
        db.execute("DELETE FROM satsa_trust_receipts WHERE id=?", (final["receipt_id"],))
    elif mutation == "ledger_hash_field":
        db.execute("UPDATE satsa_trust_finalizations SET ledger_entry_hash=? WHERE run_id=?",
                   ("0" * 64, run))
    elif mutation in {"ledger_reordered", "ledger_truncated", "ledger_event_edited"}:
        path, lines = ledger_lines(api)
        if mutation == "ledger_reordered":
            lines[-1], lines[-2] = lines[-2], lines[-1]
        elif mutation == "ledger_truncated":
            final = db.query_one("SELECT id FROM satsa_trust_finalizations WHERE run_id=?", (run,))
            lines = [line for line in lines if json.loads(line)["record"].get("event_id") != final["id"]]
        else:
            for index, line in enumerate(lines):
                entry = json.loads(line)
                if entry["record"].get("action") == "trust.supervisory_finalized":
                    entry["record"]["actor"] = "forged"
                    lines[index] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif mutation == "finalization_deleted":
        db.execute("DELETE FROM satsa_trust_finalizations WHERE run_id=?", (run,))
    elif mutation == "run_rebound":
        db.execute(
            "UPDATE satsa_trust_finalizations SET run_id=? WHERE run_id=?", (other + "-x", run)
        )
    else:  # pragma: no cover
        raise AssertionError(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "reviewer_identity",
        "reviewer_user",
        "decision_moved_to_other_run",
        "receipt_from_other_run",
        "attacker_key",
        "algorithm",
        "receipt_deleted",
        "ledger_hash_field",
        "ledger_reordered",
        "ledger_truncated",
        "ledger_event_edited",
        "finalization_deleted",
        "run_rebound",
    ],
)
def test_tampering_is_reported_inconsistent_over_http(api, mutation):
    from qsmlops.core.errors import QSMLOPSError

    run = finalized_run(api, "run-a")
    other = finalized_run(api, "run-b")
    try:
        mutate(api, run, other, mutation)
    except QSMLOPSError:
        # Foreign keys and unique constraints refused the tampering itself;
        # the recorded state is intact and still verifies.
        assert verify(api, run) == "verified", mutation
        return
    assert verify(api, run) == "inconsistent", mutation


def test_supervised_run_awaiting_review_is_not_finalized_not_inconsistent(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    _, _, _, version, _ = dataset(api)
    run = api["client"].post(
        "/api/v1/runs",
        headers=headers(api, key="pending"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    ).json()["id"]
    assert verify(api, run) == "not_finalized"
    AnalysisExecutionWorker(
        api["db"], worker_id="p", audit=api["audit"], trust_key_dir=str(api["keys"])
    ).run_once()
    assert verify(api, run) == "not_finalized"


def test_missing_signing_key_never_completes_a_supervised_run(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    _, _, _, version, _ = dataset(api)
    c = api["client"]
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key="nokey"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    ).json()["id"]
    good = AnalysisExecutionWorker(
        api["db"], worker_id="good", audit=api["audit"], trust_key_dir=str(api["keys"])
    )
    assert good.run_once() == "awaiting_review"
    c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Reviewed"},
    )
    broken = AnalysisExecutionWorker(
        api["db"], worker_id="broken", audit=api["audit"], trust_key_dir=None
    )
    broken.run_once()
    state = c.get(f"/api/v1/runs/{run}", headers=headers(api)).json()["status"]
    assert state not in {"completed", "partial"}, state
    assert verify(api, run) != "verified"

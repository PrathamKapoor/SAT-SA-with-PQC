"""Replays and races on the hosted workflow (PostgreSQL shows the real races).

Invariants: duplicate requests return the original object; competing requests
produce exactly one outcome and the losers a clean conflict; no race leaves a
cancelled run resurrected or a run with two supervisory decisions.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def user_id(api, role):
    return api["client"].get("/api/v1/session", headers=headers(api, role)).json()["user_id"]


def services(api, role):
    from satsa.analysis.execution import AnalysisExecutionService
    from satsa.submissions.service import SubmissionService

    uid = user_id(api, role)
    storage = api["client"].app.state.storage
    return (
        SubmissionService(api["db"], api["org"], uid, storage=storage, audit=api["audit"]),
        AnalysisExecutionService(api["db"], api["org"], uid, audit=api["audit"]),
    )


def race(fn, args, workers=6):
    """Run fn(*arg) for every arg at once; return (results, errors)."""
    barrier = threading.Barrier(len(args))

    def call(arg):
        barrier.wait(timeout=30)
        try:
            return ("ok", fn(*arg))
        except Exception as exc:  # noqa: BLE001 - the classification is asserted
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(call, args))


def reviewed_run(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    _, _, _, version, _ = dataset(api)
    run = api["client"].post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    ).json()["id"]
    worker = AnalysisExecutionWorker(
        api["db"], worker_id="race", audit=api["audit"], trust_key_dir=str(api["keys"])
    )
    assert worker.run_once() == "awaiting_review"
    return version["id"], run, worker


def conflict(exc):
    from satsa.errors import DomainValidationError

    return isinstance(exc, DomainValidationError)


def test_competing_supervisory_decisions_record_exactly_one(api):
    _, run, _ = reviewed_run(api)
    _, supervisor = services(api, "supervisor")
    _, admin = services(api, "admin")
    attempts = [
        (supervisor, "confirm", "first"),
        (admin, "dismiss", "second"),
        (supervisor, "escalate", "third"),
        (admin, "confirm", "fourth"),
    ]
    outcomes = race(lambda svc, action, reason: svc.decide(run, action=action, reason=reason),
                    attempts)
    winners = [value for kind, value in outcomes if kind == "ok"]
    losers = [value for kind, value in outcomes if kind == "error"]
    assert len({w["id"] for w in winners}) == 1, outcomes
    assert all(conflict(exc) for exc in losers), losers
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_run_review_decisions WHERE run_id=?", (run,)
    )["n"] == 1


def test_identical_decision_replay_is_idempotent_under_concurrency(api):
    _, run, worker = reviewed_run(api)
    _, supervisor = services(api, "supervisor")
    outcomes = race(lambda: supervisor.decide(run, action="confirm", reason="same"), [()] * 4)
    ids = {value["id"] for kind, value in outcomes if kind == "ok"}
    assert len(ids) == 1, outcomes
    assert all(kind == "ok" or conflict(value) for kind, value in outcomes), outcomes
    assert worker.run_once() in {"completed", "partial"}
    verified = api["client"].post(f"/api/v1/runs/{run}/verify", headers=headers(api))
    assert verified.json()["status"] == "verified"


def test_cancel_racing_a_decision_never_resurrects_a_cancelled_run(api):
    _, run, worker = reviewed_run(api)
    _, supervisor = services(api, "supervisor")
    _, admin = services(api, "admin")
    outcomes = race(
        lambda op: op(),
        [
            (lambda: supervisor.decide(run, action="confirm", reason="race"),),
            (lambda: admin.cancel(run),),
        ],
    )
    assert all(kind == "ok" or conflict(value) for kind, value in outcomes), outcomes
    status = api["db"].query_one("SELECT status FROM satsa_runs WHERE id=?", (run,))["status"]
    decided = api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_run_review_decisions WHERE run_id=?", (run,)
    )["n"]
    worker.run_once()
    final = api["db"].query_one("SELECT status FROM satsa_runs WHERE id=?", (run,))["status"]
    if status in {"cancel_requested", "cancelled"}:
        assert final == "cancelled", (status, final, decided)
        assert not api["db"].query_one(
            "SELECT run_id FROM satsa_trust_finalizations WHERE run_id=?", (run,)
        )
    else:
        assert decided == 1 and final in {"completed", "partial", "cancelled"}


def test_cancel_between_decision_checks_and_commit_is_honoured(api, request):
    """Deterministic interleavings of a decision and a cancel on PostgreSQL."""
    if "postgresql" not in request.node.callspec.id:
        pytest.skip("SQLite serializes whole transactions; the interleaving cannot occur")
    from satsa.analysis import canonical

    # 1. Cancel commits after the decision's pre-checks, before its transaction.
    _, run, worker = reviewed_run(api)
    _, supervisor = services(api, "supervisor")
    _, admin = services(api, "admin")
    original = canonical.live_finding_digest

    def cancel_first(*args, **kwargs):
        admin.cancel(run)
        return original(*args, **kwargs)

    canonical.live_finding_digest = cancel_first
    try:
        with pytest.raises(Exception) as caught:
            supervisor.decide(run, action="confirm", reason="late")
    finally:
        canonical.live_finding_digest = original
    assert conflict(caught.value), caught.value
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_run_review_decisions WHERE run_id=?", (run,)
    )["n"] == 0
    worker.run_once()
    assert api["db"].query_one("SELECT status FROM satsa_runs WHERE id=?", (run,))["status"] == "cancelled"


def test_cancel_during_a_decision_waits_and_is_not_lost(api, request):
    if "postgresql" not in request.node.callspec.id:
        pytest.skip("SQLite serializes whole transactions; the interleaving cannot occur")
    from satsa.analysis import canonical

    _, run, worker = reviewed_run(api)
    _, supervisor = services(api, "supervisor")
    _, admin = services(api, "admin")
    original = canonical.supervisory_document
    threads = []

    def cancel_inside(*args, **kwargs):
        if not threads:
            thread = threading.Thread(target=admin.cancel, args=(run,))
            threads.append(thread)
            thread.start()
            thread.join(timeout=1)
            assert thread.is_alive(), "cancel must wait for the decision's row lock"
        return original(*args, **kwargs)

    canonical.supervisory_document = cancel_inside
    try:
        supervisor.decide(run, action="confirm", reason="first")
    finally:
        canonical.supervisory_document = original
    threads[0].join(timeout=30)
    assert not threads[0].is_alive()
    # The cancel applied to the queued (decided) run instead of being lost.
    assert api["db"].query_one("SELECT status FROM satsa_runs WHERE id=?", (run,))["status"] == "cancel_requested"
    worker.run_once()
    assert api["db"].query_one("SELECT status FROM satsa_runs WHERE id=?", (run,))["status"] == "cancelled"
    assert not api["db"].query_one(
        "SELECT run_id FROM satsa_trust_finalizations WHERE run_id=?", (run,)
    )


def test_concurrent_run_requests_with_one_key_create_one_run(api):
    _, _, _, version, _ = dataset(api)
    _, analyst = services(api, "analyst")
    outcomes = race(
        lambda: analyst.create_run(version["id"], idempotency_key="same", review_required=True),
        [()] * 6,
    )
    assert all(kind == "ok" for kind, _ in outcomes), outcomes
    assert len({value["id"] for _, value in outcomes}) == 1
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_execution_jobs WHERE organization_id=?", (api["org"],)
    )["n"] == 1


def test_concurrent_validation_produces_one_report(api):
    from test_phase2_submission_platform import ALERTS

    c = api["client"]
    h = headers(api)
    entity = c.post("/api/v1/entities", headers=h, json={"display_name": "V"}).json()
    assessment = c.post(
        "/api/v1/assessments", headers=h,
        json={"entity_id": entity["id"], "period_start": 1700000000, "period_end": 1800000000},
    ).json()
    submission = c.post("/api/v1/submissions", headers=headers(api, key="s"),
                        json={"assessment_id": assessment["id"]}).json()
    version = c.post(f"/api/v1/submissions/{submission['id']}/versions",
                     headers=headers(api, key="v")).json()["id"]
    submissions, _ = services(api, "analyst")
    import io

    outcomes = race(
        lambda: submissions.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                                   filename="alerts.csv", content_type="text/csv",
                                   idempotency_key="u"),
        [()] * 4,
    )
    assert all(kind == "ok" for kind, _ in outcomes), outcomes
    assert len({value["id"] for _, value in outcomes}) == 1
    submissions.complete_uploads(version)
    outcomes = race(lambda: submissions.validate(version), [()] * 4)
    assert all(kind == "ok" or conflict(value) for kind, value in outcomes), outcomes
    assert any(kind == "ok" for kind, _ in outcomes)
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_validation_reports WHERE version_id=?", (version,)
    )["n"] == 1
    state = c.get(f"/api/v1/versions/{version}", headers=h).json()["status"]
    assert state == "valid", state
    # Whatever lost the race, the version is usable and validation is stable.
    assert submissions.validate(version)["status"] == "valid"

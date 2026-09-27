"""Tenant-scoped entity prioritization over persisted run results."""

from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def _analysed_run(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    entity, _, _, version, _ = dataset(api)
    start = c.post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    )
    assert start.status_code == 202, start.text
    worker = AnalysisExecutionWorker(
        api["db"],
        worker_id="priority-test",
        audit=api["audit"],
        trust_key_dir=str(api["keys"]),
    )
    assert worker.run_once() == "awaiting_review"
    return entity, start.json()["id"], worker


def test_priorities_rank_persisted_risk_within_tenant(api):
    c = api["client"]
    empty = c.get("/api/v1/priorities", headers=headers(api, "viewer"))
    assert empty.status_code == 200, empty.text
    assert empty.json()["items"] == []

    entity, run, worker = _analysed_run(api)
    page = c.get("/api/v1/priorities", headers=headers(api, "viewer"))
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["has_more"] is False
    [item] = body["items"]
    assert item["entity_id"] == entity["id"]
    assert item["run_id"] == run
    assert item["run_status"] == "awaiting_review"
    risk = c.get(f"/api/v1/runs/{run}/risk", headers=headers(api)).json()
    assert item["risk_score"] == round(risk["profile"]["total_score"], 2)
    assert item["confidence_bucket"] == risk["profile"]["confidence_bucket"]
    assert item["priority_score"] >= item["risk_score"]

    # The ranking survives the decision and terminal finalization.
    decided = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Examined evidence"},
    )
    assert decided.status_code == 201, decided.text
    assert worker.run_once() in {"completed", "partial"}
    [after] = c.get("/api/v1/priorities", headers=headers(api)).json()["items"]
    assert after["run_id"] == run
    assert after["run_status"] in {"completed", "partial"}


def test_priorities_do_not_cross_tenants(api):
    c = api["client"]
    _analysed_run(api)
    foreign = c.get("/api/v1/priorities", headers=headers(api, "outsider"))
    assert foreign.status_code == 200, foreign.text
    assert foreign.json()["items"] == []

    # An outsider naming the other organization is refused, not served.
    spoofed = {**headers(api, "outsider"), "X-Organization-ID": api["org"]}
    assert c.get("/api/v1/priorities", headers=spoofed).status_code in {403, 404}
    unauthenticated = c.get(
        "/api/v1/priorities", headers={"X-Organization-ID": api["org"]}
    )
    assert unauthenticated.status_code == 401

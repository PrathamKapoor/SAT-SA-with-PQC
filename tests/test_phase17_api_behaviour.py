"""Behaviour the frontend contract relies on (docs/API_CONTRACT.md)."""

import io

from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def _worker(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    return AnalysisExecutionWorker(
        api["db"],
        worker_id="phase17-test",
        audit=api["audit"],
        trust_key_dir=str(api["keys"]),
    )


def _second_entity_run(api) -> tuple[str, str]:
    """Analyse a second entity of the same organization."""
    from test_phase2_submission_platform import ALERTS

    c, h = api["client"], headers(api)
    entity = c.post("/api/v1/entities", headers=h, json={"display_name": "Bank B"})
    assessment = c.post(
        "/api/v1/assessments",
        headers=h,
        json={
            "entity_id": entity.json()["id"],
            "period_start": 1700000000,
            "period_end": 1800000000,
        },
    )
    body = {"assessment_id": assessment.json()["id"]}
    submission = c.post(
        "/api/v1/submissions", headers=headers(api, key="b-sub"), json=body
    ).json()
    version = c.post(
        f"/api/v1/submissions/{submission['id']}/versions",
        headers=headers(api, key="b-ver"),
    ).json()
    c.post(
        f"/api/v1/versions/{version['id']}/artifacts?category=alerts",
        headers=headers(api, key="b-alerts"),
        files={"file": ("alerts.csv", io.BytesIO(ALERTS), "text/csv")},
    )
    c.post(f"/api/v1/versions/{version['id']}/complete", headers=h)
    assert (
        c.post(f"/api/v1/versions/{version['id']}/validate", headers=h).json()["status"]
        == "valid"
    )
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key="b-run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    )
    assert run.status_code == 202, run.text
    return entity.json()["id"], run.json()["id"]


def _first_entity_run(api) -> tuple[str, str, str]:
    c = api["client"]
    entity, _, _, version, _ = dataset(api)
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key="a-run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    )
    assert run.status_code == 202, run.text
    return entity["id"], run.json()["id"], version["id"]


def test_priorities_rank_multiple_entities_with_pagination(api):
    c = api["client"]
    first_entity, first_run, _ = _first_entity_run(api)
    second_entity, second_run = _second_entity_run(api)
    worker = _worker(api)
    assert worker.run_once() == "awaiting_review"
    assert worker.run_once() == "awaiting_review"

    full = c.get("/api/v1/priorities", headers=headers(api)).json()
    assert {row["entity_id"] for row in full["items"]} == {first_entity, second_entity}
    assert {row["run_id"] for row in full["items"]} == {first_run, second_run}
    scores = [row["priority_score"] for row in full["items"]]
    assert scores == sorted(scores, reverse=True)

    page1 = c.get("/api/v1/priorities?limit=1", headers=headers(api)).json()
    page2 = c.get("/api/v1/priorities?limit=1&offset=1", headers=headers(api)).json()
    assert page1["has_more"] is True and page2["has_more"] is False
    assert [page1["items"][0], page2["items"][0]] == full["items"]

    outsider = c.get("/api/v1/priorities", headers=headers(api, "outsider")).json()
    assert outsider["items"] == []


def test_records_ordering_and_unknown_version(api):
    c = api["client"]
    _, _, version = _first_entity_run(api)
    records = c.get(f"/api/v1/versions/{version}/records", headers=headers(api)).json()[
        "items"
    ]
    keys = [(r["category"], r["record_id"]) for r in records]
    assert keys == sorted(keys)
    unknown = c.get("/api/v1/versions/version_missing/records", headers=headers(api))
    assert unknown.status_code in {403, 404}
    assert "payload" not in unknown.text


def test_organization_admin_decides_and_receipt_has_no_private_material(api):
    c = api["client"]
    _, run, _ = _first_entity_run(api)
    worker = _worker(api)
    assert worker.run_once() == "awaiting_review"
    for role in ("viewer", "analyst", "auditor"):
        denied = c.post(
            f"/api/v1/runs/{run}/decision",
            headers=headers(api, role),
            json={"action": "confirm", "reason": "not allowed"},
        )
        assert denied.status_code == 403, role
    decided = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "admin"),
        json={"action": "escalate", "reason": "Administrator review"},
    )
    assert decided.status_code == 201, decided.text
    conflict = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "dismiss", "reason": "different"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DOMAIN_CONFLICT"
    assert worker.run_once() in {"completed", "partial"}

    receipt = c.get(f"/api/v1/runs/{run}/receipt", headers=headers(api, "viewer"))
    assert receipt.status_code == 200, receipt.text
    lowered = {key.lower() for key in receipt.json()}
    assert not any("private" in key or "secret" in key for key in lowered)
    verified = c.post(f"/api/v1/runs/{run}/verify", headers=headers(api, "viewer"))
    assert verified.json()["status"] == "verified"


def test_error_contract_for_missing_organization(api):
    c = api["client"]
    response = c.get(
        "/api/v1/entities",
        headers={
            "Authorization": f"Bearer {api['tokens']['viewer']}",
            "X-Request-ID": "contract-check-1",
        },
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "ORGANIZATION_REQUIRED"
    assert error["request_id"] == "contract-check-1"
    assert response.headers["X-Request-ID"] == "contract-check-1"
    assert "Traceback" not in response.text


def test_session_token_logout_keeps_the_credential(api):
    c = api["client"]
    credential = api["tokens"]["viewer"]
    login = c.post("/api/v1/session", json={"credential": credential})
    assert login.status_code == 200, login.text
    session_token = login.cookies.get("satsa_api_session")
    assert session_token and session_token != credential
    assert login.json()["csrf_token"]
    c.cookies.clear()

    as_session = {"Authorization": f"Bearer {session_token}"}
    assert c.get("/api/v1/session", headers=as_session).status_code == 200
    assert c.delete("/api/v1/session", headers=as_session).status_code == 204
    assert c.get("/api/v1/session", headers=as_session).status_code == 401
    still = c.get("/api/v1/session", headers={"Authorization": f"Bearer {credential}"})
    assert still.status_code == 200

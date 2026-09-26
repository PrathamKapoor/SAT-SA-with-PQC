"""Real HTTP workflow backed by SQLite and PostgreSQL services."""

import io

import pytest
from fastapi.testclient import TestClient

from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.service import IdentityService
from satsa.tenancy import TenantAdministration

pytest_plugins = ["test_tenant_schema"]


@pytest.fixture
def api(engine, tmp_path):
    from satsa.api import create_app
    from satsa.api.settings import ApiSettings
    from satsa.submissions.storage import LocalArtifactStorage

    audit = AuditService(EvidenceLedger(tmp_path / "audit.jsonl"), database=engine)
    identities = IdentityService(engine, audit)
    admin = TenantAdministration(engine)
    org = admin.create_organization("CSE A")
    other = admin.create_organization("CSE B")
    tokens = {}
    for role in ["viewer", "analyst", "supervisor", "auditor", "admin"]:
        identity = identities.create_identity("human", role, "owner", f"satsa_{role}")
        user = admin.create_user(identity.id, f"{role}@example.test")
        admin.add_membership(org, user, f"satsa_{role}")
        tokens[role] = identities.issue_credential(identity.id)
    outsider = identities.create_identity("human", "outsider", "owner", "satsa_admin")
    user = admin.create_user(outsider.id, "outsider@example.test")
    admin.add_membership(other, user, "satsa_admin")
    tokens["outsider"] = identities.issue_credential(outsider.id)
    app = create_app(
        engine,
        storage=LocalArtifactStorage(tmp_path / "artifacts"),
        audit=audit,
        identity_service=identities,
        settings=ApiSettings(secure_cookies=False),
        trust_key_dir=tmp_path / "keys",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield {
            "client": client,
            "db": engine,
            "tokens": tokens,
            "org": org,
            "other": other,
            "audit": audit,
            "identities": identities,
            "keys": tmp_path / "keys",
        }


def headers(api, role="analyst", key=None):
    result = {
        "Authorization": f"Bearer {api['tokens'][role]}",
        "X-Organization-ID": api["other"] if role == "outsider" else api["org"],
    }
    if key:
        result["Idempotency-Key"] = key
    return result


def dataset(api):
    client = api["client"]
    h = headers(api)
    entity = client.post(
        "/api/v1/entities",
        headers=h,
        json={"display_name": "Bank A", "sector": "banking"},
    )
    assert entity.status_code == 201, entity.text
    assessment = client.post(
        "/api/v1/assessments",
        headers=h,
        json={
            "entity_id": entity.json()["id"],
            "period_start": 1700000000,
            "period_end": 1800000000,
        },
    )
    assert assessment.status_code == 201, assessment.text
    body = {"assessment_id": assessment.json()["id"]}
    submission = client.post(
        "/api/v1/submissions", headers=headers(api, key="submission"), json=body
    )
    assert submission.status_code == 201, submission.text
    assert (
        client.post(
            "/api/v1/submissions", headers=headers(api, key="submission"), json=body
        ).json()["id"]
        == submission.json()["id"]
    )
    version = client.post(
        f"/api/v1/submissions/{submission.json()['id']}/versions",
        headers=headers(api, key="version"),
    )
    assert version.status_code == 201, version.text
    from test_phase2_submission_platform import ALERTS

    uploaded = client.post(
        f"/api/v1/versions/{version.json()['id']}/artifacts?category=alerts",
        headers=headers(api, key="alerts"),
        files={"file": ("alerts.csv", io.BytesIO(ALERTS), "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    complete = client.post(
        f"/api/v1/versions/{version.json()['id']}/complete", headers=h
    )
    assert complete.status_code == 200, complete.text
    valid = client.post(f"/api/v1/versions/{version.json()['id']}/validate", headers=h)
    assert valid.status_code == 200, valid.text
    return (
        entity.json(),
        assessment.json(),
        submission.json(),
        version.json(),
        uploaded.json(),
    )


def test_authentication_and_error_contract(api):
    c = api["client"]
    response = c.get("/api/v1/entities")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert c.post("/api/v1/session", json={"credential": "bad"}).status_code == 401
    login = c.post("/api/v1/session", json={"credential": api["tokens"]["analyst"]})
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "satsa_analyst"
    assert "HttpOnly" in login.headers["set-cookie"]
    assert c.get("/api/v1/session").status_code == 200
    # Cookie mutations require a session-bound token.
    assert c.delete("/api/v1/session").status_code == 403
    assert (
        c.delete(
            "/api/v1/session", headers={"X-CSRF-Token": login.json()["csrf_token"]}
        ).status_code
        == 204
    )
    assert c.get("/api/v1/session").status_code == 401


def test_bearer_logout_revokes_credential(api):
    c = api["client"]
    bearer_headers = headers(api)
    assert c.get("/api/v1/session", headers=bearer_headers).status_code == 200
    assert c.delete("/api/v1/session", headers=bearer_headers).status_code == 204
    assert c.get("/api/v1/session", headers=bearer_headers).status_code == 401


@pytest.mark.parametrize("graph", [False, True])
def test_complete_api_product_flow(api, graph):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    entity, assessment, submission, version, artifact = dataset(api)
    start = c.post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={
            "submission_version_id": version["id"],
            "execution_mode": "graph" if graph else "standard",
        },
    )
    assert start.status_code == 202, start.text
    run = start.json()["id"]
    assert start.json()["review_required"] is True
    worker = AnalysisExecutionWorker(
        api["db"],
        worker_id="api-test",
        audit=api["audit"],
        trust_key_dir=str(api["keys"]),
    )
    assert worker.run_once() == "awaiting_review"
    assert (
        c.get(f"/api/v1/runs/{run}", headers=headers(api)).json()["status"]
        == "awaiting_review"
    )
    for suffix in ["findings", "evidence", "recommendations", "risk", "steps"]:
        r = c.get(f"/api/v1/runs/{run}/{suffix}", headers=headers(api))
        assert r.status_code == 200, r.text
    assert (
        c.post(
            f"/api/v1/runs/{run}/decision",
            headers=headers(api),
            json={"action": "confirm"},
        ).status_code
        == 403
    )
    decision = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Examined evidence"},
    )
    assert decision.status_code == 201, decision.text
    repeated = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Examined evidence"},
    )
    assert repeated.json()["id"] == decision.json()["id"]
    assert worker.run_once() in {"completed", "partial"}
    assert c.get(f"/api/v1/runs/{run}/receipt", headers=headers(api)).status_code == 200
    verified = c.post(f"/api/v1/runs/{run}/verify", headers=headers(api))
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"
    audit = c.get("/api/v1/audit/events", headers=headers(api, "auditor"))
    assert audit.status_code == 200, audit.text
    assert "trust.supervisory_finalized" in {e["action"] for e in audit.json()["items"]}
    for path in [
        f"entities/{entity['id']}",
        f"assessments/{assessment['id']}",
        f"submissions/{submission['id']}",
        f"versions/{version['id']}",
        f"artifacts/{artifact['id']}",
        f"runs/{run}",
        f"runs/{run}/receipt",
        f"runs/{run}/decision",
        f"versions/{version['id']}/validation",
    ]:
        assert c.get(
            f"/api/v1/{path}", headers=headers(api, "outsider")
        ).status_code in {403, 404}, path


def test_pagination_rbac_and_openapi(api):
    c = api["client"]
    assert (
        c.post(
            "/api/v1/entities",
            headers=headers(api, "viewer"),
            json={"display_name": "Denied"},
        ).status_code
        == 403
    )
    assert c.get("/api/v1/audit/events", headers=headers(api)).status_code == 403
    empty = c.get("/api/v1/entities", headers=headers(api))
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"items": [], "limit": 50, "offset": 0, "has_more": False}
    invalid = c.get("/api/v1/entities?limit=201", headers=headers(api))
    assert invalid.status_code == 422
    assert "error" in invalid.json()
    schema = c.get("/openapi.json").json()
    assert "/api/v1/runs/{run_id}/decision" in schema["paths"]
    assert "securitySchemes" in schema["components"]


def test_member_admin_and_scope(api):
    c = api["client"]
    body = {"name": "New analyst", "email": "new@example.test", "role": "satsa_analyst"}
    assert c.post("/api/v1/members", headers=headers(api), json=body).status_code == 403
    member = c.post("/api/v1/members", headers=headers(api, "admin"), json=body)
    assert member.status_code == 201, member.text
    members = c.get("/api/v1/members", headers=headers(api, "admin"))
    assert member.json()["id"] in {m["id"] for m in members.json()["items"]}
    assert c.delete(
        f"/api/v1/members/{member.json()['id']}", headers=headers(api, "outsider")
    ).status_code in {403, 404}
    assert (
        c.delete(
            f"/api/v1/members/{member.json()['id']}", headers=headers(api, "admin")
        ).status_code
        == 204
    )


def test_admin_organization_provisioning(api):
    c = api["client"]
    assert (
        c.post(
            "/api/v1/organizations",
            headers=headers(api, "analyst"),
            json={"name": "Denied"},
        ).status_code
        == 403
    )
    created = c.post(
        "/api/v1/organizations", headers=headers(api, "admin"), json={"name": "CSE C"}
    )
    assert created.status_code == 201, created.text
    org = created.json()["id"]
    listed = c.get("/api/v1/organizations", headers=headers(api, "admin"))
    assert {item["id"] for item in listed.json()["items"]} >= {api["org"], org}
    new_context = {
        "Authorization": f"Bearer {api['tokens']['admin']}",
        "X-Organization-ID": org,
    }
    assert c.get("/api/v1/entities", headers=new_context).status_code == 200


@pytest.mark.parametrize(
    "role,can_write,can_review,can_audit",
    [
        ("viewer", False, False, False),
        ("analyst", True, False, False),
        ("supervisor", True, True, False),
        ("auditor", False, False, True),
        ("admin", True, True, True),
    ],
)
def test_role_matrix(api, role, can_write, can_review, can_audit):
    c = api["client"]
    h = headers(api, role)
    assert c.get("/api/v1/entities", headers=h).status_code == 200
    assert c.post(
        "/api/v1/entities", headers=h, json={"display_name": "RBAC"}
    ).status_code == (201 if can_write else 403)
    assert c.get("/api/v1/audit/events", headers=h).status_code == (
        200 if can_audit else 403
    )
    # Ownership failure and permission failure both deny; no run existence leak.
    assert c.post(
        "/api/v1/runs/foreign/decision", headers=h, json={"action": "confirm"}
    ).status_code in {403, 404}


def test_session_expiry_rotation_and_csrf_isolation(api):
    c = api["client"]
    first = c.post("/api/v1/session", json={"credential": api["tokens"]["analyst"]})
    first_csrf = first.json()["csrf_token"]
    second = c.post("/api/v1/session", json={"credential": api["tokens"]["supervisor"]})
    assert second.status_code == 200
    assert (
        c.delete("/api/v1/session", headers={"X-CSRF-Token": first_csrf}).status_code
        == 403
    )
    api["db"].execute("UPDATE satsa_sessions SET expires_at=0")
    assert c.get("/api/v1/session").status_code == 401
    login = c.post("/api/v1/session", json={"credential": api["tokens"]["analyst"]})
    api["identities"].revoke_credential(login.json()["identity_id"])
    assert c.get("/api/v1/session").status_code == 401


def test_limits_security_headers_and_login_origin(api):
    c = api["client"]
    assert (
        c.post(
            "/api/v1/session",
            headers={"Origin": "https://attacker.test"},
            json={"credential": api["tokens"]["analyst"]},
        ).status_code
        == 403
    )
    for _ in range(4):
        assert (
            c.post("/api/v1/session", json={"credential": "invalid"}).status_code == 401
        )
    limited = c.post("/api/v1/session", json={"credential": "invalid"})
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    health = c.get("/health/live")
    assert health.status_code == 200
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert c.get("/health/ready").status_code == 200
    assert (
        c.post(
            "/api/v1/session",
            headers={"Content-Length": str(18 * 1024 * 1024)},
            content=b"{}",
        ).status_code
        == 413
    )


def test_upload_retry_and_invalid_file(api):
    c = api["client"]
    _, _, _, version, artifact = dataset(api)
    from test_phase2_submission_platform import ALERTS

    retry = c.post(
        f"/api/v1/versions/{version['id']}/artifacts?category=alerts",
        headers=headers(api, key="alerts"),
        files={"file": ("alerts.csv", ALERTS, "text/csv")},
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == artifact["id"]
    assert "storage_key" not in retry.json()
    bad = c.post(
        f"/api/v1/versions/{version['id']}/artifacts?category=cases",
        headers=headers(api, key="bad"),
        files={"file": ("../cases.csv", b"invalid", "text/csv")},
    )
    assert bad.status_code == 422
    assert c.post(
        f"/api/v1/versions/{version['id']}/artifacts?category=alerts",
        headers=headers(api, "outsider", "foreign"),
        files={"file": ("alerts.csv", ALERTS, "text/csv")},
    ).status_code in {403, 404}

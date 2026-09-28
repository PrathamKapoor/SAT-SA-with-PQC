"""Authentication, session and role authorization checks for the hosted API.

The expected matrix below is the documented contract
(docs/security/AUTHORIZATION_MATRIX.md); every route in the OpenAPI schema
must appear in it, so a new route cannot ship without an explicit decision.
"""

import io
import time

import pytest
from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]

ALL = {"viewer", "analyst", "supervisor", "auditor", "admin"}
WRITERS = {"analyst", "supervisor", "admin"}
REVIEWERS = {"supervisor", "admin"}

# (method, path) -> roles allowed in the organization; None = no tenant role
# (session routes, organization discovery; see the matrix document).
MATRIX = {
    ("POST", "/api/v1/session"): None,
    ("GET", "/api/v1/session"): None,
    ("DELETE", "/api/v1/session"): None,
    ("GET", "/api/v1/organizations"): None,
    ("POST", "/api/v1/organizations"): {"admin"},
    ("GET", "/api/v1/members"): {"admin"},
    ("POST", "/api/v1/members"): {"admin"},
    ("DELETE", "/api/v1/members/{user_id}"): {"admin"},
    ("GET", "/api/v1/entities"): ALL,
    ("POST", "/api/v1/entities"): WRITERS,
    ("GET", "/api/v1/entities/{entity_id}"): ALL,
    ("GET", "/api/v1/assessments"): ALL,
    ("POST", "/api/v1/assessments"): WRITERS,
    ("GET", "/api/v1/assessments/{assessment_id}"): ALL,
    ("GET", "/api/v1/submissions"): ALL,
    ("POST", "/api/v1/submissions"): WRITERS,
    ("GET", "/api/v1/submissions/{submission_id}"): ALL,
    ("POST", "/api/v1/submissions/{submission_id}/versions"): WRITERS,
    ("GET", "/api/v1/submissions/{submission_id}/versions"): ALL,
    ("GET", "/api/v1/versions/{version_id}"): ALL,
    ("POST", "/api/v1/versions/{version_id}/artifacts"): WRITERS,
    ("GET", "/api/v1/versions/{version_id}/artifacts"): ALL,
    ("GET", "/api/v1/artifacts/{artifact_id}"): ALL,
    ("POST", "/api/v1/versions/{version_id}/complete"): WRITERS,
    ("POST", "/api/v1/versions/{version_id}/validate"): WRITERS,
    ("GET", "/api/v1/versions/{version_id}/validation"): ALL,
    ("GET", "/api/v1/versions/{version_id}/summary"): ALL,
    ("GET", "/api/v1/versions/{version_id}/records"): ALL,
    ("POST", "/api/v1/runs"): WRITERS,
    ("GET", "/api/v1/runs"): ALL,
    ("GET", "/api/v1/runs/{run_id}"): ALL,
    ("POST", "/api/v1/runs/{run_id}/cancel"): REVIEWERS,
    ("GET", "/api/v1/runs/{run_id}/steps"): ALL,
    ("GET", "/api/v1/runs/{run_id}/findings"): ALL,
    ("GET", "/api/v1/findings/{finding_id}"): ALL,
    ("GET", "/api/v1/runs/{run_id}/evidence"): ALL,
    ("GET", "/api/v1/runs/{run_id}/risk"): ALL,
    ("GET", "/api/v1/priorities"): ALL,
    ("GET", "/api/v1/runs/{run_id}/recommendations"): ALL,
    ("POST", "/api/v1/runs/{run_id}/decision"): REVIEWERS,
    ("GET", "/api/v1/runs/{run_id}/decision"): ALL,
    ("GET", "/api/v1/runs/{run_id}/receipt"): ALL,
    ("POST", "/api/v1/runs/{run_id}/verify"): ALL,
    ("GET", "/api/v1/audit/events"): {"auditor", "admin"},
}
PUBLIC = {("GET", "/health/live"), ("GET", "/health/ready"), ("POST", "/api/v1/session")}


def api_routes(app):
    for route in app.routes:
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            if route.path.startswith(("/api/", "/health/")):
                yield method, route.path


def test_every_route_has_an_explicit_authorization_decision(api):
    routes = set(api_routes(api["client"].app))
    assert routes - PUBLIC == set(MATRIX) - PUBLIC, "update MATRIX and the matrix document"


def test_every_non_public_route_requires_authentication(api):
    c = api["client"]
    for method, path in api_routes(c.app):
        if (method, path) in PUBLIC:
            continue
        url = path.replace("{", "x").replace("}", "")
        for auth in [None, "Bearer ", "Bearer not-a-credential", "Basic YTpi",
                     "Bearer " + "A" * 4096]:
            h = {"X-Organization-ID": api["org"]}
            if auth:
                h["Authorization"] = auth
            response = c.request(method, url, headers=h, json={})
            assert response.status_code == 401, (method, path, auth, response.text)
            assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"


@pytest.fixture
def world(api):
    """An organization with a run awaiting review and a queued run."""
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    entity, assessment, submission, version, artifact = dataset(api)
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    ).json()["id"]
    worker = AnalysisExecutionWorker(
        api["db"], worker_id="authz", audit=api["audit"], trust_key_dir=str(api["keys"])
    )
    assert worker.run_once() == "awaiting_review"
    queued = c.post(
        "/api/v1/runs",
        headers=headers(api, key="queued"),
        json={"submission_version_id": version["id"], "execution_mode": "graph"},
    ).json()["id"]
    finding = c.get(f"/api/v1/runs/{run}/findings", headers=headers(api)).json()["items"][0]
    member = next(
        m for m in c.get("/api/v1/members", headers=headers(api, "admin")).json()["items"]
        if m["name"] == "viewer"
    )
    fresh = c.post(
        "/api/v1/submissions/" + submission["id"] + "/versions",
        headers=headers(api, key="fresh"),
    ).json()["id"]
    return {
        "entity_id": entity["id"], "assessment_id": assessment["id"],
        "submission_id": submission["id"], "version_id": version["id"],
        "artifact_id": artifact["id"], "run_id": run, "queued": queued,
        "finding_id": finding["id"], "user_id": member["id"], "fresh": fresh,
    }


def call(api, role, method, path, w):
    """Issue a well-formed request so only authorization can refuse it."""
    from test_phase2_submission_platform import ALERTS

    c = api["client"]
    h = headers(api, role, key=f"{role}-{method}-{path}"[:128])
    url = path.format(**w).replace("{user_id}", w["user_id"])
    body = None
    files = None
    if (method, path) == ("POST", "/api/v1/entities"):
        body = {"display_name": "Matrix"}
    elif (method, path) == ("POST", "/api/v1/assessments"):
        body = {"entity_id": w["entity_id"], "period_start": 1, "period_end": 2}
    elif (method, path) == ("POST", "/api/v1/submissions"):
        body = {"assessment_id": w["assessment_id"]}
    elif (method, path) == ("POST", "/api/v1/versions/{version_id}/artifacts"):
        url = f"/api/v1/versions/{w['fresh']}/artifacts?category=alerts"
        files = {"file": ("alerts.csv", io.BytesIO(ALERTS), "text/csv")}
    elif path.startswith("/api/v1/versions/{version_id}/") and method == "POST":
        url = url.replace(w["version_id"], w["fresh"])
    elif (method, path) == ("POST", "/api/v1/runs"):
        body = {"submission_version_id": w["version_id"]}
    elif (method, path) == ("POST", "/api/v1/runs/{run_id}/cancel"):
        url = f"/api/v1/runs/{w['queued']}/cancel"
    elif (method, path) == ("POST", "/api/v1/runs/{run_id}/decision"):
        body = {"action": "confirm", "reason": "matrix"}
    elif (method, path) == ("POST", "/api/v1/members"):
        body = {"name": f"m-{role}", "email": f"m-{role}@example.test", "role": "satsa_viewer"}
    elif (method, path) == ("POST", "/api/v1/organizations"):
        body = {"name": f"org by {role}"}
    return c.request(method, url, headers=h, json=body, files=files)


@pytest.mark.parametrize("role", sorted(ALL))
def test_role_matrix_over_every_tenant_route(api, world, role):
    for (method, path), allowed in MATRIX.items():
        if allowed is None or (method, path) == ("DELETE", "/api/v1/members/{user_id}"):
            continue
        response = call(api, role, method, path, world)
        if role in allowed:
            # Allowed: past authorization (404 = no decision/receipt yet).
            assert response.status_code < 400 or response.status_code == 404, (
                role, method, path, response.text)
        else:
            assert response.status_code == 403, (role, method, path, response.text)
            assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    # Revocation last: it would otherwise remove a member other checks use.
    revoke = call(api, role, "DELETE", "/api/v1/members/{user_id}", world)
    assert revoke.status_code == (204 if role == "admin" else 403), revoke.text


def test_revoked_or_expired_sessions_and_disabled_identities_are_rejected(api):
    c = api["client"]
    token = c.post("/api/v1/session", json={"credential": api["tokens"]["analyst"]}).json()
    session_token = c.cookies.get("satsa_api_session")
    bearer = {"Authorization": f"Bearer {session_token}", "X-Organization-ID": api["org"]}
    assert c.get("/api/v1/entities", headers=bearer).status_code == 200
    # Deliberate logout revokes the server-side session for every transport.
    assert c.delete("/api/v1/session", headers={"X-CSRF-Token": token["csrf_token"]}).status_code == 204
    assert c.get("/api/v1/entities", headers=bearer).status_code == 401
    c.cookies.clear()

    # Disabled user: every session and the credential stop working.
    token = c.post("/api/v1/session", json={"credential": api["tokens"]["viewer"]}).json()
    session_token = c.cookies.get("satsa_api_session")
    c.cookies.clear()
    api["db"].execute("UPDATE satsa_users SET status='disabled' WHERE id=?", (token["user_id"],))
    for credential in [session_token, api["tokens"]["viewer"]]:
        h = {"Authorization": f"Bearer {credential}", "X-Organization-ID": api["org"]}
        assert c.get("/api/v1/session", headers=h).status_code == 401

    # Revoked identity: same outcome.
    login = c.post("/api/v1/session", json={"credential": api["tokens"]["auditor"]}).json()
    session_token = c.cookies.get("satsa_api_session")
    c.cookies.clear()
    api["identities"].revoke(login["identity_id"], reason="test")
    for credential in [session_token, api["tokens"]["auditor"]]:
        h = {"Authorization": f"Bearer {credential}", "X-Organization-ID": api["org"]}
        assert c.get("/api/v1/session", headers=h).status_code == 401

    # Expired session presented as a bearer token.
    c.post("/api/v1/session", json={"credential": api["tokens"]["supervisor"]})
    session_token = c.cookies.get("satsa_api_session")
    c.cookies.clear()
    api["db"].execute("UPDATE satsa_sessions SET expires_at=?", (time.time() - 1,))
    h = {"Authorization": f"Bearer {session_token}", "X-Organization-ID": api["org"]}
    assert c.get("/api/v1/session", headers=h).status_code == 401


def test_cookie_sessions_require_csrf_for_every_mutation(api):
    c = api["client"]
    login = c.post("/api/v1/session", json={"credential": api["tokens"]["admin"]}).json()
    h = {"X-Organization-ID": api["org"]}
    valid = login["csrf_token"]
    altered = valid[:-1] + ("1" if valid[-1] == "0" else "0")
    for token in [None, "", "0" * 64, altered]:
        extra = {} if token is None else {"X-CSRF-Token": token}
        response = c.post("/api/v1/entities", headers={**h, **extra}, json={"display_name": "csrf"})
        assert response.status_code == 403, response.text
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_entities WHERE display_name='csrf'"
    )["n"] == 0
    ok = c.post(
        "/api/v1/entities",
        headers={**h, "X-CSRF-Token": login["csrf_token"]},
        json={"display_name": "csrf"},
    )
    assert ok.status_code == 201, ok.text


def test_failed_logins_do_not_distinguish_credential_states(api):
    c = api["client"]
    valid = api["tokens"]["viewer"]
    key_id, secret = valid.split(".", 1)
    answers = set()
    # Unknown key, known key with wrong secret, malformed, oversized.
    for credential in ["unknown.secret", f"{key_id}.{secret[::-1]}", "a", "x" * 512]:
        response = c.post("/api/v1/session", json={"credential": credential})
        assert response.status_code == 401, response.text
        answers.add(response.json()["error"]["message"])
    assert len(answers) == 1, answers
    assert c.post("/api/v1/session", json={"credential": "x" * 513}).status_code == 422

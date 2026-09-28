"""Adversarial cross-organization tests over every hosted object path.

Organization A holds a complete, reviewed and TRUST-SAT finalized run.
Organization B's administrator (every permission, but only in B) and A's own
users with a forged organization header then try to read, mutate, enumerate
and replay A's objects. Every attempt must be refused without disclosing A's
data, and A's recorded state must be unchanged afterwards.
"""

import io

import pytest
from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]

# Tables whose organization-scoped row counts must not change under attack.
SCOPED_TABLES = [
    "satsa_entities",
    "satsa_assessments",
    "satsa_submissions",
    "satsa_submission_versions",
    "satsa_artifacts",
    "satsa_validation_reports",
    "satsa_version_records",
    "satsa_runs",
    "satsa_execution_jobs",
    "satsa_run_context",
    "satsa_run_risk",
    "satsa_run_recommendations",
    "satsa_run_review_decisions",
    "satsa_trust_finalizations",
    "satsa_memberships",
]


@pytest.fixture
def victim(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    entity, assessment, submission, version, artifact = dataset(api)
    run = c.post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    ).json()["id"]
    worker = AnalysisExecutionWorker(
        api["db"], worker_id="victim", audit=api["audit"], trust_key_dir=str(api["keys"])
    )
    assert worker.run_once() == "awaiting_review"
    decided = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Examined evidence"},
    )
    assert decided.status_code == 201, decided.text
    assert worker.run_once() in {"completed", "partial"}
    finding = c.get(f"/api/v1/runs/{run}/findings", headers=headers(api)).json()
    assert finding["items"], "the victim run must produce findings to attack"
    members = c.get("/api/v1/members", headers=headers(api, "admin")).json()["items"]
    return {
        "entity": entity["id"],
        "assessment": assessment["id"],
        "submission": submission["id"],
        "version": version["id"],
        "artifact": artifact["id"],
        "run": run,
        "finding": finding["items"][0]["id"],
        "members": {m["name"]: m["id"] for m in members},
        "secret_names": [entity["display_name"], artifact["original_filename"]],
    }


def snapshot(api):
    db, org = api["db"], api["org"]
    counts = {
        table: db.query_one(
            f"SELECT COUNT(*) AS n FROM {table} WHERE organization_id=?", (org,)
        )["n"]
        for table in SCOPED_TABLES
    }
    counts["active_members"] = db.query_one(
        "SELECT COUNT(*) AS n FROM satsa_memberships WHERE organization_id=? AND status='active'",
        (org,),
    )["n"]
    counts["runs"] = db.query_all(
        "SELECT id,status FROM satsa_runs WHERE organization_id=? ORDER BY id", (org,)
    )
    counts["versions"] = db.query_all(
        "SELECT id,status FROM satsa_submission_versions WHERE organization_id=? ORDER BY id",
        (org,),
    )
    return counts


def refused(response, victim):
    assert response.status_code in {403, 404, 422}, (response.status_code, response.text)
    body = response.text
    for secret in victim["secret_names"]:
        assert secret not in body, f"refusal disclosed {secret!r}"
    assert "error" in response.json()


def read_paths(v):
    return [
        f"entities/{v['entity']}",
        f"assessments/{v['assessment']}",
        f"submissions/{v['submission']}",
        f"submissions/{v['submission']}/versions",
        f"versions/{v['version']}",
        f"versions/{v['version']}/artifacts",
        f"versions/{v['version']}/validation",
        f"versions/{v['version']}/summary",
        f"versions/{v['version']}/records",
        f"artifacts/{v['artifact']}",
        f"runs/{v['run']}",
        f"runs/{v['run']}/steps",
        f"runs/{v['run']}/findings",
        f"runs/{v['run']}/evidence",
        f"runs/{v['run']}/risk",
        f"runs/{v['run']}/recommendations",
        f"runs/{v['run']}/decision",
        f"runs/{v['run']}/receipt",
        f"findings/{v['finding']}",
        f"assessments?entity_id={v['entity']}",
        f"submissions?entity_id={v['entity']}",
        f"runs?entity_id={v['entity']}",
    ]


def mutation_attempts(api, v, h):
    c = api["client"]
    from test_phase2_submission_platform import ALERTS

    def keyed(key):
        return {**h, "Idempotency-Key": key}

    return {
        "assessment on foreign entity": c.post(
            "/api/v1/assessments",
            headers=h,
            json={"entity_id": v["entity"], "period_start": 1, "period_end": 2},
        ),
        "submission on foreign assessment": c.post(
            "/api/v1/submissions",
            headers=keyed("submission"),
            json={"assessment_id": v["assessment"]},
        ),
        "version on foreign submission": c.post(
            f"/api/v1/submissions/{v['submission']}/versions", headers=keyed("version")
        ),
        "upload to foreign version": c.post(
            f"/api/v1/versions/{v['version']}/artifacts?category=cases",
            headers=keyed("alerts"),
            files={"file": ("cases.csv", io.BytesIO(ALERTS), "text/csv")},
        ),
        "complete foreign version": c.post(
            f"/api/v1/versions/{v['version']}/complete", headers=h
        ),
        "validate foreign version": c.post(
            f"/api/v1/versions/{v['version']}/validate", headers=h
        ),
        "run on foreign version": c.post(
            "/api/v1/runs",
            headers=keyed("run"),
            json={"submission_version_id": v["version"]},
        ),
        "cancel foreign run": c.post(f"/api/v1/runs/{v['run']}/cancel", headers=h),
        "decide foreign run": c.post(
            f"/api/v1/runs/{v['run']}/decision",
            headers=h,
            json={"action": "reject", "reason": "hostile"},
        ),
        "verify foreign run": c.post(f"/api/v1/runs/{v['run']}/verify", headers=h),
        "revoke foreign member": c.delete(
            f"/api/v1/members/{v['members']['analyst']}", headers=h
        ),
    }


def test_foreign_administrator_cannot_read_or_mutate_any_object(api, victim):
    c = api["client"]
    attacker = headers(api, "outsider")
    before = snapshot(api)
    for path in read_paths(victim):
        refused(c.get(f"/api/v1/{path}", headers=attacker), victim)
    for name, response in mutation_attempts(api, victim, attacker).items():
        assert response.status_code in {403, 404, 422}, (name, response.text)
        refused(response, victim)
    assert snapshot(api) == before
    # The attacker's own organization gained nothing either.
    other = api["other"]
    for table in SCOPED_TABLES[:-1]:
        assert api["db"].query_one(
            f"SELECT COUNT(*) AS n FROM {table} WHERE organization_id=?", (other,)
        )["n"] == 0, table
    # A's run still verifies and its decision is the supervisor's.
    assert c.post(
        f"/api/v1/runs/{victim['run']}/verify", headers=headers(api)
    ).json()["status"] == "verified"
    assert c.get(
        f"/api/v1/runs/{victim['run']}/decision", headers=headers(api)
    ).json()["action"] == "confirm"


def test_foreign_collections_and_audit_are_empty_for_the_attacker(api, victim):
    c = api["client"]
    attacker = headers(api, "outsider")
    for path in ["entities", "assessments", "submissions", "runs", "priorities"]:
        page = c.get(f"/api/v1/{path}", headers=attacker)
        assert page.status_code == 200, page.text
        assert page.json()["items"] == [], path
    members = c.get("/api/v1/members", headers=attacker).json()["items"]
    assert set(victim["members"].values()).isdisjoint({m["id"] for m in members})
    audit = c.get(f"/api/v1/audit/events?run_id={victim['run']}", headers=attacker)
    # A foreign run filter is refused like any foreign object.
    assert audit.status_code in {403, 404} or audit.json()["items"] == [], audit.text
    whole = c.get("/api/v1/audit/events?limit=200", headers=attacker).json()["items"]
    assert not any(victim["run"] in e["resource"] for e in whole)
    orgs = c.get("/api/v1/organizations", headers=attacker).json()["items"]
    assert [o["id"] for o in orgs] == [api["other"]]


@pytest.mark.parametrize("role", ["viewer", "analyst", "supervisor", "auditor", "admin"])
def test_forged_organization_header_is_refused_for_every_role(api, victim, role):
    """A's users cannot select B by header, nor reach A objects through B."""
    c = api["client"]
    forged = {**headers(api, role), "X-Organization-ID": api["other"]}
    for path in ["entities", "runs", "members", "audit/events", f"runs/{victim['run']}"]:
        response = c.get(f"/api/v1/{path}", headers=forged)
        assert response.status_code == 403, (path, response.text)
    for value in ["", "x" * 129, "' OR '1'='1", "../" + api["org"]]:
        response = c.get("/api/v1/entities", headers={**forged, "X-Organization-ID": value})
        assert response.status_code in {400, 403}, (value, response.text)


def test_same_idempotency_key_in_two_organizations_never_replays_across(api, victim):
    """Keys are scoped to the organization: B reusing A's keys creates B objects."""
    c = api["client"]
    b = headers(api, "outsider")
    entity = c.post("/api/v1/entities", headers=b, json={"display_name": "B bank"}).json()
    assessment = c.post(
        "/api/v1/assessments",
        headers=b,
        json={"entity_id": entity["id"], "period_start": 1700000000, "period_end": 1800000000},
    ).json()
    submission = c.post(
        "/api/v1/submissions",
        headers={**b, "Idempotency-Key": "submission"},
        json={"assessment_id": assessment["id"]},
    )
    assert submission.status_code == 201, submission.text
    assert submission.json()["id"] != victim["submission"]
    assert submission.json()["organization_id"] == api["other"]
    version = c.post(
        f"/api/v1/submissions/{submission.json()['id']}/versions",
        headers={**b, "Idempotency-Key": "version"},
    )
    assert version.status_code == 201, version.text
    assert version.json()["id"] != victim["version"]


def test_revoked_membership_is_listed_as_revoked_and_denied(api, victim):
    c = api["client"]
    analyst = victim["members"]["analyst"]
    assert c.delete(f"/api/v1/members/{analyst}", headers=headers(api, "admin")).status_code == 204
    members = c.get("/api/v1/members", headers=headers(api, "admin")).json()["items"]
    assert {m["id"]: m["status"] for m in members}[analyst] == "revoked"
    # The credential still authenticates, but grants nothing in the organization.
    assert c.get("/api/v1/session", headers=headers(api)).status_code == 200
    for path in ["entities", f"runs/{victim['run']}", f"findings/{victim['finding']}"]:
        assert c.get(f"/api/v1/{path}", headers=headers(api)).status_code == 403, path
    assert c.post(
        "/api/v1/entities", headers=headers(api), json={"display_name": "late"}
    ).status_code == 403


def test_administrator_cannot_revoke_own_membership(api):
    c = api["client"]
    me = c.get("/api/v1/session", headers=headers(api, "admin")).json()["user_id"]
    response = c.delete(f"/api/v1/members/{me}", headers=headers(api, "admin"))
    assert response.status_code == 422, response.text
    assert c.get("/api/v1/members", headers=headers(api, "admin")).status_code == 200


def test_unknown_and_malformed_identifiers_do_not_leak_existence(api, victim):
    c = api["client"]
    h = headers(api)
    for value in ["missing", "x" * 5000, "%00", "..%2F..%2Fetc%2Fpasswd", "' OR 1=1 --"]:
        for template in ["entities/{}", "runs/{}", "findings/{}", "versions/{}/records"]:
            response = c.get(f"/api/v1/{template.format(value)}", headers=h)
            assert response.status_code in {400, 403, 404, 422}, (template, value, response.text)
            assert "Traceback" not in response.text
            assert "SELECT" not in response.text.upper()
    # Foreign and missing objects answer alike for the attacker.
    attacker = headers(api, "outsider")
    foreign = c.get(f"/api/v1/runs/{victim['run']}", headers=attacker)
    missing = c.get("/api/v1/runs/run-does-not-exist", headers=attacker)
    assert foreign.status_code == missing.status_code
    assert foreign.json()["error"]["code"] == missing.json()["error"]["code"]


def test_nul_bytes_are_rejected_as_input_not_database_failures(api, victim):
    """PostgreSQL text cannot hold NUL: it must be a client error, never a 500."""
    c = api["client"]
    h = headers(api)
    nul = chr(0)
    for response in [
        c.get("/api/v1/entities/a%00b", headers=h),
        c.get("/api/v1/runs?entity_id=a%00b", headers=h),
        c.post("/api/v1/entities", headers=h, json={"display_name": f"bad{nul}name"}),
        c.post(
            f"/api/v1/runs/{victim['run']}/decision",
            headers=headers(api, "supervisor"),
            json={"action": "confirm", "reason": f"x{nul}y"},
        ),
    ]:
        assert response.status_code in {400, 422}, response.text
        assert response.json()["error"]["code"] in {"MALFORMED_REQUEST", "VALIDATION_ERROR"}

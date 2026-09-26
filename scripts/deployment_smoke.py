"""Exercise the deployed SAT-SA workflow through its public HTTP API."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


class SmokeFailure(RuntimeError):
    pass


def request(
    base: str,
    method: str,
    path: str,
    *,
    credential: str,
    organization: str | None = None,
    body=None,
    headers=None,
):
    request_headers = {"Authorization": f"Bearer {credential}"}
    if organization:
        request_headers["X-Organization-ID"] = organization
    if body is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode()
    request_headers.update(headers or {})
    req = urllib.request.Request(
        base + path, data=body, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise SmokeFailure(
            f"{method} {path} returned HTTP {exc.code}: {detail}"
        ) from exc


def assert_foreign_tenant_denied(base: str, path: str, credential: str) -> None:
    req = urllib.request.Request(
        base + path,
        headers={
            "Authorization": f"Bearer {credential}",
            "X-Organization-ID": f"org_foreign_{uuid.uuid4().hex}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            raise SmokeFailure("cross-tenant request unexpectedly succeeded")
    except urllib.error.HTTPError as exc:
        if exc.code not in {403, 404}:
            raise SmokeFailure(
                f"cross-tenant request returned HTTP {exc.code}"
            ) from exc


def main() -> int:
    base = os.environ.get("SATSA_SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    analyst = os.environ.get("SATSA_SMOKE_ANALYST_CREDENTIAL", "")
    supervisor = os.environ.get("SATSA_SMOKE_SUPERVISOR_CREDENTIAL", "")
    auditor = os.environ.get("SATSA_SMOKE_AUDITOR_CREDENTIAL", "")
    organization = os.environ.get("SATSA_SMOKE_ORGANIZATION_ID", "")
    if not all((analyst, supervisor, auditor, organization)):
        raise SmokeFailure(
            "set SATSA_SMOKE_ANALYST_CREDENTIAL, "
            "SATSA_SMOKE_SUPERVISOR_CREDENTIAL, SATSA_SMOKE_AUDITOR_CREDENTIAL, "
            "and SATSA_SMOKE_ORGANIZATION_ID"
        )

    _, live = request(base, "GET", "/health/live", credential=analyst)
    _, ready = request(base, "GET", "/health/ready", credential=analyst)
    if live.get("status") != "alive" or ready.get("status") != "ready":
        raise SmokeFailure("API liveness/readiness did not report healthy")

    # Validate each real bearer credential before any mutating workflow call.
    for credential in (analyst, supervisor, auditor):
        request(base, "GET", "/api/v1/organizations", credential=credential)
    orgs_status, orgs = request(
        base, "GET", "/api/v1/organizations", credential=analyst
    )
    if orgs_status != 200 or organization not in {item["id"] for item in orgs["items"]}:
        raise SmokeFailure("analyst is not a member of the configured organization")

    headers = {"Idempotency-Key": f"phase7-smoke-{uuid.uuid4().hex}"}
    _, entity = request(
        base,
        "POST",
        "/api/v1/entities",
        credential=analyst,
        organization=organization,
        body={"display_name": f"SAT-SA smoke {uuid.uuid4().hex[:8]}", "sector": "test"},
    )
    _, assessment = request(
        base,
        "POST",
        "/api/v1/assessments",
        credential=analyst,
        organization=organization,
        body={
            "entity_id": entity["id"],
            "period_start": 1735689600,
            "period_end": 1735776000,
        },
    )
    _, submission = request(
        base,
        "POST",
        "/api/v1/submissions",
        credential=analyst,
        organization=organization,
        body={"assessment_id": assessment["id"]},
        headers=headers,
    )
    _, version = request(
        base,
        "POST",
        f"/api/v1/submissions/{submission['id']}/versions",
        credential=analyst,
        organization=organization,
        headers={"Idempotency-Key": f"version-{uuid.uuid4().hex}"},
    )

    boundary = "SATSA" + uuid.uuid4().hex
    csv = (
        b"native_id,created_at,severity\n"
        b"SMOKE-001,1735689600,critical\n"
        b"SMOKE-002,1735693260,high\n"
        b"SMOKE-003,1735696920,medium\n"
    )
    multipart = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="alerts.csv"\r\nContent-Type: text/csv\r\n\r\n'
        ).encode()
        + csv
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        f"{base}/api/v1/versions/{version['id']}/artifacts?category=alerts",
        data=multipart,
        method="POST",
        headers={
            "Authorization": f"Bearer {analyst}",
            "X-Organization-ID": organization,
            "Idempotency-Key": f"artifact-{uuid.uuid4().hex}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            artifact = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SmokeFailure(f"artifact upload returned HTTP {exc.code}") from exc
    if artifact["storage_status"] != "stored":
        raise SmokeFailure("uploaded artifact was not durably stored")
    request(
        base,
        "POST",
        f"/api/v1/versions/{version['id']}/complete",
        credential=analyst,
        organization=organization,
    )
    _, validation = request(
        base,
        "POST",
        f"/api/v1/versions/{version['id']}/validate",
        credential=analyst,
        organization=organization,
    )
    if validation["status"] != "valid":
        raise SmokeFailure(f"smoke dataset validation failed: {validation['errors']}")
    _, run = request(
        base,
        "POST",
        "/api/v1/runs",
        credential=analyst,
        organization=organization,
        body={"submission_version_id": version["id"], "execution_mode": "graph"},
        headers={"Idempotency-Key": f"run-{uuid.uuid4().hex}"},
    )

    deadline = time.monotonic() + int(
        os.environ.get("SATSA_SMOKE_TIMEOUT_SECONDS", "600")
    )
    while time.monotonic() < deadline:
        _, run = request(
            base,
            "GET",
            f"/api/v1/runs/{run['id']}",
            credential=analyst,
            organization=organization,
        )
        if run["status"] == "awaiting_review":
            break
        if run["status"] in {"failed", "cancelled", "partial"}:
            raise SmokeFailure(
                f"analysis stopped in state {run['status']}: {run['error']}"
            )
        time.sleep(2)
    else:
        raise SmokeFailure("worker did not reach supervisory review before timeout")
    assert_foreign_tenant_denied(base, f"/api/v1/runs/{run['id']}", analyst)

    findings_status, findings = request(
        base,
        "GET",
        f"/api/v1/runs/{run['id']}/findings?limit=100",
        credential=analyst,
        organization=organization,
    )
    if findings_status != 200:
        raise SmokeFailure("finding query failed")
    if not findings["items"]:
        raise SmokeFailure("analysis produced no findings for the smoke dataset")
    _, risk = request(
        base,
        "GET",
        f"/api/v1/runs/{run['id']}/risk",
        credential=analyst,
        organization=organization,
    )
    if not risk:
        raise SmokeFailure("analysis produced no persisted risk result")
    _, recommendations = request(
        base,
        "GET",
        f"/api/v1/runs/{run['id']}/recommendations?limit=100",
        credential=analyst,
        organization=organization,
    )
    if not recommendations["items"]:
        raise SmokeFailure("analysis produced no recommendations for the smoke dataset")

    request(
        base,
        "POST",
        f"/api/v1/runs/{run['id']}/decision",
        credential=supervisor,
        organization=organization,
        body={"action": "confirm", "reason": "Phase 7 deployment smoke review"},
    )
    while time.monotonic() < deadline:
        _, run = request(
            base,
            "GET",
            f"/api/v1/runs/{run['id']}",
            credential=analyst,
            organization=organization,
        )
        if run["status"] == "completed":
            break
        if run["status"] in {"failed", "cancelled", "partial"}:
            raise SmokeFailure(
                f"post-review run ended in {run['status']}: {run['error']}"
            )
        time.sleep(2)
    else:
        raise SmokeFailure("run did not complete TRUST-SAT finalization before timeout")
    _, receipt = request(
        base,
        "GET",
        f"/api/v1/runs/{run['id']}/receipt",
        credential=analyst,
        organization=organization,
    )
    _, verification = request(
        base,
        "POST",
        f"/api/v1/runs/{run['id']}/verify",
        credential=analyst,
        organization=organization,
    )
    if verification["status"] != "verified":
        raise SmokeFailure(f"TRUST-SAT verification failed: {verification['status']}")
    _, audit = request(
        base,
        "GET",
        f"/api/v1/audit/events?limit=200&run_id={run['id']}",
        credential=auditor,
        organization=organization,
    )
    if not audit["items"]:
        raise SmokeFailure("no run audit events were available")

    print(
        json.dumps(
            {
                "status": "passed",
                "entity_id": entity["id"],
                "submission_id": submission["id"],
                "artifact_id": artifact["id"],
                "run_id": run["id"],
                "finding_count": len(findings["items"]),
                "receipt_id": receipt["id"],
                "verification": verification["status"],
                "audit_event_count": len(audit["items"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"deployment smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

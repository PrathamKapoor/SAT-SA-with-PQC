"""Exercise the deployed SAT-SA workflow through its public HTTP API.

Every step is recorded as a structured check (PASS / FAIL / NOT_RUN) with
its duration, the server's X-Request-ID and the run id where applicable.
A check is PASS only when it actually executed and its assertion held;
after the first failure every remaining check is NOT_RUN. The process exits
non-zero unless every check passed.

Credentials: set SATSA_SMOKE_ANALYST_CREDENTIAL, ..._SUPERVISOR_...,
..._AUDITOR_... and SATSA_SMOKE_ORGANIZATION_ID; or pass ``--provision``
with SATSA_SMOKE_ADMIN_CREDENTIAL and SATSA_SMOKE_ORGANIZATION_ID to invite
those three members first (this creates durable, audited test users).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any


class SmokeFailure(RuntimeError):
    pass


_LAST_REQUEST_ID: list[str | None] = [None]


def request(
    base: str,
    method: str,
    path: str,
    *,
    credential: str,
    organization: str | None = None,
    body=None,
    headers=None,
    data: bytes | None = None,
):
    request_headers = {"Authorization": f"Bearer {credential}"}
    if organization:
        request_headers["X-Organization-ID"] = organization
    if body is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request_headers.update(headers or {})
    req = urllib.request.Request(
        base + path, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            _LAST_REQUEST_ID[0] = response.headers.get("X-Request-ID")
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        _LAST_REQUEST_ID[0] = exc.headers.get("X-Request-ID") if exc.headers else None
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise SmokeFailure(
            f"{method} {path} returned HTTP {exc.code}: {detail}"
        ) from exc


class Checks:
    """Ordered structured check results; nothing is PASS unless it ran."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.failed = False
        self.context: dict[str, Any] = {}

    def run(self, name: str, step: Callable[[], dict[str, Any] | None]) -> None:
        entry: dict[str, Any] = {
            "check": name,
            "status": "NOT_RUN",
            "duration_seconds": None,
            "request_id": None,
            "run_id": None,
            "failure_reason": None,
        }
        self.results.append(entry)
        if self.failed:
            return
        _LAST_REQUEST_ID[0] = None
        started = time.monotonic()
        try:
            detail = step() or {}
        except Exception as exc:  # noqa: BLE001 - every failure becomes a record
            self.failed = True
            entry.update(
                status="FAIL",
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
        else:
            entry.update(status="PASS", **detail)
        entry["duration_seconds"] = round(time.monotonic() - started, 3)
        entry["request_id"] = _LAST_REQUEST_ID[0]

    def report(self) -> dict[str, Any]:
        counts = {
            status: sum(r["status"] == status for r in self.results)
            for status in ("PASS", "FAIL", "NOT_RUN")
        }
        return {
            "status": "passed" if counts["PASS"] == len(self.results) else "failed",
            "counts": counts,
            "checks": self.results,
        }


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
        _LAST_REQUEST_ID[0] = exc.headers.get("X-Request-ID") if exc.headers else None
        if exc.code not in {403, 404}:
            raise SmokeFailure(
                f"cross-tenant request returned HTTP {exc.code}"
            ) from exc


def provision_members(base: str, admin: str, organization: str) -> dict[str, str]:
    """Invite analyst, supervisor and auditor members; return credentials."""
    credentials = {}
    suffix = uuid.uuid4().hex[:8]
    for role in ("analyst", "supervisor", "auditor"):
        _, invitation = request(
            base,
            "POST",
            "/api/v1/members",
            credential=admin,
            organization=organization,
            body={
                "name": f"Smoke {role} {suffix}",
                "email": f"smoke-{role}-{suffix}@example.test",
                "role": f"satsa_{role}",
            },
        )
        credentials[role] = invitation["credential"]
    return credentials


def _wait_for(
    base: str,
    run_id: str,
    *,
    credential: str,
    organization: str,
    target: str,
    deadline: float,
) -> dict:
    while time.monotonic() < deadline:
        _, run = request(
            base,
            "GET",
            f"/api/v1/runs/{run_id}",
            credential=credential,
            organization=organization,
        )
        if run["status"] == target:
            return run
        if (
            run["status"] in {"failed", "cancelled", "partial"}
            and run["status"] != target
        ):
            raise SmokeFailure(f"run ended in {run['status']}: {run.get('error')}")
        time.sleep(2)
    raise SmokeFailure(f"run did not reach {target!r} before timeout")


def run_smoke(
    base: str,
    *,
    analyst: str,
    supervisor: str,
    auditor: str,
    organization: str,
    timeout_seconds: int,
) -> Checks:
    checks = Checks()
    state: dict[str, Any] = {}
    deadline = time.monotonic() + timeout_seconds

    def health():
        _, live = request(base, "GET", "/health/live", credential=analyst)
        if live.get("status") != "alive":
            raise SmokeFailure(f"liveness reported {live}")

    def readiness():
        _, ready = request(base, "GET", "/health/ready", credential=analyst)
        if ready.get("status") != "ready":
            raise SmokeFailure(f"readiness reported {ready}")

    def authentication():
        for credential in (analyst, supervisor, auditor):
            request(base, "GET", "/api/v1/organizations", credential=credential)

    def organization_access():
        _, orgs = request(base, "GET", "/api/v1/organizations", credential=analyst)
        if organization not in {item["id"] for item in orgs["items"]}:
            raise SmokeFailure("analyst is not a member of the configured organization")

    def entity_and_assessment():
        _, state["entity"] = request(
            base,
            "POST",
            "/api/v1/entities",
            credential=analyst,
            organization=organization,
            body={
                "display_name": f"SAT-SA smoke {uuid.uuid4().hex[:8]}",
                "sector": "test",
            },
        )
        _, state["assessment"] = request(
            base,
            "POST",
            "/api/v1/assessments",
            credential=analyst,
            organization=organization,
            body={
                "entity_id": state["entity"]["id"],
                "period_start": 1735689600,
                "period_end": 1735776000,
            },
        )

    def submission():
        _, state["submission"] = request(
            base,
            "POST",
            "/api/v1/submissions",
            credential=analyst,
            organization=organization,
            body={"assessment_id": state["assessment"]["id"]},
            headers={"Idempotency-Key": f"smoke-{uuid.uuid4().hex}"},
        )
        _, state["version"] = request(
            base,
            "POST",
            f"/api/v1/submissions/{state['submission']['id']}/versions",
            credential=analyst,
            organization=organization,
            headers={"Idempotency-Key": f"version-{uuid.uuid4().hex}"},
        )

    def upload():
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
        _, artifact = request(
            base,
            "POST",
            f"/api/v1/versions/{state['version']['id']}/artifacts?category=alerts",
            credential=analyst,
            organization=organization,
            data=multipart,
            headers={
                "Idempotency-Key": f"artifact-{uuid.uuid4().hex}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        if artifact["storage_status"] != "stored":
            raise SmokeFailure("uploaded artifact was not durably stored")
        state["artifact"] = artifact

    def validation():
        request(
            base,
            "POST",
            f"/api/v1/versions/{state['version']['id']}/complete",
            credential=analyst,
            organization=organization,
        )
        _, result = request(
            base,
            "POST",
            f"/api/v1/versions/{state['version']['id']}/validate",
            credential=analyst,
            organization=organization,
        )
        if result["status"] != "valid":
            raise SmokeFailure(f"validation failed: {result['errors']}")

    def analysis_run():
        _, state["run"] = request(
            base,
            "POST",
            "/api/v1/runs",
            credential=analyst,
            organization=organization,
            body={
                "submission_version_id": state["version"]["id"],
                "execution_mode": "graph",
            },
            headers={"Idempotency-Key": f"run-{uuid.uuid4().hex}"},
        )
        return {"run_id": state["run"]["id"]}

    def worker_review_checkpoint():
        state["run"] = _wait_for(
            base,
            state["run"]["id"],
            credential=analyst,
            organization=organization,
            target="awaiting_review",
            deadline=deadline,
        )
        return {"run_id": state["run"]["id"]}

    def tenant_isolation():
        assert_foreign_tenant_denied(
            base, f"/api/v1/runs/{state['run']['id']}", analyst
        )
        return {"run_id": state["run"]["id"]}

    def findings():
        _, page = request(
            base,
            "GET",
            f"/api/v1/runs/{state['run']['id']}/findings?limit=100",
            credential=analyst,
            organization=organization,
        )
        if not page["items"]:
            raise SmokeFailure("analysis produced no findings")
        state["finding_count"] = len(page["items"])
        return {"run_id": state["run"]["id"]}

    def risk():
        _, value = request(
            base,
            "GET",
            f"/api/v1/runs/{state['run']['id']}/risk",
            credential=analyst,
            organization=organization,
        )
        if not value:
            raise SmokeFailure("no persisted risk result")
        return {"run_id": state["run"]["id"]}

    def recommendations():
        _, page = request(
            base,
            "GET",
            f"/api/v1/runs/{state['run']['id']}/recommendations?limit=100",
            credential=analyst,
            organization=organization,
        )
        if not page["items"]:
            raise SmokeFailure("no recommendations")
        return {"run_id": state["run"]["id"]}

    def evidence_records():
        _, evidence = request(
            base,
            "GET",
            f"/api/v1/runs/{state['run']['id']}/evidence?limit=100",
            credential=analyst,
            organization=organization,
        )
        _, records = request(
            base,
            "GET",
            f"/api/v1/versions/{state['version']['id']}/records?limit=200",
            credential=analyst,
            organization=organization,
        )
        digests = {r["source_record_id"]: r["content_digest"] for r in records["items"]}
        for ref in evidence["items"]:
            if digests.get(ref["source_record_id"]) != ref["canonical_record_digest"]:
                raise SmokeFailure("cited evidence does not resolve to a record")
        return {"run_id": state["run"]["id"]}

    def priorities():
        _, page = request(
            base,
            "GET",
            "/api/v1/priorities?limit=200",
            credential=analyst,
            organization=organization,
        )
        if state["run"]["id"] not in {row["run_id"] for row in page["items"]}:
            raise SmokeFailure("analysed entity missing from the priority ranking")
        return {"run_id": state["run"]["id"]}

    def decision():
        request(
            base,
            "POST",
            f"/api/v1/runs/{state['run']['id']}/decision",
            credential=supervisor,
            organization=organization,
            body={"action": "confirm", "reason": "Deployment smoke review"},
        )
        return {"run_id": state["run"]["id"]}

    def trust_finalization():
        _wait_for(
            base,
            state["run"]["id"],
            credential=analyst,
            organization=organization,
            target="completed",
            deadline=deadline,
        )
        _, state["receipt"] = request(
            base,
            "GET",
            f"/api/v1/runs/{state['run']['id']}/receipt",
            credential=analyst,
            organization=organization,
        )
        return {"run_id": state["run"]["id"]}

    def verification():
        _, result = request(
            base,
            "POST",
            f"/api/v1/runs/{state['run']['id']}/verify",
            credential=analyst,
            organization=organization,
        )
        if result["status"] != "verified":
            raise SmokeFailure(f"TRUST-SAT verification returned {result['status']}")
        return {"run_id": state["run"]["id"]}

    def audit():
        _, page = request(
            base,
            "GET",
            f"/api/v1/audit/events?limit=200&run_id={state['run']['id']}",
            credential=auditor,
            organization=organization,
        )
        if not page["items"]:
            raise SmokeFailure("no run audit events")
        state["audit_event_count"] = len(page["items"])
        return {"run_id": state["run"]["id"]}

    for name, step in (
        ("health", health),
        ("readiness", readiness),
        ("authentication", authentication),
        ("organization_access", organization_access),
        ("entity_and_assessment", entity_and_assessment),
        ("submission", submission),
        ("upload", upload),
        ("validation", validation),
        ("analysis_run", analysis_run),
        ("worker_review_checkpoint", worker_review_checkpoint),
        ("tenant_isolation", tenant_isolation),
        ("findings", findings),
        ("risk", risk),
        ("recommendations", recommendations),
        ("evidence_records", evidence_records),
        ("priorities", priorities),
        ("decision", decision),
        ("trust_finalization", trust_finalization),
        ("verification", verification),
        ("audit", audit),
    ):
        checks.run(name, step)
    checks.context = {
        "run_id": state.get("run", {}).get("id"),
        "finding_count": state.get("finding_count"),
        "audit_event_count": state.get("audit_event_count"),
    }
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", help="write the JSON report to this path")
    parser.add_argument(
        "--provision",
        action="store_true",
        help="invite analyst/supervisor/auditor with SATSA_SMOKE_ADMIN_CREDENTIAL",
    )
    args = parser.parse_args(argv)
    base = os.environ.get("SATSA_SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    organization = os.environ.get("SATSA_SMOKE_ORGANIZATION_ID", "")
    if args.provision:
        admin = os.environ.get("SATSA_SMOKE_ADMIN_CREDENTIAL", "")
        if not (admin and organization):
            raise SmokeFailure(
                "--provision needs SATSA_SMOKE_ADMIN_CREDENTIAL and "
                "SATSA_SMOKE_ORGANIZATION_ID"
            )
        credentials = provision_members(base, admin, organization)
    else:
        credentials = {
            role: os.environ.get(f"SATSA_SMOKE_{role.upper()}_CREDENTIAL", "")
            for role in ("analyst", "supervisor", "auditor")
        }
    if not all(credentials.values()) or not organization:
        raise SmokeFailure(
            "set SATSA_SMOKE_ANALYST_CREDENTIAL, "
            "SATSA_SMOKE_SUPERVISOR_CREDENTIAL, SATSA_SMOKE_AUDITOR_CREDENTIAL, "
            "and SATSA_SMOKE_ORGANIZATION_ID (or use --provision)"
        )
    checks = run_smoke(
        base,
        organization=organization,
        timeout_seconds=int(os.environ.get("SATSA_SMOKE_TIMEOUT_SECONDS", "600")),
        **credentials,
    )
    report = {
        **checks.report(),
        "api_url": base,
        **checks.context,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    for row in report["checks"]:
        reason = f"  {row['failure_reason']}" if row["failure_reason"] else ""
        print(f"{row['check']:<26}{row['status']:<8}{reason}", file=sys.stderr)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"deployment smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

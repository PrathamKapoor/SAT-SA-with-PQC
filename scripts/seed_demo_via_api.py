"""Load the committed five-CSE demo through the SAT-SA HTTP API.

Every step is a real API call (the same sequence as the web ingest page):
entity, assessment period, submission, version, one upload per evidence
file, complete, validate, and an analysis run. The worker then computes
findings, risk, priorities and recommendations; nothing is precomputed.
Re-running reuses entities by name and the same idempotency keys, so it
does not create duplicates.

Usage:
    python scripts/seed_demo_via_api.py --api http://127.0.0.1:8000 \
        --credential <key_id.secret> --organization <organization id> [--wait]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEMO_ROOT = Path(
    os.environ.get("SATSA_DEMO_SUBMISSIONS")
    or Path(__file__).resolve().parents[1] / "docs" / "demo" / "submissions"
)
CATEGORIES = (
    "alerts",
    "cases",
    "investigation_steps",
    "escalations",
    "dispositions",
    "assets",
)
# The offline demo loader's values (satsa/ui/demo.py).
SECTOR, ENVIRONMENT = "defence", "on-prem"
PERIOD = (1735689600.0, 1738281600.0)


class Api:
    def __init__(self, base: str, credential: str, organization: str) -> None:
        self.base = base.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {credential}",
            "X-Organization-ID": organization,
            "Accept": "application/json",
        }

    def call(
        self,
        method: str,
        path: str,
        *,
        body=None,
        key: str | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
    ):
        headers = dict(self.headers)
        if key:
            headers["Idempotency-Key"] = key
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        # The API limits requests per client address; a limited request was
        # refused before it did anything, so waiting and resending it is safe.
        for attempt in range(6):
            request = urllib.request.Request(
                self.base + path, data=data, method=method, headers=headers
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                if exc.code == 429 and attempt < 5:
                    time.sleep(min(float(exc.headers.get("Retry-After") or 60), 65))
                    continue
                raise SystemExit(
                    f"{method} {path} failed: HTTP {exc.code} {detail}"
                ) from None

    def all(self, path: str) -> list[dict]:
        items, offset = [], 0
        while True:
            sep = "&" if "?" in path else "?"
            page = self.call("GET", f"{path}{sep}limit=200&offset={offset}")
            items += page["items"]
            if not page["has_more"]:
                return items
            offset += 200

    def upload(self, version_id: str, category: str, path: Path, key: str):
        boundary = uuid.uuid4().hex
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode()
            + path.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        return self.call(
            "POST",
            f"/api/v1/versions/{version_id}/artifacts?category={category}",
            data=body,
            key=key,
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def seed(api: Api, *, mode: str) -> list[str]:
    existing = {e["display_name"]: e for e in api.all("/api/v1/entities")}
    runs = []
    for cse_dir in sorted(p for p in DEMO_ROOT.iterdir() if p.is_dir()):
        name = cse_dir.name
        entity = existing.get(name) or api.call(
            "POST",
            "/api/v1/entities",
            body={
                "display_name": name,
                "sector": SECTOR,
                "environment_class": ENVIRONMENT,
            },
        )
        assessments = [
            a
            for a in api.all(f"/api/v1/assessments?entity_id={entity['id']}")
            if (a["period_start"], a["period_end"]) == PERIOD and a["status"] == "open"
        ]
        assessment = (
            assessments[0]
            if assessments
            else api.call(
                "POST",
                "/api/v1/assessments",
                body={
                    "entity_id": entity["id"],
                    "period_start": PERIOD[0],
                    "period_end": PERIOD[1],
                },
            )
        )
        submission = api.call(
            "POST",
            "/api/v1/submissions",
            body={"assessment_id": assessment["id"]},
            key=f"demo-{name}-submission",
        )
        version = api.call(
            "POST",
            f"/api/v1/submissions/{submission['id']}/versions",
            key=f"demo-{name}-version",
        )
        if version["status"] in ("created", "uploading"):
            for category in CATEGORIES:
                files = sorted(cse_dir.glob(f"{category}.*"))
                if files:
                    api.upload(
                        version["id"], category, files[0], f"demo-{name}-{category}"
                    )
            version = api.call("POST", f"/api/v1/versions/{version['id']}/complete")
        if version["status"] == "uploaded":
            report = api.call("POST", f"/api/v1/versions/{version['id']}/validate")
        else:
            report = api.call("GET", f"/api/v1/versions/{version['id']}/validation")
        if report["status"] != "valid":
            print(
                f"{name}: validation {report['status']}; not analysed", file=sys.stderr
            )
            continue
        run = api.call(
            "POST",
            "/api/v1/runs",
            body={"submission_version_id": version["id"], "execution_mode": mode},
            key=f"demo-{name}-run",
        )
        print(f"{name}: entity {entity['id']} run {run['id']} ({run['status']})")
        runs.append(run["id"])
    return runs


def wait(api: Api, runs: list[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    pending = set(runs)
    while pending and time.monotonic() < deadline:
        for run_id in list(pending):
            status = api.call("GET", f"/api/v1/runs/{run_id}")["status"]
            if status not in ("queued", "running", "cancel_requested"):
                print(f"run {run_id}: {status}")
                pending.discard(run_id)
        if pending:
            time.sleep(2)
    if pending:
        raise SystemExit(
            f"runs still processing after {timeout:.0f}s: {sorted(pending)} (is the worker running?)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True)
    parser.add_argument("--credential", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--mode", choices=("graph", "standard"), default="graph")
    parser.add_argument(
        "--wait", action="store_true", help="wait until the worker releases every run"
    )
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    api = Api(args.api, args.credential, args.organization)
    runs = seed(api, mode=args.mode)
    if args.wait:
        wait(api, runs, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

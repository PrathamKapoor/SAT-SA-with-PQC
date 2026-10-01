"""Create a fresh, clearly synthetic SAT-SA demo organization through the API.

A deliberate, repeatable demo path for a live deployment:

1. a new organization named "SAT-SA demo (synthetic data) <UTC time>",
   so demo records never mix with a real organization's records;
2. one analyst, supervisor, auditor and viewer in it (credentials printed
   once, as JSON, on stdout);
3. the committed five-CSE synthetic submissions loaded, validated and
   analysed by the worker (scripts/seed_demo_via_api.py, real API calls);
4. one supervisory decision recorded by the supervisor on a run awaiting
   review, and its TRUST-SAT receipt verified.

Reset: pass --previous-state with the state file of the last demo. Its demo
members are revoked, so its credentials stop working. Nothing is deleted:
supervisory records, decisions, receipts and audit history are immutable,
and the old demo organization stays inspectable by the administrator.

    python scripts/demo_environment.py --api http://api:8000 \
        --credential <administrator key_id.secret> [--previous-state old.json]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_demo_via_api import Api, seed, wait

NAME = "SAT-SA demo (synthetic data)"
ROLES = ("analyst", "supervisor", "auditor", "viewer")
DECISION_REASON = (
    "Demo decision on synthetic data: the execution-gap findings are consistent "
    "with the submitted cases, so the run's findings are confirmed for follow-up."
)


def create_demo(admin: Api, *, stamp: str) -> dict:
    admin.headers.pop("X-Organization-ID", None)  # not a tenant call
    org = admin.call("POST", "/api/v1/organizations", body={"name": f"{NAME} {stamp}"})
    admin.headers["X-Organization-ID"] = org["id"]
    members = {}
    # Identities are unique across the platform: each demo gets its own.
    tag = "".join(ch for ch in stamp if ch.isdigit())
    for role in ROLES:
        issued = admin.call(
            "POST",
            "/api/v1/members",
            body={
                "name": f"Demo {role} {stamp}",
                "email": f"demo-{role}-{tag}@satsa.invalid",
                "role": f"satsa_{role}",
            },
        )
        members[role] = {"user_id": issued["id"], "credential": issued["credential"]}
    return {"organization_id": org["id"], "organization_name": org["name"], "members": members}


def revoke_previous(admin: Api, state: dict) -> None:
    admin.headers["X-Organization-ID"] = state["organization_id"]
    for member in state["members"].values():
        try:
            admin.call("DELETE", f"/api/v1/members/{member['user_id']}")
        except SystemExit as exc:  # already revoked is fine; report anything else
            if "404" not in str(exc) and "409" not in str(exc):
                raise


def decide_and_verify(supervisor: Api, runs: list[str]) -> dict:
    for run_id in runs:
        if supervisor.call("GET", f"/api/v1/runs/{run_id}")["status"] != "awaiting_review":
            continue
        decision = supervisor.call(
            "POST",
            f"/api/v1/runs/{run_id}/decision",
            body={"action": "confirm", "reason": DECISION_REASON},
        )
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            status = supervisor.call("GET", f"/api/v1/runs/{run_id}")["status"]
            if status not in ("awaiting_review", "queued", "running", "resuming"):
                break
            time.sleep(2)
        verification = supervisor.call("POST", f"/api/v1/runs/{run_id}/verify")
        return {"run_id": run_id, "decision_id": decision["id"], "run_status": status,
                "verification": verification["status"]}
    raise SystemExit("no demo run reached awaiting_review; is the worker running?")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True)
    parser.add_argument("--credential", required=True, help="an administrator's credential")
    parser.add_argument("--previous-state", type=Path)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(argv)

    admin = Api(args.api, args.credential, "")
    if args.previous_state and args.previous_state.is_file():
        revoke_previous(admin, json.loads(args.previous_state.read_text(encoding="utf-8")))
    state = create_demo(admin, stamp=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    org = state["organization_id"]
    analyst = Api(args.api, state["members"]["analyst"]["credential"], org)
    # Progress goes to stderr: stdout carries only the final state JSON.
    with contextlib.redirect_stdout(sys.stderr):
        runs = seed(analyst, mode="graph")
        # The graph pauses at human review; wait() treats awaiting_review as released.
        wait(analyst, runs, args.timeout)
    supervisor = Api(args.api, state["members"]["supervisor"]["credential"], org)
    state["runs"] = runs
    state["decision"] = decide_and_verify(supervisor, runs)
    print(json.dumps(state))
    return 0 if state["decision"]["verification"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())

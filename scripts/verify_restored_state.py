"""Record, then re-check, an organization's recorded state across a restore.

Before a backup (or any risky operation), `record` prints a JSON snapshot on
stdout: every finished run with its TRUST-SAT verification status and the
counts of entities, runs and audit events. After the restore, `compare` reads
that snapshot on stdin and fails unless every run is still present, every run
that verified still verifies, and no count went down.

    python scripts/verify_restored_state.py record --api http://api:8000 \
        --credential <auditor or admin key_id.secret> --organization <id> > before.json
    python scripts/verify_restored_state.py compare --api http://api:8000 \
        --credential ... --organization <id> < before.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def call(args, method: str, path: str) -> dict:
    request = urllib.request.Request(
        args.api.rstrip("/") + path,
        method=method,
        headers={
            "Authorization": f"Bearer {args.credential}",
            "X-Organization-ID": args.organization,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path}: HTTP {exc.code}") from None


def collect(args, path: str) -> list[dict]:
    items, offset = [], 0
    while True:
        separator = "&" if "?" in path else "?"
        page = call(args, "GET", f"{path}{separator}limit=200&offset={offset}")
        items += page["items"]
        if not page["has_more"]:
            return items
        offset += len(page["items"])


def snapshot(args) -> dict:
    runs = {}
    for run in collect(args, "/api/v1/runs"):
        if run["status"] in {"completed", "partial"}:
            runs[run["id"]] = call(args, "POST", f"/api/v1/runs/{run['id']}/verify")["status"]
    return {
        "runs": runs,
        "counts": {
            "entities": len(collect(args, "/api/v1/entities")),
            "runs": len(collect(args, "/api/v1/runs")),
            "audit_events": len(collect(args, "/api/v1/audit/events")),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["record", "compare"])
    parser.add_argument("--api", required=True)
    parser.add_argument("--credential", required=True,
                        help="an auditor's or administrator's credential (audit events are counted)")
    parser.add_argument("--organization", required=True)
    args = parser.parse_args(argv)
    current = snapshot(args)
    if args.mode == "record":
        if not any(status == "verified" for status in current["runs"].values()):
            raise SystemExit("no verified run to check after the restore")
        print(json.dumps(current, sort_keys=True))
        return 0
    before = json.load(sys.stdin)
    problems = []
    for run_id, status in before["runs"].items():
        after = current["runs"].get(run_id)
        if after is None:
            problems.append(f"run {run_id} missing after restore")
        elif status == "verified" and after != "verified":
            problems.append(f"run {run_id} was verified, now {after}")
    for name, count in before["counts"].items():
        if current["counts"][name] < count:
            problems.append(f"{name}: {count} before, {current['counts'][name]} after")
    for problem in problems:
        print(problem, file=sys.stderr)
    verified = sum(1 for status in current["runs"].values() if status == "verified")
    print(json.dumps({"verified_runs": verified, "counts": current["counts"], "problems": len(problems)}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

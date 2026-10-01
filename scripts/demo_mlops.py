"""Drive the full MLOps lifecycle on a demo organization through the API.

Runs against the organization created by scripts/demo_environment.py (its
state file supplies the analyst and supervisor credentials). Every step is a
real API call processed by the worker; nothing is precomputed:

1. more assessment periods for the five synthetic CSEs, analysed by the worker,
   so that there are enough supervisory decisions to learn from;
2. the synthetic supervisor decides every run with a stated rule: confirm a run
   with at least five signal findings, dismiss one with fewer (every synthetic
   CSE produces some signals, so "any signal" would give a single class, which
   dataset validation rightly refuses);
3. dataset from the recorded decisions -> validation -> training (analyst) ->
   evaluation and passport -> approval and deployment (supervisor, a different
   person from the trainer) -> inference on a new run -> drift check ->
   retraining request -> a second model version -> rollback to the first.

Prints a JSON summary on stdout; progress goes to stderr.

    python scripts/demo_mlops.py --api http://api:8000 --state state.json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_demo_via_api import CATEGORIES, DEMO_ROOT, ENVIRONMENT, SECTOR, Api, wait

MONTH = 31 * 86400.0
FIRST_PERIOD = 1735689600.0  # the period demo_environment.py already analysed
CONFIRM_AT = 5
RULE = (
    f"Demo decision rule on synthetic data: runs with at least {CONFIRM_AT} signal "
    "findings are confirmed for follow-up; runs with fewer are dismissed."
)


def log(*parts) -> None:
    print(*parts, file=sys.stderr, flush=True)


def analyse_periods(analyst: Api, periods: int) -> list[str]:
    entities = {e["display_name"]: e for e in analyst.all("/api/v1/entities")}
    runs = []
    for k in range(1, periods + 1):
        start = FIRST_PERIOD + k * MONTH
        for cse_dir in sorted(p for p in DEMO_ROOT.iterdir() if p.is_dir()):
            name = cse_dir.name
            entity = entities.get(name) or analyst.call(
                "POST", "/api/v1/entities",
                body={"display_name": name, "sector": SECTOR, "environment_class": ENVIRONMENT},
            )
            entities[name] = entity
            tag = f"mlops-{name}-p{k}"
            existing = [
                a for a in analyst.all(f"/api/v1/assessments?entity_id={entity['id']}")
                if a["period_start"] == start
            ]
            assessment = existing[0] if existing else analyst.call(
                "POST", "/api/v1/assessments",
                body={"entity_id": entity["id"], "period_start": start, "period_end": start + MONTH - 1},
            )
            submission = analyst.call("POST", "/api/v1/submissions",
                                      body={"assessment_id": assessment["id"]}, key=f"{tag}-submission")
            version = analyst.call("POST", f"/api/v1/submissions/{submission['id']}/versions",
                                   key=f"{tag}-version")
            if version["status"] in ("created", "uploading"):
                for category in CATEGORIES:
                    files = sorted(cse_dir.glob(f"{category}.*"))
                    if files:
                        analyst.upload(version["id"], category, files[0], f"{tag}-{category}")
                version = analyst.call("POST", f"/api/v1/versions/{version['id']}/complete")
            if version["status"] == "uploaded":
                analyst.call("POST", f"/api/v1/versions/{version['id']}/validate")
            run = analyst.call("POST", "/api/v1/runs",
                               body={"submission_version_id": version["id"], "execution_mode": "graph"},
                               key=f"{tag}-run")
            log(f"{name} period {k}: run {run['id']}")
            runs.append(run["id"])
    return runs


def decide_all(supervisor: Api, timeout: float) -> dict:
    counts = {"confirm": 0, "dismiss": 0}
    decided = []
    for run in supervisor.all("/api/v1/runs"):
        if run["status"] != "awaiting_review":
            continue
        findings = supervisor.all(f"/api/v1/runs/{run['id']}/findings")
        signals = sum(f.get("state") == "signal" for f in findings)
        action = "confirm" if signals >= CONFIRM_AT else "dismiss"
        supervisor.call("POST", f"/api/v1/runs/{run['id']}/decision",
                        body={"action": action, "reason": RULE})
        counts[action] += 1
        decided.append(run["id"])
    deadline = time.monotonic() + timeout
    while decided and time.monotonic() < deadline:
        decided = [r for r in decided
                   if supervisor.call("GET", f"/api/v1/runs/{r}")["status"] not in ("completed", "partial", "failed")]
        if decided:
            time.sleep(3)
    if decided:
        raise SystemExit(f"runs not finalized after decisions: {decided}")
    return counts


def settled(call) -> None:
    """Run a lifecycle transition; one that already happened (HTTP 409) is done."""
    try:
        call()
    except SystemExit as exc:
        if "HTTP 409" not in str(exc):
            raise
        log("already done:", str(exc)[:120])


def job(api: Api, job_id: str, timeout: float = 600) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = api.call("GET", f"/api/v1/ml/jobs/{job_id}")
        if current["status"] in ("completed", "failed", "cancelled"):
            return current
        time.sleep(3)
    raise SystemExit(f"ML job {job_id} still running after {timeout:.0f}s")


def train(analyst: Api, dataset_id: str, seed: int) -> dict:
    started = analyst.call("POST", "/api/v1/ml/training-runs",
                           body={"dataset_id": dataset_id, "seed": seed}, key=f"demo-train-{dataset_id}-{seed}")
    done = job(analyst, started["id"])
    if done["status"] != "completed":
        raise SystemExit(f"training failed: {done['error']}")
    run = next(r for r in analyst.all("/api/v1/ml/training-runs") if r["job_id"] == started["id"])
    return analyst.call("GET", f"/api/v1/ml/models/{run['model_id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--periods", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    state = json.loads(args.state.read_text(encoding="utf-8"))
    org = state["organization_id"]
    analyst = Api(args.api, state["members"]["analyst"]["credential"], org)
    supervisor = Api(args.api, state["members"]["supervisor"]["credential"], org)
    summary: dict = {"organization_id": org}

    with contextlib.redirect_stdout(sys.stderr):
        runs = analyse_periods(analyst, args.periods)
        wait(analyst, runs, args.timeout)
    summary["analysed_runs"] = len(runs)
    summary["decisions"] = decide_all(supervisor, args.timeout)
    log("decisions", summary["decisions"])

    dataset = analyst.call("POST", "/api/v1/ml/datasets",
                           body={"name": "review-outcome", "data_origin": "synthetic"})
    # Identical content returns the existing (possibly already validated) version.
    validation = job(analyst, analyst.call("POST", f"/api/v1/ml/datasets/{dataset['id']}/validate",
                                           key=f"demo-validate-{dataset['id']}")["id"])
    dataset = analyst.call("GET", f"/api/v1/ml/datasets/{dataset['id']}")
    summary["dataset"] = {"id": dataset["id"], "version": dataset["version"], "status": dataset["status"],
                          "record_count": dataset["record_count"], "labels": dataset["label_counts"],
                          "validation_job": validation["status"]}
    log("dataset", summary["dataset"])
    if dataset["status"] != "valid":
        print(json.dumps(summary))
        return 1

    first = train(analyst, dataset["id"], seed=7)
    summary["model_v1"] = {"id": first["id"], "version": first["version"], "state": first["state"],
                           "evaluation": first["passport"].get("evaluation"), "verification": first["passport"].get("verification")}
    log("model v1", summary["model_v1"])
    if first["state"] != "verified":
        print(json.dumps(summary))
        return 1
    settled(lambda: supervisor.call("POST", f"/api/v1/ml/models/{first['id']}/approve",
                    body={"justification": "Demo: passport and holdout metrics reviewed on synthetic data."}))
    settled(lambda: supervisor.call("POST", f"/api/v1/ml/models/{first['id']}/deploy",
                                    body={"reason": "Demo deployment"}))

    # A new run is scored by the deployed model (or abstains, with a reason).
    with contextlib.redirect_stdout(sys.stderr):
        scored = analyse_periods(analyst, args.periods + 1)[-5:]
        wait(analyst, scored, args.timeout)
    inference = supervisor.call("GET", f"/api/v1/runs/{scored[0]}/model-inference")
    summary["inference"] = {"run_id": scored[0], "status": inference.get("status"),
                            "model_id": inference.get("model_id"), "score": inference.get("score"),
                            "abstain_reason": inference.get("abstain_reason")}
    log("inference", summary["inference"])

    drift = job(analyst, analyst.call("POST", "/api/v1/ml/drift-checks", body={"window": 500},
                                      key=f"demo-drift-{first['id']}")["id"])
    summary["drift"] = drift.get("result")
    retraining = analyst.call("POST", "/api/v1/ml/retraining-requests",
                              body={"reason": "Demo: retraining proposed after new supervisory decisions."})
    summary["retraining_request"] = {"id": retraining["id"], "status": retraining["status"]}

    second = train(analyst, dataset["id"], seed=11)
    summary["model_v2"] = {"id": second["id"], "version": second["version"], "state": second["state"]}
    if second["state"] == "verified":
        settled(lambda: supervisor.call("POST", f"/api/v1/ml/models/{second['id']}/approve",
                        body={"justification": "Demo: second version reviewed on synthetic data."}))
        settled(lambda: supervisor.call("POST", f"/api/v1/ml/models/{second['id']}/deploy",
                                        body={"reason": "Demo upgrade"}))
        rollback = supervisor.call("POST", "/api/v1/ml/rollback",
                                   body={"target_model_id": first["id"], "reason": "Demo rollback to version 1"})
        active = [d for d in supervisor.all("/api/v1/ml/deployments") if d.get("active")]
        summary["rollback"] = {"deployment": rollback.get("id"),
                               "active_model": [d.get("model_id") for d in active]}
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

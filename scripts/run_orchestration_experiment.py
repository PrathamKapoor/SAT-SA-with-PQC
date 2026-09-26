"""Run the direct-vs-LangGraph overhead or recovery experiment."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.orchestration import (
    OVERHEAD_EXPERIMENT,
    RECOVERY_EXPERIMENT,
    RECOVERY_POINTS,
    run_orchestration_overhead_experiment,
    run_orchestration_recovery_experiment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure direct vs LangGraph orchestration on the hosted path"
    )
    parser.add_argument("kind", choices=("overhead", "recovery"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--experiment-id", type=str)
    parser.add_argument(
        "--trials",
        type=int,
        help="trials per mode (overhead, default 30) or per cell (recovery, default 3)",
    )
    parser.add_argument("--scenario", default="mixed")
    parser.add_argument("--seed", type=int, default=0, help="bootstrap seed")
    args = parser.parse_args(argv)
    experiment_id = args.experiment_id or (
        f"orchestration-{args.kind}-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    if (args.out / experiment_id).exists():
        parser.error(f"experiment bundle already exists: {experiment_id}")
    trials = args.trials or (30 if args.kind == "overhead" else 3)
    dataset = {
        "id": f"controlled-orchestration-{args.scenario}",
        "version": "1.0",
        "data_origin": "synthetic",
        "base_fixture": f"satsa.analysis.compval.SCENARIO_MAP[{args.scenario!r}]",
        "scope": "fresh isolated SQLite tenant per workflow run",
    }
    if args.kind == "overhead":
        config = {
            "experiment": OVERHEAD_EXPERIMENT,
            "modes": ["direct", "graph", "direct_unreviewed"],
            "trials_per_mode": trials,
            "warm_up_runs_per_mode": 1,
            "order_policy": "rotated per trial",
            "bootstrap": {"confidence": 0.95, "resamples": 10000, "seed": args.seed},
            "scenario": args.scenario,
        }
    else:
        config = {
            "experiment": RECOVERY_EXPERIMENT,
            "modes": ["direct", "graph"],
            "interruption_points": list(RECOVERY_POINTS),
            "trials_per_cell": trials,
            "scenario": args.scenario,
        }
    try:
        with tempfile.TemporaryDirectory(prefix="satsa-orchestration-") as scratch:
            if args.kind == "overhead":
                result = run_orchestration_overhead_experiment(
                    Path(scratch), trials=trials, scenario=args.scenario, seed=args.seed
                )
            else:
                result = run_orchestration_recovery_experiment(
                    Path(scratch), trials=trials, scenario=args.scenario
                )
    except Exception as exc:  # noqa: BLE001 - persist all experiment failures
        bundle = write_experiment_bundle(
            args.out,
            experiment_id=experiment_id,
            results=None,
            config=config,
            dataset=dataset,
            seed=args.seed,
            status="failed",
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
        print(json.dumps({"status": "failed", "bundle": str(bundle)}, indent=2))
        return 1
    bundle = write_experiment_bundle(
        args.out,
        experiment_id=experiment_id,
        results=result,
        config=config,
        dataset=dataset,
        seed=args.seed,
    )
    metrics = result["metrics"]
    summary = (
        {
            "analytics_identical": metrics["analytics_identical_across_modes"],
            "median_processing_seconds": {
                mode: value["processing_seconds"]["median"]
                for mode, value in metrics["per_mode"].items()
            },
        }
        if args.kind == "overhead"
        else {
            cell: {
                key: value[key]
                for key in (
                    "trials",
                    "recovered_to_completion",
                    "outputs_match_reference",
                )
            }
            for cell, value in metrics["summary"].items()
        }
    )
    print(
        json.dumps(
            {"status": result["status"], "bundle": str(bundle), "summary": summary},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

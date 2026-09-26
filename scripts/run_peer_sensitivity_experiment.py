"""Run a synthetic, isolated SAT-SA peer-cohort sensitivity experiment."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.peer import run_peer_sensitivity_experiment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run controlled peer-size and outlier-magnitude sweeps"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="root directory for immutable experiment bundles",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        help="bundle identifier; defaults to a UTC timestamp",
    )
    args = parser.parse_args()
    experiment_id = args.experiment_id or (
        "peer-sensitivity-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    dataset = {
        "id": "controlled-peer-cohorts",
        "version": "1.0",
        "data_origin": "synthetic",
        "scope": "isolated SQLite cohorts generated from declared closure times",
    }
    config = {
        "experiment": "peer-cohort-sensitivity-v1",
        "peer_counts": [2, 3, 4],
        "subject_closure_seconds": [30, 400, 750],
        "peer_closure_seconds": [300, 600, 900, 1200],
        "minimum_peers": 3,
        "deviation_threshold_mad_units": 2.0,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="satsa-peer-research-") as scratch:
            result = run_peer_sensitivity_experiment(Path(scratch))
    except Exception as exc:  # noqa: BLE001 - persist all experiment failures
        bundle = write_experiment_bundle(
            args.out,
            experiment_id=experiment_id,
            results=None,
            config=config,
            dataset=dataset,
            seed=None,
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
        seed=None,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "bundle": str(bundle),
                "cohort_size_sweep": [
                    {
                        "peer_count": row["peer_count"],
                        "finding_emitted": row["finding_emitted"],
                    }
                    for row in result["cohort_size_sweep"]
                ],
                "outlier_magnitude_sweep": [
                    {
                        "subject_closure_seconds": row["subject_closure_seconds"],
                        "finding_emitted": row["finding_emitted"],
                    }
                    for row in result["outlier_magnitude_sweep"]
                ],
                "limitations": result["limitations"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

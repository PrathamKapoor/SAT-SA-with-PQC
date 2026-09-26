"""P33 — controlled supervisory benchmark entry point.

Runs the versioned controlled benchmark
(``evaluation.controlled_benchmark``) against the real SAT-SA pipeline
and writes machine-readable results to an explicitly chosen output
directory (default: a fresh directory under the system temp dir, NEVER
a tracked source directory).

Usage:
    python scripts/run_controlled_benchmark.py --out <dir> [--seed 42]

All scratch state (DB, generated submissions, keys) lives beside the
output directory or in the system temp dir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.controlled_benchmark.manifest import build_manifest
from evaluation.controlled_benchmark.runner import (
    run_benchmark,
    write_results,
)
from evaluation.research.artifacts import write_experiment_bundle
from evaluation.workload.experiment import CLEAN_CONFIG, PATHOLOGICAL_CONFIG


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Controlled supervisory benchmark (synthetic, "
        "ground-truth-controlled; NOT real-data validation)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory for controlled-benchmark-results.json",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="workload population seed (default 42)"
    )
    parser.add_argument(
        "--population",
        type=int,
        default=10,
        help="workload population size (default 10)",
    )
    parser.add_argument(
        "--pathological",
        type=int,
        default=4,
        help="pathological entities in the workload population (default 4)",
    )
    parser.add_argument(
        "--random-trials",
        type=int,
        default=200,
        help="random-order baseline trials (default 200)",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        help="immutable artifact bundle ID; defaults to a UTC timestamp and seed",
    )
    parser.add_argument(
        "--no-ablation", action="store_true", help="skip the ablation section"
    )
    args = parser.parse_args()

    experiment_id = args.experiment_id or (
        "controlled-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-seed-{args.seed}"
    )
    bundle_root = args.out / "experiments"
    if (bundle_root / experiment_id).exists():
        parser.error(f"experiment bundle already exists: {experiment_id}")
    config = {
        "workload_seed": args.seed,
        "population": args.population,
        "pathological_entities": args.pathological,
        "random_trials": args.random_trials,
        "include_ablation": not args.no_ablation,
        "pathological_profile": PATHOLOGICAL_CONFIG,
        "clean_profile": CLEAN_CONFIG,
        "protocol": "controlled benchmark; isolated scratch SQLite; synthetic labels",
    }
    manifest = build_manifest(workload_seed=args.seed)
    manifest_digest = hashlib.sha256(
        json.dumps(
            manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    dataset = {
        "id": manifest["benchmark_name"],
        "version": manifest["benchmark_version"],
        "data_origin": "synthetic",
        "ground_truth_source": manifest["ground_truth_source"],
        "scenario_manifest_sha256": manifest_digest,
        "scope": "synthetic scenarios, constructed closure corpus, generated workload population",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="cbench-keys-") as scratch:
            keys = Path(scratch) / "keys"
            keys.mkdir()
            results = run_benchmark(
                trust_key_dir=keys,
                workload_seed=args.seed,
                n_population=args.population,
                n_pathological=args.pathological,
                n_random_trials=args.random_trials,
                include_ablation=not args.no_ablation,
            )
    except Exception as exc:
        write_experiment_bundle(
            bundle_root,
            experiment_id=experiment_id,
            results=None,
            config=config,
            dataset=dataset,
            seed=args.seed,
            status="failed",
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
        raise
    out_path = write_results(results, args.out)
    bundle_path = write_experiment_bundle(
        bundle_root,
        experiment_id=experiment_id,
        results=results,
        config=config,
        dataset=dataset,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "benchmark": results["benchmark_name"],
                "version": results["benchmark_version"],
                "results_file": str(out_path),
                "experiment_bundle": str(bundle_path),
                "metrics_summary": {
                    "scenario_corpus_micro": results["metrics"]["scenario_corpus"][
                        "micro"
                    ],
                    "action_alignment": results["metrics"]["scenario_corpus"][
                        "action_alignment"
                    ],
                    "coverage": results["metrics"]["scenario_corpus"]["coverage"][
                        "executed"
                    ],
                    "prioritization": results["metrics"]["prioritization"],
                },
                "limitations": results["limitations"][:2],
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

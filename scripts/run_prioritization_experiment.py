"""Run the seed-replicated prioritization comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.research.cli import default_experiment_id, run_and_bundle
from evaluation.research.prioritization import (
    DEFAULT_K_PERCENTAGES,
    EXPERIMENT_NAME,
    HEURISTICS,
    run_prioritization_experiment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--experiment-id", type=str)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--base-seed", type=int, default=100)
    parser.add_argument("--entities", type=int, default=20)
    parser.add_argument("--pathological", type=int, default=5)
    parser.add_argument("--random-trials", type=int, default=200)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args(argv)
    config = {
        "experiment": EXPERIMENT_NAME,
        "replicates": args.seeds,
        "seed_policy": "base_seed + replicate index",
        "base_seed": args.base_seed,
        "n_entities": args.entities,
        "n_pathological": args.pathological,
        "k_percentages": list(DEFAULT_K_PERCENTAGES),
        "methods": ["satsa", "random", *HEURISTICS],
        "random_trials_per_replicate": args.random_trials,
        "randomization_policy": "seeded per replicate",
        "confidence_level": 0.95,
        "bootstrap_seed": args.bootstrap_seed,
    }
    dataset = {
        "id": "generated-workload-populations",
        "version": "1.0",
        "data_origin": "synthetic",
        "generator": "evaluation.workload.build_population",
        "labels": "generator profile (pathological/clean) assigned before analysis",
    }
    return run_and_bundle(
        args.out,
        experiment_id=args.experiment_id or default_experiment_id("prioritization"),
        config=config,
        dataset=dataset,
        seed=args.base_seed,
        run=lambda scratch: run_prioritization_experiment(
            scratch,
            seeds=args.seeds,
            base_seed=args.base_seed,
            n_entities=args.entities,
            n_pathological=args.pathological,
            random_trials=args.random_trials,
            bootstrap_seed=args.bootstrap_seed,
        ),
        summarize=lambda result: {
            "recall@20%_median": {
                method: value["median"]
                for method, value in result["metrics"]["summary"]["recall@20%"].items()
            }
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())

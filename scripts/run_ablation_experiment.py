"""Run scenario- and population-level one-worker ablation."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.research.ablation import EXPERIMENT_NAME, run_ablation_experiment
from evaluation.research.cli import default_experiment_id, run_and_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--experiment-id", type=str)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--base-seed", type=int, default=300)
    parser.add_argument("--entities", type=int, default=20)
    parser.add_argument("--pathological", type=int, default=5)
    parser.add_argument("--k-percent", type=int, default=20)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--scenarios-only", action="store_true")
    args = parser.parse_args(argv)
    config = {
        "experiment": EXPERIMENT_NAME,
        "comparison": "full default worker set vs one worker removed",
        "population_seeds": 0 if args.scenarios_only else args.seeds,
        "base_seed": args.base_seed,
        "n_entities": args.entities,
        "n_pathological": args.pathological,
        "k_percent": args.k_percent,
        "bootstrap_seed": args.bootstrap_seed,
    }
    dataset = {
        "id": "catalog-scenarios-and-generated-populations",
        "version": "1.0",
        "data_origin": "synthetic",
        "labels": "catalog labels (scenario level); generator profiles (population level)",
    }
    return run_and_bundle(
        args.out,
        experiment_id=args.experiment_id or default_experiment_id("ablation"),
        config=config,
        dataset=dataset,
        seed=args.base_seed,
        run=lambda scratch: run_ablation_experiment(
            scratch,
            seeds=args.seeds,
            base_seed=args.base_seed,
            n_entities=args.entities,
            n_pathological=args.pathological,
            k_percent=args.k_percent,
            bootstrap_seed=args.bootstrap_seed,
            include_population=not args.scenarios_only,
        ),
        summarize=lambda result: {
            "scenario_full_micro": result["metrics"]["scenario_level"]["full"]["micro"],
            "workers_with_lost_families": [
                row["worker_removed"]
                for row in result["metrics"]["scenario_level"]["workers"]
                if row["lost_families_by_scenario"]
            ],
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())

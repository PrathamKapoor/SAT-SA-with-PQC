"""Run the isolated, synthetic imperfect-evidence (perturbation) experiment."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.robustness import (
    DEFAULT_RATES,
    DEFAULT_SEEDS,
    EXPERIMENT_NAME,
    run_evidence_robustness_experiment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a controlled SAT-SA imperfect-evidence experiment"
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
    parser.add_argument(
        "--scenarios",
        nargs="+",
        help="catalog scenario ids to perturb (default: every executable scenario)",
    )
    parser.add_argument(
        "--rates",
        nargs="+",
        type=float,
        default=list(DEFAULT_RATES),
        help="record omission rates (default: 0.10 0.25 0.50)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=DEFAULT_SEEDS,
        help="seeded omission replicates per rate (default: 5)",
    )
    parser.add_argument("--base-seed", type=int, default=0)
    args = parser.parse_args(argv)
    experiment_id = args.experiment_id or (
        "evidence-robustness-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    if (args.out / experiment_id).exists():
        parser.error(f"experiment bundle already exists: {experiment_id}")
    dataset = {
        "id": "controlled-evidence-perturbation",
        "version": "1.0",
        "data_origin": "synthetic",
        "base_fixtures": "satsa.analysis.compval.SCENARIO_MAP catalog scenarios",
        "scope": (
            "one isolated SQLite tenant per condition via hosted submission "
            "validation and analysis worker"
        ),
    }
    config = {
        "experiment": EXPERIMENT_NAME,
        "scenarios": args.scenarios,
        "omission_rates": args.rates,
        "seeds_per_rate": args.seeds,
        "base_seed": args.base_seed,
        "condition_families": {
            "missingness": ["omit_category", "omit_records", "omit_records_cascade"],
            "duplication": [
                "duplicate_exact",
                "duplicate_conflicting",
                "duplicate_near",
            ],
            "malformation": [
                "malformed_timestamp",
                "chronology_violation",
                "missing_required_column",
            ],
            "staleness": ["stale"],
            "conflict": ["conflict"],
        },
        "protocol": (
            "declare perturbation and expected validation before execution; "
            "submit each condition in its own scratch tenant; compare analyses "
            "with the paired unperturbed control"
        ),
    }
    try:
        with tempfile.TemporaryDirectory(
            prefix="satsa-robustness-research-"
        ) as scratch:
            result = run_evidence_robustness_experiment(
                Path(scratch),
                scenarios=tuple(args.scenarios) if args.scenarios else None,
                rates=tuple(args.rates),
                seeds=args.seeds,
                base_seed=args.base_seed,
            )
    except Exception as exc:  # noqa: BLE001 - persist all experiment failures
        bundle = write_experiment_bundle(
            args.out,
            experiment_id=experiment_id,
            results=None,
            config=config,
            dataset=dataset,
            seed=args.base_seed,
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
        seed=args.base_seed,
    )
    conformance = result["metrics"]["validation_contract_conformance"]
    print(
        json.dumps(
            {
                "status": result["status"],
                "bundle": str(bundle),
                "conditions_with_expectation": conformance[
                    "conditions_with_expectation"
                ],
                "validation_matches_expected": conformance["matches"],
                "record_omission_by_rate": {
                    key: {
                        name: value[name]
                        for name in (
                            "replicates",
                            "rejected_by_validation",
                            "completed_analyses",
                            "family_set_changed",
                        )
                    }
                    for key, value in result["metrics"][
                        "record_omission_by_rate"
                    ].items()
                },
                "limitations": result["limitations"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

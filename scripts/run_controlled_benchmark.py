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
import json
import tempfile
from pathlib import Path

from evaluation.controlled_benchmark.runner import (
    run_benchmark,
    write_results,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Controlled supervisory benchmark (synthetic, "
                    "ground-truth-controlled; NOT real-data validation)")
    parser.add_argument("--out", type=Path, required=True,
                        help="output directory for "
                             "controlled-benchmark-results.json")
    parser.add_argument("--seed", type=int, default=42,
                        help="workload population seed (default 42)")
    parser.add_argument("--population", type=int, default=10,
                        help="workload population size (default 10)")
    parser.add_argument("--pathological", type=int, default=4,
                        help="pathological entities in the workload "
                             "population (default 4)")
    parser.add_argument("--no-ablation", action="store_true",
                        help="skip the ablation section")
    args = parser.parse_args()

    keys = Path(tempfile.mkdtemp(prefix="cbench-keys-")) / "keys"
    keys.mkdir(parents=True, exist_ok=True)
    results = run_benchmark(
        trust_key_dir=keys,
        workload_seed=args.seed,
        n_population=args.population,
        include_ablation=not args.no_ablation,
    )
    out_path = write_results(results, args.out)
    print(json.dumps({
        "benchmark": results["benchmark_name"],
        "version": results["benchmark_version"],
        "results_file": str(out_path),
        "metrics_summary": {
            "scenario_corpus_micro": results["metrics"]["scenario_corpus"]
                                              ["micro"],
            "action_alignment": results["metrics"]["scenario_corpus"]
                                                ["action_alignment"],
            "coverage": results["metrics"]["scenario_corpus"]["coverage"]
                                        ["executed"],
            "prioritization": results["metrics"]["prioritization"],
        },
        "limitations": results["limitations"][:2],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
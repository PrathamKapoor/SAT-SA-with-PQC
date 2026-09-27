"""Run the diagnostic failure analysis of the external IT incident-log result."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.research.cli import default_experiment_id, run_and_bundle
from evaluation.research.external_failure import (
    EXPERIMENT_NAME,
    run_external_failure_analysis,
)
from public_benchmarks.itsm_incident_log.adapter import (
    ADAPTER_VERSION,
    SOURCE,
    sha256_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--download-date")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--experiment-id", type=str)
    parser.add_argument("--min-incidents", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    dataset = {
        "id": "uci-498-incident-management-event-log",
        "version": "UCI 498 (2018 release)",
        "data_origin": "benchmark",
        "source": SOURCE,
        "source_file_sha256": sha256_file(args.source_csv),
        "download_date_utc": args.download_date,
        "adapter_version": ADAPTER_VERSION,
    }
    config = {
        "experiment": EXPERIMENT_NAME,
        "diagnoses": "EXP-X02",
        "min_incidents_per_group": args.min_incidents,
        "changes_to_detectors_thresholds_or_weights": "none",
        "seed": args.seed,
    }
    return run_and_bundle(
        args.out,
        experiment_id=args.experiment_id or default_experiment_id("external-failure"),
        config=config,
        dataset=dataset,
        seed=args.seed,
        run=lambda scratch: run_external_failure_analysis(
            scratch,
            source_csv=args.source_csv,
            expected_source_sha256=args.expected_sha256,
            min_incidents=args.min_incidents,
            seed=args.seed,
        ),
        summarize=lambda result: {
            "saturated_families": [
                family
                for family, value in result["metrics"]["detector_saturation"].items()
                if value["flagging_rate"] == 1.0
            ],
            "distinct_risk_values": result["metrics"]["risk"]["distinct_total_values"],
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the external IT-incident-log evaluation (UCI dataset 498)."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.research.cli import default_experiment_id, run_and_bundle
from evaluation.research.external_itsm import (
    EXPERIMENT_NAME,
    run_external_itsm_experiment,
)
from public_benchmarks.itsm_incident_log.adapter import (
    ADAPTER_VERSION,
    SOURCE,
    sha256_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument(
        "--expected-sha256",
        help="checksum recorded at download; the run refuses a different file",
    )
    parser.add_argument("--download-date", help="UTC date the source was downloaded")
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
        "note": "real IT service-management workflow data; not SOC data",
    }
    config = {
        "experiment": EXPERIMENT_NAME,
        "min_incidents_per_group": args.min_incidents,
        "label": "final made_sla (false = SLA missed), hidden from SAT-SA",
        "relevant_set": "top quartile of groups by SLA-miss rate",
        "baselines": [
            "random",
            "incident_volume",
            "slowest_median_resolution",
            "reassignment_rate",
        ],
        "seed": args.seed,
    }
    return run_and_bundle(
        args.out,
        experiment_id=args.experiment_id or default_experiment_id("external-itsm"),
        config=config,
        dataset=dataset,
        seed=args.seed,
        run=lambda scratch: run_external_itsm_experiment(
            scratch,
            source_csv=args.source_csv,
            expected_source_sha256=args.expected_sha256,
            min_incidents=args.min_incidents,
            seed=args.seed,
        ),
        summarize=lambda result: {
            "association_with_sla_miss_rate": {
                name: value["spearman_rho"]
                for name, value in result["metrics"][
                    "association_with_sla_miss_rate"
                ].items()
            }
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())

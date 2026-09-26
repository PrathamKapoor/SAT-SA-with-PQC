"""Run the isolated, synthetic TRUST-SAT integrity mutation experiment."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.integrity import run_trust_integrity_experiment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a controlled TRUST-SAT decision-integrity experiment"
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
        "trust-integrity-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    dataset = {
        "id": "controlled-trust-synthetic-submission",
        "version": "1.0",
        "data_origin": "synthetic",
        "scope": "one isolated SQLite submission, analysis, authorized decision, and receipt",
    }
    config = {
        "experiment": "trust-sat-controlled-mutation-v1",
        "mutations": [
            "decision",
            "finding",
            "risk",
            "recommendation",
            "source_provenance",
            "canonical_payload",
            "receipt_signature",
            "ledger_chain",
            "decision_reason",
            "observation_scope",
            "version_record_payload",
            "artifact_digest",
            "receipt_public_key",
        ],
        "negative_controls": ["operational_queue_field_control"],
        "protocol": "verify valid control; mutate one scratch field at a time; restore and re-verify",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="satsa-trust-research-") as scratch:
            result = run_trust_integrity_experiment(Path(scratch))
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
                "valid_control": result["valid_control"],
                "mutations_detected": sum(
                    row["detected"] for row in result["mutations"]
                ),
                "mutations_tested": len(result["mutations"]),
                "limitations": result["limitations"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

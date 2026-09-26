"""Shared run-and-bundle wrapper for research experiment scripts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.research.artifacts import write_experiment_bundle


def default_experiment_id(prefix: str) -> str:
    return f"{prefix}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_and_bundle(
    out: Path,
    *,
    experiment_id: str,
    config: dict[str, Any],
    dataset: dict[str, Any],
    seed: int | None,
    run: Callable[[Path], dict[str, Any]],
    summarize: Callable[[dict[str, Any]], dict[str, Any]],
) -> int:
    """Run ``run(scratch)`` in a temporary directory and persist a bundle.

    Any exception becomes a ``failed`` bundle carrying the failure reason,
    never a measured result. Returns a process exit code.
    """
    if (Path(out) / experiment_id).exists():
        raise SystemExit(f"experiment bundle already exists: {experiment_id}")
    try:
        with tempfile.TemporaryDirectory(prefix="satsa-research-") as scratch:
            result = run(Path(scratch))
    except Exception as exc:  # noqa: BLE001 - persist all experiment failures
        bundle = write_experiment_bundle(
            out,
            experiment_id=experiment_id,
            results=None,
            config=config,
            dataset=dataset,
            seed=seed,
            status="failed",
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
        print(json.dumps({"status": "failed", "bundle": str(bundle)}, indent=2))
        return 1
    bundle = write_experiment_bundle(
        out,
        experiment_id=experiment_id,
        results=result,
        config=config,
        dataset=dataset,
        seed=seed,
    )
    print(
        json.dumps(
            {"status": result["status"], "bundle": str(bundle), **summarize(result)},
            indent=2,
            default=str,
        )
    )
    return 0

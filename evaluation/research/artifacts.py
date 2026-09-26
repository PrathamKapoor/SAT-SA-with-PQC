"""Immutable, reproducible artifacts for controlled SAT-SA experiments.

Research-artifact SHA-256 hashes identify files and configurations here;
they are not TRUST-SAT canonical evidence digests and do not alter the
domain trust model.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_metadata() -> dict[str, Any]:
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=_REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    status = git("status", "--porcelain") or ""
    source_suffixes = {".py", ".toml", ".txt", ".yml", ".yaml", ".Dockerfile"}
    paths = [line[3:].strip().split(" -> ")[-1] for line in status.splitlines()]
    source_dirty = any(
        Path(path).suffix.lower() in source_suffixes
        or Path(path).name in {"Dockerfile", "requirements.txt", "Makefile"}
        for path in paths
    )
    return {
        "commit": git("rev-parse", "HEAD") or "unknown",
        "branch": git("branch", "--show-current") or "unknown",
        "working_tree_dirty": bool(status),
        "source_tree_dirty": source_dirty,
    }


def _versions() -> dict[str, str]:
    from satsa import __version__ as satsa_version

    versions: dict[str, str] = {"python": sys.version.split()[0]}
    versions["satsa"] = str(satsa_version)
    for name in ("qsmlops", "numpy", "scipy", "langgraph"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            if name == "qsmlops":
                try:
                    import tomllib

                    project = tomllib.loads(
                        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
                    )["project"]
                    versions[name] = str(project["version"])
                except (OSError, KeyError, ValueError):
                    versions[name] = "unknown"
            else:
                versions[name] = "not-installed"
    return versions


def _dependency_definition_hashes() -> dict[str, str]:
    result = {}
    for name in ("pyproject.toml", "requirements.txt"):
        path = _REPO_ROOT / name
        if path.is_file():
            result[name] = _file_hash(path)
    return result


def _flatten_metrics(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_metrics(value[key], child))
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            rows.extend(_flatten_metrics(child_value, f"{prefix}[{index}]"))
    elif isinstance(value, (int, float, bool)) or value is None:
        rows.append((prefix, value))
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _write_exports(root: Path, metrics: dict[str, Any]) -> None:
    rows = _flatten_metrics(metrics)
    csv_path = root / "processed" / "metrics.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("metric", "value"))
        writer.writerows(
            (name, json.dumps(value, ensure_ascii=False)) for name, value in rows
        )

    lines = [
        "# Controlled experiment summary",
        "",
        (
            "This report contains measured output from the recorded run. "
            "Read `manifest.json` for dataset scope, protocol, code state, "
            "and limitations."
        ),
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for name, value in rows:
        shown = "undefined" if value is None else str(value)
        escaped = shown.replace("|", "\\|")
        lines.append(f"| `{name}` | {escaped} |")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_experiment_bundle(
    output_root: Path,
    *,
    experiment_id: str,
    results: dict[str, Any] | None,
    config: dict[str, Any],
    dataset: dict[str, Any],
    seed: int | None,
    status: str = "completed",
    failure_reason: str | None = None,
) -> Path:
    """Write one immutable run bundle, returning its directory.

    The writer refuses to overwrite an experiment ID. Completed bundles
    include raw results and flattened JSON/CSV/Markdown metrics. Failed
    runs preserve configuration/environment/failure provenance without
    being misrepresented as successful result bundles.
    """
    if not _SAFE_ID.fullmatch(experiment_id):
        raise ValueError("experiment_id must be a path-safe identifier")
    if status not in {"completed", "failed", "cancelled", "partial"}:
        raise ValueError("status must be completed, failed, cancelled, or partial")
    if status == "completed" and results is None:
        raise ValueError("completed experiment requires results")
    if status != "completed" and not failure_reason:
        raise ValueError("non-completed experiment requires a failure_reason")
    if dataset.get("data_origin") not in {"synthetic", "controlled", "benchmark"}:
        raise ValueError(
            "research bundle dataset must declare non-production data_origin"
        )

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / experiment_id
    if destination.exists():
        raise FileExistsError(f"experiment bundle already exists: {experiment_id}")

    staging = Path(tempfile.mkdtemp(prefix=f".{experiment_id}-", dir=output_root))
    try:
        _write_json(staging / "config.json", config)
        artifacts: dict[str, str] = {"config.json": _file_hash(staging / "config.json")}
        if status == "completed" and results is not None:
            _write_json(staging / "raw" / "results.json", results)
            processed = dict(results.get("metrics", {}))
            if "performance" in results:
                processed["performance"] = results["performance"]
            _write_json(staging / "processed" / "metrics.json", processed)
            _write_exports(staging, processed)
            for relative in (
                "raw/results.json",
                "processed/metrics.json",
                "processed/metrics.csv",
                "summary.md",
            ):
                path = staging / relative
                artifacts[relative] = _file_hash(path)

        dataset_copy = dict(dataset)
        dataset_copy.setdefault("data_origin", "synthetic")
        manifest: dict[str, Any] = {
            "manifest_schema": "satsa-research-run-v1",
            "experiment_id": experiment_id,
            "run_id": uuid4().hex,
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset": dataset_copy,
            "dataset_descriptor_sha256": _sha256(_json_bytes(dataset_copy)),
            "seed": seed,
            "model_version": None,
            "configuration_sha256": _sha256(_json_bytes(config)),
            "code": _git_metadata(),
            "environment": {
                "platform": platform.platform(),
                "versions": _versions(),
                "dependency_definition_sha256": _dependency_definition_hashes(),
            },
            "artifacts_sha256": artifacts,
            "measurement_status": ("measured" if status == "completed" else status),
            "trust_digest_note": (
                "Artifact SHA-256 values identify research files and are "
                "separate from TRUST-SAT SHA3-256 canonical evidence digests."
            ),
        }
        if failure_reason:
            manifest["failure_reason"] = failure_reason
        _write_json(staging / "manifest.json", manifest)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            raise FileExistsError(
                f"experiment bundle already exists: {experiment_id}"
            ) from None
        return destination
    except Exception:
        if staging.exists():
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
        raise

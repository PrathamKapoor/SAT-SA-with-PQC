"""Research evidence freeze: canonical bundle set with verifiable hashes.

A freeze copies selected experiment bundles byte-for-byte into a versioned
directory and writes ``freeze.json`` recording, per bundle, its role
(canonical / superseded / historical), experiment, dataset, seed,
configuration digest, code commit, environment and the SHA-256 of its
manifest and every artifact. ``verify_freeze`` recomputes all of them;
any change to a manifest, raw result, processed metric, configuration or
summary is reported. Bundles are never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FREEZE_SCHEMA = "satsa-evidence-freeze/1"
ROLES = ("canonical", "superseded", "historical", "supporting")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_bundle(
    path: Path, *, expected_manifest_sha256: str | None = None
) -> list[str]:
    """Return integrity problems for one bundle (empty list = intact)."""
    path = Path(path)
    problems: list[str] = []
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json missing"]
    if expected_manifest_sha256 and _sha256(manifest_path) != expected_manifest_sha256:
        problems.append("manifest.json differs from the frozen manifest hash")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [*problems, "manifest.json is not valid JSON"]
    for relative, expected in sorted(manifest.get("artifacts_sha256", {}).items()):
        artifact = path / relative
        if not artifact.is_file():
            problems.append(f"{relative} missing")
        elif _sha256(artifact) != expected:
            problems.append(f"{relative} hash mismatch")
    config = path / "config.json"
    if config.is_file() and _sha256(config) != manifest.get("configuration_sha256"):
        problems.append("config.json does not match configuration_sha256")
    return problems


def _entry(bundle: Path, role: str, note: str) -> dict[str, Any]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    raw = bundle / "raw" / "results.json"
    experiment = None
    if raw.is_file():
        experiment = json.loads(raw.read_text(encoding="utf-8")).get("experiment")
    return {
        "bundle": bundle.name,
        "role": role,
        "note": note,
        "experiment": experiment,
        "status": manifest.get("status"),
        "measurement_status": manifest.get("measurement_status"),
        "run_id": manifest.get("run_id"),
        "created_at_utc": manifest.get("created_at_utc"),
        "dataset": manifest.get("dataset"),
        "dataset_descriptor_sha256": manifest.get("dataset_descriptor_sha256"),
        "seed": manifest.get("seed"),
        "configuration_sha256": manifest.get("configuration_sha256"),
        "code": manifest.get("code"),
        "environment": manifest.get("environment"),
        "manifest_sha256": _sha256(bundle / "manifest.json"),
        "artifacts_sha256": manifest.get("artifacts_sha256"),
    }


def build_freeze(
    selections: list[dict[str, Any]],
    out_dir: Path,
    *,
    freeze_id: str,
    canonical_commit: str,
    supporting_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Copy bundles into ``out_dir/bundles`` and write ``freeze.json``.

    ``selections`` items: ``{"path": Path, "role": str, "note": str}``.
    Refuses an existing freeze directory and any bundle that fails
    verification before copying.
    """
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f"freeze already exists: {out_dir}")
    entries = []
    for item in selections:
        source = Path(item["path"])
        if item["role"] not in ROLES:
            raise ValueError(f"unknown role {item['role']!r}")
        problems = verify_bundle(source)
        if problems:
            raise ValueError(f"{source.name} fails verification: {problems}")
        entries.append((source, _entry(source, item["role"], item.get("note", ""))))
    staging = out_dir.with_name(out_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "bundles").mkdir(parents=True)
    for source, entry in entries:
        shutil.copytree(source, staging / "bundles" / source.name)
        copied = verify_bundle(
            staging / "bundles" / source.name,
            expected_manifest_sha256=entry["manifest_sha256"],
        )
        if copied:
            raise ValueError(f"copy of {source.name} changed bytes: {copied}")
    supporting = []
    for item in supporting_files or []:
        source = Path(item["path"])
        target = staging / "supporting" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        supporting.append(
            {
                "file": f"supporting/{source.name}",
                "role": "supporting",
                "note": item.get("note", ""),
                "sha256": _sha256(target),
            }
        )
    record = {
        "schema": FREEZE_SCHEMA,
        "freeze_id": freeze_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_code_commit": canonical_commit,
        "bundles": [entry for _, entry in entries],
        "supporting_files": supporting,
        "verification": "python scripts/verify_evidence_freeze.py <freeze dir>",
    }
    (staging / "freeze.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    staging.rename(out_dir)
    return record


def verify_freeze(freeze_dir: Path) -> dict[str, Any]:
    """Recompute every recorded hash in a freeze."""
    freeze_dir = Path(freeze_dir)
    record = json.loads((freeze_dir / "freeze.json").read_text(encoding="utf-8"))
    if record.get("schema") != FREEZE_SCHEMA:
        raise ValueError("not an evidence freeze")
    results = {}
    for entry in record["bundles"]:
        bundle = freeze_dir / "bundles" / entry["bundle"]
        problems = verify_bundle(
            bundle, expected_manifest_sha256=entry["manifest_sha256"]
        )
        results[entry["bundle"]] = problems
    for item in record.get("supporting_files", []):
        path = freeze_dir / item["file"]
        ok = path.is_file() and _sha256(path) == item["sha256"]
        results[item["file"]] = [] if ok else ["supporting file hash mismatch"]
    return {
        "freeze_id": record["freeze_id"],
        "intact": all(not problems for problems in results.values()),
        "checked": len(results),
        "problems": {k: v for k, v in results.items() if v},
    }

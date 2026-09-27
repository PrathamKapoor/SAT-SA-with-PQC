"""Build the research results catalog from a freeze and a claim spec.

The spec (committed JSON) holds what only a human can state — research
question, paper-safe claim, baseline, metric, limitations — keyed by bundle.
Everything else (dataset, dataset type, system version, status, location,
manifest hash) is read from the freeze, so the catalog cannot drift from the
evidence. Entries without a bundle keep an explicit status such as
NOT EXECUTED or BLOCKED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG_SCHEMA = "satsa-evidence-catalog/1"
ALLOWED_STATUSES = {"MEASURED", "NOT EXECUTED", "BLOCKED", "NOT DEMONSTRATED"}
_DATASET_TYPE = {
    "synthetic": "controlled synthetic",
    "controlled": "controlled synthetic",
    "benchmark": "external dataset",
}


def build_catalog(freeze_dir: Path, spec_path: Path) -> dict[str, Any]:
    freeze_dir = Path(freeze_dir)
    record = json.loads((freeze_dir / "freeze.json").read_text(encoding="utf-8"))
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    bundles = {b["bundle"]: b for b in record["bundles"]}
    entries = []
    for item in spec["entries"]:
        bundle_name = item.get("bundle")
        if bundle_name:
            bundle = bundles.get(bundle_name)
            if bundle is None:
                raise ValueError(
                    f"spec names a bundle not in the freeze: {bundle_name}"
                )
            if bundle["role"] != "canonical":
                raise ValueError(
                    f"catalog may only cite canonical bundles: {bundle_name}"
                )
            dataset = bundle["dataset"] or {}
            entries.append(
                {
                    **item,
                    "dataset": f"{dataset.get('id')} ({dataset.get('version')})",
                    "dataset_type": _DATASET_TYPE.get(
                        str(dataset.get("data_origin")), dataset.get("data_origin")
                    ),
                    "system_version": bundle["code"]["commit"],
                    "status": "MEASURED",
                    "result_location": f"{freeze_dir.as_posix()}/bundles/{bundle_name}",
                    "manifest_hash": bundle["manifest_sha256"],
                }
            )
        else:
            if item.get("status") not in ALLOWED_STATUSES - {"MEASURED"}:
                raise ValueError(
                    f"{item['experiment_id']}: entries without evidence need an explicit "
                    "NOT EXECUTED / BLOCKED / NOT DEMONSTRATED status"
                )
            entries.append(
                {
                    **item,
                    "dataset": None,
                    "dataset_type": None,
                    "system_version": None,
                    "result_location": None,
                    "manifest_hash": None,
                }
            )
    return {
        "schema": CATALOG_SCHEMA,
        "freeze_id": record["freeze_id"],
        "freeze_dir": freeze_dir.as_posix(),
        "entries": entries,
    }

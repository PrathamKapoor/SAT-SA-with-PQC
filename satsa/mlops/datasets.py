"""Dataset registry: immutable, versioned training snapshots.

A dataset version is a canonical JSON snapshot of (run, features, label) rows
built from the organization's own recorded supervisory decisions. Its identity
is the SHA3-256 of the snapshot bytes. Rebuilding with identical content
returns the existing version; different content becomes a new version. A
version's content is never updated in place.

The creator must declare the data origin (organizational, synthetic,
controlled, external). The declaration is attributed, stored on the dataset
and carried into every model passport trained from it, so synthetic
decisions are never presented as real supervisory labels.
"""

from __future__ import annotations

import math
import time
from collections import Counter

from satsa.errors import DomainValidationError
from satsa.mlops import artifact
from satsa.mlops.common import dumps, get_bytes, put_bytes, stable_id
from satsa.mlops.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    FeaturesUnavailable,
    label_for,
    run_features,
)
from satsa.mlops.policy import POLICY

SCHEMA_VERSION = 1
DATA_ORIGINS = ("organizational", "synthetic", "controlled", "external")
SOURCE = "satsa_run_review_decisions"

# Plausible value ranges per feature; anything outside is an invalid value,
# not an outlier (counts cannot be negative, scores are bounded).
_RANGES = {
    "risk_total": (0.0, 100.0),
    "mean_signal_confidence": (0.0, 1.0),
}


def build_snapshot(db, organization_id: str) -> tuple[dict, dict]:
    """Snapshot document and lineage for every decided run with features."""
    decisions = db.query_all(
        "SELECT id, run_id, action FROM satsa_run_review_decisions"
        " WHERE organization_id=? ORDER BY run_id",
        (organization_id,),
    )
    rows, skipped = [], []
    for decision in decisions:
        try:
            features = run_features(db, organization_id, decision["run_id"])
        except FeaturesUnavailable:
            skipped.append(decision["run_id"])
            continue
        rows.append(
            {
                "run_id": decision["run_id"],
                "decision_id": decision["id"],
                "features": [features[name] for name in FEATURE_NAMES],
                "label": label_for(decision["action"]),
            }
        )
    document = {
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "label_definition": "1 = supervisor confirmed or escalated the run; 0 = dismissed",
        "rows": rows,
    }
    lineage = {
        "source": SOURCE,
        "decisions_considered": len(decisions),
        "runs_without_features": skipped,
        "decision_ids_digest": artifact.sha3(
            dumps(sorted(d["id"] for d in decisions)).encode("utf-8")
        ),
    }
    return document, lineage


def create_dataset(db, storage, organization_id: str, user_id: str, *,
                   name: str, data_origin: str) -> tuple[dict, bool]:
    """Create (or return the identical existing) dataset version.

    Returns (dataset row, created)."""
    document, lineage = build_snapshot(db, organization_id)
    return register_snapshot(db, storage, organization_id, user_id, name=name,
                             data_origin=data_origin, document=document, lineage=lineage)


def register_snapshot(db, storage, organization_id: str, user_id: str, *, name: str,
                      data_origin: str, document: dict, lineage: dict) -> tuple[dict, bool]:
    """Store a snapshot document as an immutable dataset version."""
    if data_origin not in DATA_ORIGINS:
        raise DomainValidationError(f"data_origin must be one of {', '.join(DATA_ORIGINS)}")
    data = artifact.canonical_bytes(document)
    digest = artifact.sha3(data)
    existing = db.query_one(
        "SELECT * FROM satsa_ml_datasets WHERE organization_id=? AND name=? AND content_digest=?",
        (organization_id, name, digest),
    )
    if existing is not None:
        return existing, False
    key = f"ml/{organization_id}/datasets/{digest}.json"
    put_bytes(storage, key, data, "application/json")
    rows = document.get("rows") if isinstance(document.get("rows"), list) else []
    labels = Counter(row.get("label") for row in rows if isinstance(row, dict))
    now = time.time()
    with db.transaction():
        latest = db.query_one(
            "SELECT MAX(version) AS v FROM satsa_ml_datasets WHERE organization_id=? AND name=?",
            (organization_id, name),
        )
        version = int(latest["v"] or 0) + 1
        dataset_id = stable_id("mlds", organization_id, name, digest)
        db.execute(
            "INSERT INTO satsa_ml_datasets (id,organization_id,name,version,data_origin,source,"
            "feature_version,schema_version,record_count,label_counts_json,content_digest,"
            "storage_key,lineage_json,status,created_by,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'created',?,?)",
            (
                dataset_id, organization_id, name, version, data_origin,
                str(lineage.get("source", SOURCE)), str(document.get("feature_version", "")),
                int(document.get("schema_version") or 0), len(rows),
                dumps({"1": labels.get(1, 0), "0": labels.get(0, 0)}), digest, key,
                dumps(lineage), user_id, now,
            ),
        )
    return db.query_one("SELECT * FROM satsa_ml_datasets WHERE id=?", (dataset_id,)), True


def load_snapshot(storage, dataset: dict) -> dict:
    """Snapshot content, refused if the stored bytes no longer match the version."""
    data = get_bytes(storage, dataset["storage_key"])
    if artifact.sha3(data) != dataset["content_digest"]:
        raise DomainValidationError("dataset snapshot does not match its recorded digest")
    import json

    return json.loads(data.decode("utf-8"))


def holdout_split(rows: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    """Deterministic stratified split: order each class by SHA3(seed, run_id)."""
    train, holdout = [], []
    for label in (0, 1):
        members = sorted(
            (r for r in rows if r["label"] == label),
            key=lambda r: artifact.sha3(f"{seed}:{r['run_id']}".encode("utf-8")),
        )
        cut = math.ceil(len(members) * POLICY.holdout_fraction)
        holdout.extend(members[:cut])
        train.extend(members[cut:])
    return train, holdout


def validate_snapshot(document: dict, *, seed: int = 0) -> dict:
    """Run every validation check; the dataset is valid only if all pass."""
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str, **data) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail, **data})

    names = document.get("feature_names")
    check(
        "schema",
        document.get("schema_version") == SCHEMA_VERSION
        and document.get("feature_version") == FEATURE_VERSION
        and names == list(FEATURE_NAMES),
        f"expects schema {SCHEMA_VERSION}, {FEATURE_VERSION}, {len(FEATURE_NAMES)} named features",
    )
    rows = document.get("rows") if isinstance(document.get("rows"), list) else []
    width = len(FEATURE_NAMES)
    bad_types = sum(
        1 for r in rows
        if not isinstance(r.get("features"), list) or len(r["features"]) != width
        or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in r["features"])
    )
    check("types", bad_types == 0, f"{bad_types} rows with a malformed feature vector",
          malformed_rows=bad_types)
    typed = [r for r in rows if isinstance(r.get("features"), list) and len(r["features"]) == width]
    missing = sum(
        1 for r in typed for v in r["features"]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
    )
    check("missingness", missing == 0, f"{missing} missing or non-finite feature values",
          missing_values=missing)
    run_ids = [r.get("run_id") for r in rows]
    duplicate_runs = len(run_ids) - len(set(run_ids))
    check("duplicate_rows", duplicate_runs == 0, f"{duplicate_runs} duplicated runs",
          duplicate_runs=duplicate_runs)
    invalid = 0
    for r in typed:
        for name, value in zip(FEATURE_NAMES, r["features"]):
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            low, high = _RANGES.get(name, (0.0, math.inf))
            if value < low or value > high:
                invalid += 1
    check("invalid_values", invalid == 0, f"{invalid} feature values outside their valid range",
          invalid_values=invalid)
    unlabeled = sum(1 for r in rows if r.get("label") not in (0, 1))
    check("label_availability", unlabeled == 0 and len(rows) > 0,
          f"{unlabeled} rows without a 0/1 label out of {len(rows)}", unlabeled_rows=unlabeled)
    counts = Counter(r.get("label") for r in rows if r.get("label") in (0, 1))
    minority = min(counts.get(0, 0), counts.get(1, 0))
    total = counts.get(0, 0) + counts.get(1, 0)
    check("minimum_rows", total >= POLICY.min_labeled_rows,
          f"{total} labeled rows; policy requires {POLICY.min_labeled_rows}", labeled_rows=total)
    check(
        "class_balance",
        minority >= POLICY.min_rows_per_class
        and total > 0 and minority / total >= POLICY.min_minority_share,
        f"class counts {{0: {counts.get(0, 0)}, 1: {counts.get(1, 0)}}}; policy requires "
        f">= {POLICY.min_rows_per_class} per class and a minority share >= {POLICY.min_minority_share}",
        class_counts={"0": counts.get(0, 0), "1": counts.get(1, 0)},
    )
    labeled = [r for r in typed if r.get("label") in (0, 1)]
    _, holdout = holdout_split(labeled, seed)
    holdout_classes = Counter(r["label"] for r in holdout)
    check(
        "train_evaluation_compatibility",
        len(holdout) >= POLICY.min_holdout_rows and len(holdout_classes) == 2,
        f"deterministic holdout has {len(holdout)} rows and {len(holdout_classes)} classes; "
        f"policy requires >= {POLICY.min_holdout_rows} rows and both classes",
        holdout_rows=len(holdout),
    )
    return {
        "policy_version": POLICY.version,
        "status": "valid" if all(c["passed"] for c in checks) else "invalid",
        "checks": checks,
    }

"""Advisory inference for one analysis run.

Called by the analysis worker after recommendations and before human review.
Exactly one inference record is written per run (retries return it). The
record is either ``scored`` with a probability, or ``abstained`` with an
explicit reason; nothing is forced into a number:

    no_deployed_model        no model is active for the organization
    model_unavailable        the active artifact is missing, altered or invalid
    feature_version_mismatch the deployed model expects other features
    missing_features         the run lacks the persisted inputs
    out_of_distribution      a feature is far outside the training population
    low_confidence           the probability is too close to 0.5 to rank
    inference_error          an unexpected failure; the run continues

The score is advisory. It does not change findings, risk, recommendations or
the decision, and review proceeds identically whether or not a model scored.
"""

from __future__ import annotations

import json
import time

from qsmlops.crypto.hashing import digest_document
from satsa.mlops import artifact
from satsa.mlops.common import MODEL_NAME, log, stable_id
from satsa.mlops.features import FEATURE_NAMES, FEATURE_VERSION, FeaturesUnavailable, run_features
from satsa.mlops.policy import POLICY
from satsa.mlops.registry import active_deployment, verify_artifact


def get_inference(db, org: str, run_id: str) -> dict | None:
    return db.query_one(
        "SELECT * FROM satsa_ml_inferences WHERE organization_id=? AND run_id=?", (org, run_id)
    )


def infer_run(db, storage, org: str, run_id: str) -> dict:
    existing = get_inference(db, org, run_id)
    if existing is not None:
        return existing
    started = time.perf_counter()
    record = {
        "model_name": MODEL_NAME,
        "model_id": None,
        "deployment_id": None,
        "artifact_digest": None,
        "feature_version": FEATURE_VERSION,
        "features": None,
        "status": "abstained",
        "abstain_reason": None,
        "score": None,
    }
    try:
        _score(db, storage, org, run_id, record)
    except Exception:  # never let the advisory model break a supervisory run
        log.exception("model inference failed", extra={"run_id": run_id, "organization_id": org})
        record.update(status="abstained", abstain_reason="inference_error", score=None)
    record["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    content = {"run_id": run_id, "organization_id": org, **record}
    content.pop("latency_ms")
    now = time.time()
    db.execute(
        "INSERT INTO satsa_ml_inferences (id,organization_id,run_id,model_name,model_id,deployment_id,"
        "artifact_digest,feature_version,features_json,status,abstain_reason,score,latency_ms,"
        "content_digest,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(run_id) DO NOTHING",
        (
            stable_id("mlinf", org, run_id), org, run_id, record["model_name"], record["model_id"],
            record["deployment_id"], record["artifact_digest"], record["feature_version"],
            json.dumps(record["features"]) if record["features"] is not None else None,
            record["status"], record["abstain_reason"], record["score"], record["latency_ms"],
            digest_document(content), now,
        ),
    )
    log.info(
        "model inference recorded",
        extra={"run_id": run_id, "model_id": record["model_id"], "status": record["status"],
               "abstain_reason": record["abstain_reason"]},
    )
    return get_inference(db, org, run_id)


def _score(db, storage, org: str, run_id: str, record: dict) -> None:
    deployment = active_deployment(db, org)
    if deployment is None:
        record["abstain_reason"] = "no_deployed_model"
        return
    model_row = db.query_one(
        "SELECT * FROM satsa_ml_models WHERE organization_id=? AND id=?",
        (org, deployment["model_id"]),
    )
    record.update(deployment_id=deployment["id"], model_id=deployment["model_id"])
    if model_row is None:
        record["abstain_reason"] = "model_unavailable"
        return
    record["artifact_digest"] = model_row["artifact_digest"]
    if model_row["feature_version"] != FEATURE_VERSION:
        record["abstain_reason"] = "feature_version_mismatch"
        return
    try:
        model = _cached_model(db, storage, model_row)
    except artifact.ArtifactError:
        log.warning("deployed model artifact failed verification",
                    extra={"model_id": model_row["id"], "run_id": run_id})
        record["abstain_reason"] = "model_unavailable"
        return
    try:
        features = run_features(db, org, run_id)
    except FeaturesUnavailable:
        record["abstain_reason"] = "missing_features"
        return
    vector = [features[name] for name in FEATURE_NAMES]
    record["features"] = vector
    if model["features"] != list(FEATURE_NAMES):
        record["abstain_reason"] = "feature_version_mismatch"
        return
    if any(abs(z) > POLICY.ood_z_limit for z in artifact.standardized(model, vector)):
        record["abstain_reason"] = "out_of_distribution"
        return
    probability = artifact.probability(model, vector)
    if abs(probability - 0.5) < POLICY.low_confidence_band:
        record["abstain_reason"] = "low_confidence"
        return
    record.update(status="scored", score=round(probability, 6))


# Verified artifacts keyed by digest. A digest identifies immutable content, so
# a cached entry can never describe different bytes; a new model is a new key.
_CACHE: dict[str, dict] = {}


def _cached_model(db, storage, model_row: dict) -> dict:
    digest = model_row["artifact_digest"]
    if digest not in _CACHE:
        _CACHE[digest] = verify_artifact(db, storage, model_row)
    return _CACHE[digest]

"""Monitoring, drift detection and retraining triggers.

Everything here is computed from persisted inference records, stored
datasets and recorded supervisory decisions. Nothing is estimated when data
is missing: an empty window reports ``no_observations``, a small drift window
reports ``insufficient_data``, and realized performance needs enough later
decisions before it reports a number.

Drift detection only *recommends* retraining (an open request). Retraining
starts when a supervisor accepts the request; the new model still has to be
verified, approved and deployed. Those are separate, separately recorded steps.
"""

from __future__ import annotations

import json
import time

from qsmlops.core.errors import NotFoundError
from qsmlops.ml.drift import PSIDriftDetector
from satsa.errors import DomainValidationError
from satsa.mlops import artifact
from satsa.mlops.common import MODEL_NAME, dumps, stable_id
from satsa.mlops.datasets import load_snapshot
from satsa.mlops.features import FEATURE_NAMES, label_for
from satsa.mlops.policy import POLICY
from satsa.mlops.registry import active_deployment, verify_artifact


def _quantiles(values: list[float]) -> dict:
    ordered = sorted(values)

    def q(p: float) -> float:
        return round(ordered[min(len(ordered) - 1, int(p * (len(ordered) - 1) + 0.5))], 6)

    return {"p05": q(0.05), "p25": q(0.25), "p50": q(0.5), "p75": q(0.75), "p95": q(0.95)}


def realized_performance(db, org: str, model_id: str) -> dict:
    """Score quality against supervisory decisions recorded after scoring."""
    rows = db.query_all(
        "SELECT i.score, d.action FROM satsa_ml_inferences i JOIN satsa_run_review_decisions d"
        " ON d.run_id=i.run_id AND d.organization_id=i.organization_id"
        " WHERE i.organization_id=? AND i.model_id=? AND i.status='scored'",
        (org, model_id),
    )
    labels = [label_for(r["action"]) for r in rows]
    result = {"labeled_inferences": len(rows), "minimum_required": POLICY.min_realized_labels}
    if len(rows) < POLICY.min_realized_labels or len(set(labels)) < 2:
        result["status"] = "insufficient_labels"
        return result
    from sklearn.metrics import roc_auc_score

    result.update(status="available", roc_auc=float(roc_auc_score(labels, [r["score"] for r in rows])))
    return result


def summary(db, org: str) -> dict:
    """Monitoring view of the active model, from its inference records."""
    deployment = active_deployment(db, org)
    totals = db.query_all(
        "SELECT status, abstain_reason, COUNT(*) AS n FROM satsa_ml_inferences"
        " WHERE organization_id=? GROUP BY status, abstain_reason",
        (org,),
    )
    result: dict = {
        "model_name": MODEL_NAME,
        "active_deployment": deployment,
        "all_models": {
            "inferences": sum(r["n"] for r in totals),
            "abstentions_by_reason": {
                r["abstain_reason"]: r["n"] for r in totals if r["status"] == "abstained"
            },
        },
    }
    if deployment is None:
        result["status"] = "no_deployed_model"
        return result
    rows = db.query_all(
        "SELECT status, abstain_reason, score, latency_ms FROM satsa_ml_inferences"
        " WHERE organization_id=? AND model_id=? ORDER BY created_at",
        (org, deployment["model_id"]),
    )
    if not rows:
        result["status"] = "no_observations"
        return result
    scores = [r["score"] for r in rows if r["status"] == "scored"]
    latencies = [r["latency_ms"] for r in rows]
    result.update(
        status="observed",
        active_model={
            "inferences": len(rows),
            "scored": len(scores),
            "abstained": len(rows) - len(scores),
            "missing_feature_rate": round(
                sum(1 for r in rows if r["abstain_reason"] == "missing_features") / len(rows), 4
            ),
            "score_distribution": _quantiles(scores) if scores else None,
            "latency_ms": _quantiles(latencies),
            "realized_performance": realized_performance(db, org, deployment["model_id"]),
        },
    )
    return result


def detect_drift(db, storage, org: str, job: dict) -> dict:
    """Compare the active model's recent scores with its training population."""
    params = json.loads(job["params_json"])
    deployment = active_deployment(db, org)
    if deployment is None:
        raise DomainValidationError("no deployed model to check for drift")
    model = db.query_one(
        "SELECT * FROM satsa_ml_models WHERE organization_id=? AND id=?",
        (org, deployment["model_id"]),
    )
    dataset = db.query_one(
        "SELECT * FROM satsa_ml_datasets WHERE organization_id=? AND id=?", (org, model["dataset_id"])
    )
    loaded = verify_artifact(db, storage, model)
    snapshot = load_snapshot(storage, dataset)
    baseline_rows = snapshot["rows"]
    baseline_scores = [artifact.probability(loaded, r["features"]) for r in baseline_rows]
    window = int(params.get("window", 500))
    current = db.query_all(
        "SELECT score, features_json, created_at FROM satsa_ml_inferences"
        " WHERE organization_id=? AND model_id=? AND status='scored'"
        " ORDER BY created_at DESC LIMIT ?",
        (org, model["id"], window),
    )
    current_scores = [r["score"] for r in current]
    details: dict = {"window_limit": window, "psi_bins": POLICY.psi_bins}
    if len(baseline_scores) < POLICY.min_drift_samples or len(current_scores) < POLICY.min_drift_samples:
        result, psi = "insufficient_data", None
        details["reason"] = (
            f"PSI needs >= {POLICY.min_drift_samples} observations per window "
            f"(baseline {len(baseline_scores)}, current {len(current_scores)})"
        )
    else:
        import numpy as np

        detector = PSIDriftDetector()
        psi = detector.compute_psi(
            np.array(baseline_scores), np.array(current_scores), bins=POLICY.psi_bins
        )
        base_matrix = np.array([r["features"] for r in baseline_rows], dtype=float)
        cur_matrix = np.array([json.loads(r["features_json"]) for r in current], dtype=float)
        details["feature_psi"] = {
            name: round(detector.compute_psi(base_matrix[:, i], cur_matrix[:, i], bins=POLICY.psi_bins), 6)
            for i, name in enumerate(FEATURE_NAMES)
        }
        details["score_psi"] = round(psi, 6)
        result = "drift" if psi > POLICY.psi_threshold else "no_drift"
    now = time.time()
    report_id = stable_id("mldrift", job["id"])
    db.execute(
        "INSERT INTO satsa_ml_drift_reports (id,organization_id,model_id,job_id,metric,threshold,"
        "baseline_count,current_count,window_start,window_end,result,details_json,policy_version,"
        "created_at) VALUES (?,?,?,?,'psi_score',?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO NOTHING",
        (
            report_id, org, model["id"], job["id"], POLICY.psi_threshold, len(baseline_scores),
            len(current_scores), min((r["created_at"] for r in current), default=None),
            max((r["created_at"] for r in current), default=None), result, dumps(details),
            POLICY.version, now,
        ),
    )
    _maybe_request_retraining(db, org, model, job["requested_by"])
    return db.query_one("SELECT * FROM satsa_ml_drift_reports WHERE id=?", (report_id,))


def _maybe_request_retraining(db, org: str, model: dict, user_id: str) -> None:
    recent = db.query_all(
        "SELECT id, result FROM satsa_ml_drift_reports WHERE organization_id=? AND model_id=?"
        " AND result<>'insufficient_data' ORDER BY created_at DESC LIMIT ?",
        (org, model["id"], POLICY.sustained_drift_reports),
    )
    if len(recent) == POLICY.sustained_drift_reports and all(r["result"] == "drift" for r in recent):
        open_request(db, org, trigger="drift", model_id=model["id"], user_id=user_id,
                     evidence={"drift_report_ids": [r["id"] for r in recent],
                               "policy": POLICY.version})
    performance = realized_performance(db, org, model["id"])
    if performance["status"] == "available" and performance["roc_auc"] < POLICY.min_realized_roc_auc:
        open_request(db, org, trigger="performance", model_id=model["id"], user_id=user_id,
                     evidence={"realized_performance": performance, "policy": POLICY.version})


def open_request(db, org: str, *, trigger: str, model_id: str | None, user_id: str,
                 evidence: dict) -> dict:
    """Open a retraining request; an identical open request is returned, not duplicated."""
    existing = db.query_one(
        "SELECT * FROM satsa_ml_retraining_requests WHERE organization_id=? AND model_name=?"
        " AND trigger=? AND status='open'",
        (org, MODEL_NAME, trigger),
    )
    if existing is not None:
        return existing
    now = time.time()
    request_id = stable_id("mlretrain", org, trigger, repr(now))
    db.execute(
        "INSERT INTO satsa_ml_retraining_requests (id,organization_id,model_name,model_id,trigger,"
        "status,evidence_json,requested_by,created_at) VALUES (?,?,?,?,?,'open',?,?,?)"
        " ON CONFLICT DO NOTHING",
        (request_id, org, MODEL_NAME, model_id, trigger, dumps(evidence), user_id, now),
    )
    row = db.query_one(
        "SELECT * FROM satsa_ml_retraining_requests WHERE organization_id=? AND model_name=?"
        " AND trigger=? AND status='open'",
        (org, MODEL_NAME, trigger),
    )
    if row is None:
        raise NotFoundError("retraining request could not be opened")
    return row

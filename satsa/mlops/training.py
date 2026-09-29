"""Training and evaluation of the review-outcome model.

Model family: L2-regularized logistic regression on standardized features
(scikit-learn, lbfgs). With a fixed dataset, split seed and hyperparameters the
fit is deterministic on a given platform and library version; the passport
records those versions because bit-identical results across versions are not
guaranteed by scikit-learn.

Evaluation scores the holdout with :func:`satsa.mlops.artifact.probability`,
the function inference uses, so the reported metrics describe the exact
serving code path.
"""

from __future__ import annotations

import platform
import sys

from satsa.errors import DomainValidationError
from satsa.mlops import artifact
from satsa.mlops.datasets import holdout_split
from satsa.mlops.features import FEATURE_NAMES, FEATURE_VERSION
from satsa.mlops.policy import POLICY

MODEL_FAMILY = "logistic_regression"
DEFAULT_HYPERPARAMETERS = {"C": 1.0, "max_iter": 1000, "class_weight": "balanced"}
DEFAULT_SEED = 20260929


def normalize_hyperparameters(raw: dict | None) -> dict:
    params = dict(DEFAULT_HYPERPARAMETERS)
    for key, value in (raw or {}).items():
        if key not in DEFAULT_HYPERPARAMETERS:
            raise DomainValidationError(f"unsupported hyperparameter {key!r}")
        params[key] = value
    if not isinstance(params["C"], (int, float)) or isinstance(params["C"], bool) or not 0 < params["C"] <= 1e4:
        raise DomainValidationError("C must be a number in (0, 10000]")
    if not isinstance(params["max_iter"], int) or not 10 <= params["max_iter"] <= 10000:
        raise DomainValidationError("max_iter must be an integer in [10, 10000]")
    if params["class_weight"] not in ("balanced", None):
        raise DomainValidationError("class_weight must be 'balanced' or null")
    params["C"] = float(params["C"])
    return params


def environment() -> dict:
    import numpy
    import sklearn

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "scikit_learn": sklearn.__version__,
    }


def train(snapshot: dict, *, hyperparameters: dict, seed: int) -> tuple[dict, dict]:
    """Fit on the deterministic training split. Returns (artifact doc, evaluation)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    if snapshot.get("feature_names") != list(FEATURE_NAMES):
        raise DomainValidationError("dataset feature schema does not match the feature version")
    train_rows, holdout = holdout_split(snapshot["rows"], seed)
    if len({r["label"] for r in train_rows}) < 2:
        raise DomainValidationError("training split contains a single class")
    X = np.array([r["features"] for r in train_rows], dtype=float)
    y = np.array([r["label"] for r in train_rows], dtype=int)
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(
        C=hyperparameters["C"],
        max_iter=hyperparameters["max_iter"],
        class_weight=hyperparameters["class_weight"],
        solver="lbfgs",
        random_state=seed,
    ).fit(scaler.transform(X), y)
    document = {
        "format": artifact.ARTIFACT_FORMAT,
        "feature_version": FEATURE_VERSION,
        "features": list(FEATURE_NAMES),
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) for v in scaler.scale_],
        "coef": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
        "train_min": [float(v) for v in X.min(axis=0)],
        "train_max": [float(v) for v in X.max(axis=0)],
    }
    loaded = artifact.load(
        artifact.canonical_bytes(document),
        expected_digest=artifact.sha3(artifact.canonical_bytes(document)),
        feature_version=FEATURE_VERSION,
    )
    evaluation = evaluate(loaded, holdout)
    evaluation["training_rows"] = len(train_rows)
    return document, evaluation


def evaluate(model: dict, holdout: list[dict]) -> dict:
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = [r["label"] for r in holdout]
    p = [artifact.probability(model, r["features"]) for r in holdout]
    result: dict = {
        "holdout_rows": len(holdout),
        "holdout_positive": sum(y),
        "threshold": 0.5,
    }
    if len(holdout) < POLICY.min_holdout_rows or len(set(y)) < 2:
        result["supervised_metrics"] = "unavailable"
        result["reason"] = "holdout lacks enough rows or both classes"
        return result
    predicted = [1 if v >= 0.5 else 0 for v in p]
    tp = sum(1 for a, b in zip(y, predicted) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y, predicted) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, predicted) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(y, predicted) if a == 0 and b == 0)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    bins = []
    for low in (0.0, 0.2, 0.4, 0.6, 0.8):
        members = [(a, b) for a, b in zip(y, p) if low <= b < low + 0.2 or (low == 0.8 and b == 1.0)]
        if members:
            bins.append(
                {
                    "range": [low, round(low + 0.2, 1)],
                    "count": len(members),
                    "mean_predicted": round(sum(b for _, b in members) / len(members), 4),
                    "observed_rate": round(sum(a for a, _ in members) / len(members), 4),
                }
            )
    result.update(
        {
            "supervised_metrics": "available",
            "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc_auc": float(roc_auc_score(y, p)),
            "pr_auc": float(average_precision_score(y, p)),
            "brier": sum((b - a) ** 2 for a, b in zip(y, p)) / len(y),
            "calibration": bins,
        }
    )
    return result


def verification(evaluation: dict) -> tuple[bool, str]:
    """Policy gate between registration and approval eligibility."""
    if evaluation.get("supervised_metrics") != "available":
        return False, "supervised evaluation unavailable: " + evaluation.get("reason", "")
    if evaluation["roc_auc"] < POLICY.min_roc_auc:
        return False, f"holdout ROC-AUC {evaluation['roc_auc']:.3f} below policy minimum {POLICY.min_roc_auc}"
    if evaluation["brier"] > POLICY.max_brier:
        return False, f"holdout Brier score {evaluation['brier']:.3f} above policy maximum {POLICY.max_brier}"
    return True, f"meets {POLICY.version}"

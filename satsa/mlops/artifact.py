"""Data-only model artifact for SAT-SA production models.

A model is a JSON document: feature order, standardization parameters,
logistic-regression coefficients and the training range of every feature.
Loading one is ``json.loads`` plus a strict schema check; there is no code
path from an artifact to executable Python (unlike pickle or torch.load).

The artifact is addressed by the SHA3-256 of its canonical bytes. Loaders
verify that digest against the registry record before parsing.
"""

from __future__ import annotations

import hashlib
import json
import math

ARTIFACT_FORMAT = "satsa-logistic-regression/1"


class ArtifactError(ValueError):
    """The artifact bytes are missing, altered or not a valid model."""


def canonical_bytes(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha3(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()


def _finite_list(value, length: int, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ArtifactError(f"{field} must be a list of {length} numbers")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ArtifactError(f"{field} contains a non-finite or non-numeric value")
        out.append(float(item))
    return out


def load(data: bytes, *, expected_digest: str, feature_version: str) -> dict:
    """Parse and validate artifact bytes that must match ``expected_digest``."""
    if not data:
        raise ArtifactError("model artifact is empty")
    if sha3(data) != expected_digest:
        raise ArtifactError("model artifact digest does not match the registry record")
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("model artifact is not valid JSON") from exc
    if not isinstance(doc, dict) or doc.get("format") != ARTIFACT_FORMAT:
        raise ArtifactError("unsupported model artifact format")
    if doc.get("feature_version") != feature_version:
        raise ArtifactError("model artifact was built for a different feature version")
    names = doc.get("features")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise ArtifactError("model artifact has no feature list")
    n = len(names)
    model = {
        "features": list(names),
        "mean": _finite_list(doc.get("mean"), n, "mean"),
        "scale": _finite_list(doc.get("scale"), n, "scale"),
        "coef": _finite_list(doc.get("coef"), n, "coef"),
        "intercept": _finite_list([doc.get("intercept")], 1, "intercept")[0],
        "train_min": _finite_list(doc.get("train_min"), n, "train_min"),
        "train_max": _finite_list(doc.get("train_max"), n, "train_max"),
    }
    if any(s <= 0 for s in model["scale"]):
        raise ArtifactError("model artifact has a non-positive scale")
    return model


def standardized(model: dict, vector: list[float]) -> list[float]:
    return [(x - m) / s for x, m, s in zip(vector, model["mean"], model["scale"])]


def probability(model: dict, vector: list[float]) -> float:
    """P(actionable) for one feature vector ordered as model['features']."""
    z = standardized(model, vector)
    logit = model["intercept"] + sum(w * v for w, v in zip(model["coef"], z))
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    e = math.exp(logit)
    return e / (1.0 + e)

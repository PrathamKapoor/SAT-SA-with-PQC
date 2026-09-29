"""Versioned feature pipeline for the review-outcome model.

One function, :func:`run_features`, turns a persisted analysis run into the
feature vector. Training (dataset snapshots) and inference both call it, so
there is exactly one implementation and no train/serve skew. The feature list,
order and missing-value behaviour are part of :data:`FEATURE_VERSION`; any
change to them requires a new version string, and models refuse input built
with a different version.

Every feature is derived from results SAT-SA's deterministic workers already
persisted for the run. No feature reads the supervisory decision (the label).
"""

from __future__ import annotations

import json

from satsa.analysis.risk import DIMENSION_WEIGHTS

FEATURE_VERSION = "review-outcome-features/1"

_DIMENSIONS = tuple(sorted(DIMENSION_WEIGHTS))

FEATURES: tuple[tuple[str, str], ...] = (
    ("risk_total", "Entity risk score for the run, 0-100 (satsa_run_risk.total_score)"),
    *(
        (f"risk_{name}", f"Risk dimension '{name}' score, 0-{DIMENSION_WEIGHTS[name]}")
        for name in _DIMENSIONS
    ),
    ("signal_count", "Number of findings in state 'signal'"),
    ("insufficient_data_count", "Number of findings in state 'insufficient_data'"),
    (
        "mean_signal_confidence",
        "Mean confidence.overall of signal findings; 0.0 when there are none "
        "(signal_count carries that case)",
    ),
)
FEATURE_NAMES: tuple[str, ...] = tuple(name for name, _ in FEATURES)


class FeaturesUnavailable(ValueError):
    """The run lacks the persisted results the feature version requires."""


def feature_definitions() -> list[dict]:
    return [{"name": name, "definition": text} for name, text in FEATURES]


def run_features(db, organization_id: str, run_id: str) -> dict[str, float]:
    """Feature vector for one run, keyed and ordered by FEATURE_NAMES.

    Missing-value behaviour: a run without a persisted risk profile has no
    defined features and raises FeaturesUnavailable (callers abstain or skip
    the row). No value is ever imputed from other runs.
    """
    risk = db.query_one(
        "SELECT profile_json FROM satsa_run_risk WHERE organization_id=? AND run_id=?",
        (organization_id, run_id),
    )
    if risk is None:
        raise FeaturesUnavailable("run has no persisted risk profile")
    profile = json.loads(risk["profile_json"])
    dimensions = {d["name"]: float(d["score"]) for d in profile.get("dimensions", [])}
    findings = db.query_all(
        "SELECT f.state, f.confidence_json FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " JOIN satsa_runs r ON r.id=o.run_id"
        " WHERE r.organization_id=? AND r.id=?",
        (organization_id, run_id),
    )
    signals = [f for f in findings if f["state"] == "signal"]
    confidences = [
        float(json.loads(f["confidence_json"] or "{}").get("overall", 0.0))
        for f in signals
    ]
    values = {
        "risk_total": float(profile["total_score"]),
        **{f"risk_{name}": dimensions.get(name, 0.0) for name in _DIMENSIONS},
        "signal_count": float(len(signals)),
        "insufficient_data_count": float(
            sum(1 for f in findings if f["state"] == "insufficient_data")
        ),
        "mean_signal_confidence": (
            sum(confidences) / len(confidences) if confidences else 0.0
        ),
    }
    return {name: values[name] for name in FEATURE_NAMES}


def label_for(action: str) -> int:
    """Supervisory decision to training label: actionable (1) or dismissed (0)."""
    if action in {"confirm", "escalate"}:
        return 1
    if action == "dismiss":
        return 0
    raise ValueError(f"unknown supervisory action {action!r}")

"""Versioned model-governance policy for the SAT-SA MLOps lifecycle.

Every threshold the lifecycle enforces lives here, with the reason it has the
value it has. The policy version is recorded on every validation, passport,
drift report and retraining request, so a later change to a number never
silently re-interprets an earlier decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GovernancePolicy:
    version: str = "satsa-ml-governance/1"

    # Dataset validation. Logistic regression over 11 features needs enough
    # rows per class for the holdout to contain both classes; below these a
    # fitted model and its metrics would be noise.
    min_labeled_rows: int = 30
    min_rows_per_class: int = 8
    # A class share below this makes accuracy-style metrics misleading.
    min_minority_share: float = 0.10

    # Deterministic holdout used for evaluation.
    holdout_fraction: float = 0.25
    min_holdout_rows: int = 8

    # Verification gate between registration and approval. 0.5 ROC-AUC is
    # chance; requiring a margin above it rejects models that learned nothing.
    min_roc_auc: float = 0.60
    # Brier score of a constant 0.5 predictor is 0.25; a model must beat it.
    max_brier: float = 0.25

    # Inference abstention.
    # A standardized feature further than this from the training mean is
    # outside the population the model saw.
    ood_z_limit: float = 4.0
    # Probabilities this close to 0.5 carry no ranking information.
    low_confidence_band: float = 0.05

    # Drift: PSI over the score distribution. 0.1/0.25 are the conventional
    # PSI "moderate"/"significant" bands; 0.2 is the common action threshold.
    psi_threshold: float = 0.20
    psi_bins: int = 10
    # PSI on fewer observations per window is dominated by sampling noise.
    min_drift_samples: int = 30
    # Retraining is recommended only after this many consecutive drift results.
    sustained_drift_reports: int = 2

    # Realized performance from later supervisory decisions.
    min_realized_labels: int = 20
    # Recommend retraining when realized ROC-AUC falls below this.
    min_realized_roc_auc: float = 0.55

    def to_dict(self) -> dict:
        return asdict(self)


POLICY = GovernancePolicy()

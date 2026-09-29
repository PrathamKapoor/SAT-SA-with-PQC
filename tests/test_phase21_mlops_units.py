"""Phase 21 unit tests: features, artifact format, validation, training, drift math."""

import copy
import math
import random

import pytest

from satsa.mlops import artifact
from satsa.mlops.datasets import holdout_split, validate_snapshot
from satsa.mlops.features import FEATURE_NAMES, FEATURE_VERSION, feature_definitions, label_for
from satsa.mlops.policy import POLICY
from satsa.mlops.training import (
    DEFAULT_HYPERPARAMETERS,
    normalize_hyperparameters,
    train,
    verification,
)


def synthetic_snapshot(n: int = 80, *, seed: int = 7, separable: bool = True) -> dict:
    """Controlled rows: label depends on risk_total when separable, else random."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        risk = rng.uniform(0, 100)
        label = int(risk > 50) if separable else rng.randint(0, 1)
        if separable and rng.random() < 0.1:
            label = 1 - label
        features = [risk] + [rng.uniform(0, 10) for _ in FEATURE_NAMES[1:-3]] + [
            float(rng.randint(0, 20)), float(rng.randint(0, 5)), rng.uniform(0.2, 1.0)]
        rows.append({"run_id": f"run_{i:03d}", "decision_id": f"d_{i:03d}",
                     "features": features, "label": label})
    return {"schema_version": 1, "feature_version": FEATURE_VERSION,
            "feature_names": list(FEATURE_NAMES), "label_definition": "test", "rows": rows}


def test_feature_version_is_explicit_and_ordered():
    assert FEATURE_VERSION == "review-outcome-features/1"
    assert [d["name"] for d in feature_definitions()] == list(FEATURE_NAMES)
    assert FEATURE_NAMES[0] == "risk_total" and len(FEATURE_NAMES) == 11
    assert label_for("confirm") == label_for("escalate") == 1
    assert label_for("dismiss") == 0
    with pytest.raises(ValueError):
        label_for("annotate")


def test_valid_snapshot_passes_every_check():
    report = validate_snapshot(synthetic_snapshot())
    assert report["status"] == "valid", report
    assert report["policy_version"] == POLICY.version
    assert {c["check"] for c in report["checks"]} >= {
        "schema", "types", "missingness", "duplicate_rows", "invalid_values",
        "label_availability", "minimum_rows", "class_balance",
        "train_evaluation_compatibility"}


@pytest.mark.parametrize("mutate, failing", [
    (lambda d: d.update(feature_version="other/1"), "schema"),
    (lambda d: d["rows"][0].update(features=[1.0]), "types"),
    (lambda d: d["rows"][0]["features"].__setitem__(1, math.nan), "missingness"),
    (lambda d: d["rows"].append(copy.deepcopy(d["rows"][0])), "duplicate_rows"),
    (lambda d: d["rows"][0]["features"].__setitem__(0, 250.0), "invalid_values"),
    (lambda d: d["rows"][0].pop("label"), "label_availability"),
    (lambda d: d.update(rows=d["rows"][:10]), "minimum_rows"),
    (lambda d: [r.update(label=1) for r in d["rows"][2:]], "class_balance"),
])
def test_each_validation_check_rejects_its_defect(mutate, failing):
    document = synthetic_snapshot()
    mutate(document)
    report = validate_snapshot(document)
    assert report["status"] == "invalid"
    assert {c["check"] for c in report["checks"] if not c["passed"]} >= {failing}


def test_empty_dataset_is_invalid_not_valid():
    document = synthetic_snapshot()
    document["rows"] = []
    assert validate_snapshot(document)["status"] == "invalid"


def test_holdout_split_is_deterministic_stratified_and_disjoint():
    rows = synthetic_snapshot()["rows"]
    train_a, hold_a = holdout_split(rows, 1)
    train_b, hold_b = holdout_split(list(reversed(rows)), 1)
    assert {r["run_id"] for r in hold_a} == {r["run_id"] for r in hold_b}
    assert not {r["run_id"] for r in train_a} & {r["run_id"] for r in hold_a}
    assert {r["label"] for r in hold_a} == {0, 1}
    assert {r["run_id"] for r in holdout_split(rows, 2)[1]} != {r["run_id"] for r in hold_a}


def test_training_is_reproducible_and_serving_math_matches_sklearn():
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    snapshot = synthetic_snapshot()
    params = normalize_hyperparameters(None)
    doc_a, eval_a = train(snapshot, hyperparameters=params, seed=11)
    doc_b, eval_b = train(snapshot, hyperparameters=params, seed=11)
    assert artifact.canonical_bytes(doc_a) == artifact.canonical_bytes(doc_b)
    assert eval_a == eval_b
    # The data-only artifact scores exactly what the fitted estimator would.
    train_rows, _ = holdout_split(snapshot["rows"], 11)
    X = np.array([r["features"] for r in train_rows])
    y = np.array([r["label"] for r in train_rows])
    scaler = StandardScaler().fit(X)
    est = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=11).fit(
        scaler.transform(X), y)
    data = artifact.canonical_bytes(doc_a)
    model = artifact.load(data, expected_digest=artifact.sha3(data), feature_version=FEATURE_VERSION)
    for row in snapshot["rows"][:10]:
        expected = est.predict_proba(scaler.transform([row["features"]]))[0][1]
        assert artifact.probability(model, row["features"]) == pytest.approx(expected, abs=1e-9)


def test_evaluation_reports_real_metrics_and_gate_decides():
    doc, evaluation = train(synthetic_snapshot(), hyperparameters=normalize_hyperparameters(None), seed=3)
    assert evaluation["supervised_metrics"] == "available"
    cm = evaluation["confusion_matrix"]
    assert sum(cm.values()) == evaluation["holdout_rows"]
    assert 0.0 <= evaluation["roc_auc"] <= 1.0 and 0.0 <= evaluation["brier"] <= 1.0
    assert verification(evaluation)[0] is True
    # A model trained on noise must not pass verification.
    _, noise = train(synthetic_snapshot(seed=9, separable=False),
                     hyperparameters=normalize_hyperparameters(None), seed=3)
    passed, reason = verification(noise)
    assert not passed and ("ROC-AUC" in reason or "Brier" in reason)


def test_unavailable_supervised_evaluation_fails_the_gate():
    passed, reason = verification({"supervised_metrics": "unavailable", "reason": "one class"})
    assert not passed and "unavailable" in reason


def test_hyperparameters_are_whitelisted_and_bounded():
    from satsa.errors import DomainValidationError

    assert normalize_hyperparameters({"C": 2}) == {**DEFAULT_HYPERPARAMETERS, "C": 2.0}
    for bad in [{"kernel": "rbf"}, {"C": 0}, {"C": "1"}, {"max_iter": 1}, {"class_weight": "x"}]:
        with pytest.raises(DomainValidationError):
            normalize_hyperparameters(bad)


def _artifact_bytes():
    doc, _ = train(synthetic_snapshot(), hyperparameters=normalize_hyperparameters(None), seed=5)
    return doc, artifact.canonical_bytes(doc)


def test_artifact_loader_rejects_tampering_and_malformed_content():
    doc, data = _artifact_bytes()
    digest = artifact.sha3(data)
    assert artifact.load(data, expected_digest=digest, feature_version=FEATURE_VERSION)
    with pytest.raises(artifact.ArtifactError, match="digest"):
        artifact.load(data + b" ", expected_digest=digest, feature_version=FEATURE_VERSION)
    with pytest.raises(artifact.ArtifactError, match="empty"):
        artifact.load(b"", expected_digest=digest, feature_version=FEATURE_VERSION)
    for change in [
        {"format": "pickle"},
        {"feature_version": "review-outcome-features/0"},
        {"coef": doc["coef"][:-1]},
        {"scale": [0.0] * len(doc["scale"])},
        {"intercept": True},
    ]:
        bad = artifact.canonical_bytes({**doc, **change})
        with pytest.raises(artifact.ArtifactError):
            artifact.load(bad, expected_digest=artifact.sha3(bad), feature_version=FEATURE_VERSION)
    not_json = b"\x80\x04K\x01."  # a pickle stream is not a model here
    with pytest.raises(artifact.ArtifactError, match="JSON"):
        artifact.load(not_json, expected_digest=artifact.sha3(not_json), feature_version=FEATURE_VERSION)


def test_probability_is_numerically_stable():
    model = {"features": ["a"], "mean": [0.0], "scale": [1.0], "coef": [1.0], "intercept": 0.0,
             "train_min": [0.0], "train_max": [1.0]}
    assert artifact.probability(model, [1000.0]) == pytest.approx(1.0)
    assert artifact.probability(model, [-1000.0]) == pytest.approx(0.0)
    assert artifact.probability(model, [0.0]) == pytest.approx(0.5)


def test_policy_is_versioned_and_serializable():
    data = POLICY.to_dict()
    assert data["version"] == "satsa-ml-governance/1"
    assert data["min_drift_samples"] >= 30 and 0 < data["psi_threshold"] < 1

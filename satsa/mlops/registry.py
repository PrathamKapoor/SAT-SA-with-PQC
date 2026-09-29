"""Model registry, passport, approval, deployment, rollback and retirement.

States (stored on satsa_ml_models, history in satsa_ml_model_events):

    registered -> verified -> approved -> retired
               -> quarantined -> retired
                  verified -> retired

``registered``  artifact stored, digest recorded, passport sealed.
``verified``    holdout evaluation meets the governance policy.
``quarantined`` evaluation does not meet policy; can never be approved.
``approved``    a supervisor (not the training requester) approved it.
``retired``     withdrawn; cannot be deployed or rolled back to.

Deployment is not a model state. The active model is the single row with
active=1 in satsa_ml_deployments (a unique partial index enforces one per
organization and model name); history is every earlier row. This keeps one
source of truth for "what is deployed" and lets a rollback restore an older
approved model without changing any model's history.

The passport is immutable: it is written once at registration with its
SHA3-256 digest and never updated. Approval and deployment are recorded as
events and deployments, and the model view composes them with the passport.
"""

from __future__ import annotations

import json
import time

from qsmlops.core.errors import NotFoundError
from satsa.errors import DomainValidationError
from satsa.mlops import artifact
from satsa.mlops.common import MODEL_NAME, ArtifactMissing, dumps, get_bytes, put_bytes, stable_id
from satsa.mlops.features import FEATURE_VERSION, feature_definitions
from satsa.mlops.policy import POLICY
from satsa.mlops.training import MODEL_FAMILY

TRANSITIONS = {
    "registered": {"verified", "quarantined"},
    "verified": {"approved", "retired"},
    "quarantined": {"retired"},
    "approved": {"retired"},
    "retired": set(),
}

INTENDED_USE = (
    "Advisory ordering of the supervisory review queue: estimates how likely a "
    "supervisor is to confirm or escalate (rather than dismiss) a completed "
    "analysis run. It never changes findings, risk, recommendations or the "
    "decision; a supervisor makes every decision."
)
LIMITATIONS = [
    "Learns only from this organization's past supervisory decisions; it "
    "reproduces their patterns, including any bias in them.",
    "Uses 11 aggregate features of a run; it does not read finding text or evidence.",
    "Not a measure of whether a finding is correct; a dismissed run may still "
    "contain real control failures.",
    "Abstains outside the training range, at probabilities near 0.5, and when "
    "features are unavailable.",
]


def _event(db, org: str, model_id: str, from_state, to_state: str, user_id: str,
           reason: str, now: float) -> None:
    db.execute(
        "INSERT INTO satsa_ml_model_events (id,organization_id,model_id,from_state,to_state,"
        "actor_user_id,reason,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (stable_id("mlev", model_id, str(from_state), to_state, repr(now)), org, model_id,
         from_state, to_state, user_id, reason, now),
    )


def _lock_model(db, org: str, model_id: str) -> dict | None:
    suffix = " FOR UPDATE" if db.dialect == "postgresql" else ""
    return db.query_one(
        "SELECT * FROM satsa_ml_models WHERE organization_id=? AND id=?" + suffix,
        (org, model_id),
    )


def transition(db, org: str, model_id: str, target: str, user_id: str, reason: str) -> dict:
    now = time.time()
    with db.transaction():
        model = _lock_model(db, org, model_id)
        if model is None:
            raise NotFoundError("model not found")
        if target not in TRANSITIONS[model["state"]]:
            raise DomainValidationError(
                f"model conflict: cannot move from {model['state']} to {target}"
            )
        db.execute(
            "UPDATE satsa_ml_models SET state=? WHERE organization_id=? AND id=?",
            (target, org, model_id),
        )
        _event(db, org, model_id, model["state"], target, user_id, reason, now)
    return get_model(db, org, model_id)


def register(db, storage, org: str, *, training_run: dict, dataset: dict,
             document: dict, evaluation: dict, environment: dict) -> dict:
    """Store the artifact, seal the passport and apply the verification gate."""
    from satsa.mlops.training import verification

    data = artifact.canonical_bytes(document)
    digest = artifact.sha3(data)
    key = f"ml/{org}/models/{digest}.json"
    stored = put_bytes(storage, key, data, "application/json")
    if stored != digest:
        raise DomainValidationError("stored model artifact digest mismatch")
    # Re-read and verify before binding the passport to the artifact.
    artifact.load(get_bytes(storage, key), expected_digest=digest, feature_version=FEATURE_VERSION)
    model_id = stable_id("mlmodel", training_run["id"])
    existing = db.query_one(
        "SELECT id FROM satsa_ml_models WHERE organization_id=? AND id=?", (org, model_id)
    )
    if existing is not None:  # retried job after a crash: registration already done
        return get_model(db, org, model_id)
    passed, gate_reason = verification(evaluation)
    now = time.time()
    with db.transaction():
        latest = db.query_one(
            "SELECT MAX(version) AS v FROM satsa_ml_models WHERE organization_id=? AND name=?",
            (org, MODEL_NAME),
        )
        version = int(latest["v"] or 0) + 1
        passport = {
            "passport_version": 1,
            "model_id": model_id,
            "model_name": MODEL_NAME,
            "model_version": version,
            "organization_id": org,
            "training_run_id": training_run["id"],
            "dataset": {
                "id": dataset["id"],
                "name": dataset["name"],
                "version": dataset["version"],
                "content_digest": dataset["content_digest"],
                "data_origin": dataset["data_origin"],
                "record_count": dataset["record_count"],
                "label_counts": json.loads(dataset["label_counts_json"]),
            },
            "training_population": (
                f"{dataset['record_count']} runs of this organization with a recorded "
                f"supervisory decision; declared data origin: {dataset['data_origin']}"
            ),
            "feature_version": FEATURE_VERSION,
            "feature_dependencies": feature_definitions(),
            "algorithm": MODEL_FAMILY,
            "hyperparameters": json.loads(training_run["hyperparameters_json"]),
            "random_seed": training_run["seed"],
            "environment": environment,
            "artifact": {"format": artifact.ARTIFACT_FORMAT, "sha3_256": digest, "storage_key": key},
            "evaluation": evaluation,
            "verification": {"passed": passed, "reason": gate_reason, "policy": POLICY.version},
            "intended_use": INTENDED_USE,
            "known_limitations": LIMITATIONS,
            "created_at": now,
        }
        passport_json = dumps(passport)
        db.execute(
            "INSERT INTO satsa_ml_models (id,organization_id,name,version,training_run_id,dataset_id,"
            "feature_version,artifact_key,artifact_digest,passport_json,passport_digest,state,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,'registered',?)",
            (model_id, org, MODEL_NAME, version, training_run["id"], dataset["id"], FEATURE_VERSION,
             key, digest, passport_json, artifact.sha3(passport_json.encode("utf-8")), now),
        )
        _event(db, org, model_id, None, "registered", training_run["requested_by"],
               "artifact stored and passport sealed", now)
        db.execute(
            "UPDATE satsa_ml_training_runs SET model_id=? WHERE organization_id=? AND id=?",
            (model_id, org, training_run["id"]),
        )
        target = "verified" if passed else "quarantined"
        db.execute(
            "UPDATE satsa_ml_models SET state=? WHERE organization_id=? AND id=?",
            (target, org, model_id),
        )
        _event(db, org, model_id, "registered", target, training_run["requested_by"],
               gate_reason, now + 1e-6)
    return get_model(db, org, model_id)


def get_model(db, org: str, model_id: str) -> dict:
    row = db.query_one(
        "SELECT * FROM satsa_ml_models WHERE organization_id=? AND id=?", (org, model_id)
    )
    if row is None:
        raise NotFoundError("model not found")
    return row


def active_deployment(db, org: str, model_name: str = MODEL_NAME) -> dict | None:
    return db.query_one(
        "SELECT * FROM satsa_ml_deployments WHERE organization_id=? AND model_name=? AND active=1",
        (org, model_name),
    )


def verify_artifact(db, storage, model: dict) -> dict:
    """Load and validate the stored artifact against the registry digest."""
    try:
        data = get_bytes(storage, model["artifact_key"])
    except ArtifactMissing as exc:
        raise artifact.ArtifactError("model artifact is missing from storage") from exc
    passport = json.loads(model["passport_json"])
    if artifact.sha3(model["passport_json"].encode("utf-8")) != model["passport_digest"]:
        raise artifact.ArtifactError("model passport does not match its digest")
    if passport["artifact"]["sha3_256"] != model["artifact_digest"]:
        raise artifact.ArtifactError("passport and registry disagree on the artifact digest")
    return artifact.load(data, expected_digest=model["artifact_digest"],
                         feature_version=model["feature_version"])


def approve(db, org: str, model_id: str, user_id: str, justification: str) -> dict:
    if not justification.strip():
        raise DomainValidationError("approval requires a justification")
    model = get_model(db, org, model_id)
    requester = db.query_one(
        "SELECT requested_by FROM satsa_ml_training_runs WHERE organization_id=? AND id=?",
        (org, model["training_run_id"]),
    )
    if requester and requester["requested_by"] == user_id:
        from qsmlops.core.errors import PermissionDeniedError

        raise PermissionDeniedError("the user who requested training may not approve the model")
    return transition(db, org, model_id, "approved", user_id, justification.strip())


def deploy(db, storage, org: str, model_id: str, user_id: str, *, kind: str = "deploy",
           reason: str = "") -> dict:
    model = get_model(db, org, model_id)
    if model["state"] != "approved":
        raise DomainValidationError(
            f"model conflict: only an approved model can be deployed (state is {model['state']})"
        )
    try:
        verify_artifact(db, storage, model)
    except artifact.ArtifactError as exc:
        raise DomainValidationError(f"model artifact failed verification: {exc}") from exc
    now = time.time()
    with db.transaction():
        # Lock the model row so a concurrent retirement cannot interleave.
        current_model = _lock_model(db, org, model_id)
        if current_model is None or current_model["state"] != "approved":
            raise DomainValidationError("model conflict: model is no longer approved")
        current = active_deployment(db, org, model["name"])
        if current is not None and current["model_id"] == model_id:
            return current
        if current is not None:
            db.execute(
                "UPDATE satsa_ml_deployments SET active=0,deactivated_at=?"
                " WHERE organization_id=? AND id=? AND active=1",
                (now, org, current["id"]),
            )
        deployment_id = stable_id("mldep", org, model_id, repr(now))
        db.execute(
            "INSERT INTO satsa_ml_deployments (id,organization_id,model_name,model_id,kind,active,"
            "previous_deployment_id,deployed_by,reason,created_at) VALUES (?,?,?,?,?,1,?,?,?,?)",
            (deployment_id, org, model["name"], model_id, kind,
             current["id"] if current else None, user_id, reason, now),
        )
    return db.query_one("SELECT * FROM satsa_ml_deployments WHERE id=?", (deployment_id,))


def rollback(db, storage, org: str, user_id: str, *, target_model_id: str | None,
             reason: str, model_name: str = MODEL_NAME) -> dict:
    current = active_deployment(db, org, model_name)
    if current is None:
        raise DomainValidationError("model conflict: no active deployment to roll back")
    if target_model_id is None:
        previous = db.query_one(
            "SELECT d.model_id FROM satsa_ml_deployments d JOIN satsa_ml_models m"
            " ON m.id=d.model_id AND m.organization_id=d.organization_id"
            " WHERE d.organization_id=? AND d.model_name=? AND d.active=0 AND d.model_id<>?"
            " AND m.state='approved' ORDER BY d.created_at DESC LIMIT 1",
            (org, model_name, current["model_id"]),
        )
        if previous is None:
            raise DomainValidationError(
                "model conflict: no previously deployed approved model to roll back to"
            )
        target_model_id = previous["model_id"]
    target = get_model(db, org, target_model_id)
    if target["id"] == current["model_id"]:
        raise DomainValidationError("model conflict: target is already the active model")
    if target["state"] != "approved":
        raise DomainValidationError(
            f"model conflict: rollback target must be approved (state is {target['state']})"
        )
    return deploy(db, storage, org, target["id"], user_id, kind="rollback", reason=reason)


def retire(db, org: str, model_id: str, user_id: str, reason: str) -> dict:
    if not reason.strip():
        raise DomainValidationError("retirement requires a reason")
    active = active_deployment(db, org, get_model(db, org, model_id)["name"])
    if active is not None and active["model_id"] == model_id:
        raise DomainValidationError(
            "model conflict: the active model cannot be retired; deploy or roll back first"
        )
    return transition(db, org, model_id, "retired", user_id, reason.strip())


def model_view(db, org: str, model: dict) -> dict:
    """Passport + current lifecycle state, for the API and workbench."""
    passport = json.loads(model["passport_json"])
    events = db.query_all(
        "SELECT from_state,to_state,actor_user_id,reason,created_at FROM satsa_ml_model_events"
        " WHERE organization_id=? AND model_id=? ORDER BY created_at",
        (org, model["id"]),
    )
    active = active_deployment(db, org, model["name"])
    deployments = db.query_all(
        "SELECT id,kind,active,deployed_by,reason,created_at,deactivated_at FROM satsa_ml_deployments"
        " WHERE organization_id=? AND model_id=? ORDER BY created_at",
        (org, model["id"]),
    )
    approval = next((e for e in reversed(events) if e["to_state"] == "approved"), None)
    return {
        "id": model["id"],
        "name": model["name"],
        "version": model["version"],
        "state": model["state"],
        "deployed": bool(active and active["model_id"] == model["id"]),
        "artifact_digest": model["artifact_digest"],
        "passport_digest": model["passport_digest"],
        "feature_version": model["feature_version"],
        "dataset_id": model["dataset_id"],
        "training_run_id": model["training_run_id"],
        "created_at": model["created_at"],
        "approval": (
            {"approved_by": approval["actor_user_id"], "justification": approval["reason"],
             "approved_at": approval["created_at"]}
            if approval else None
        ),
        "passport": passport,
        "events": events,
        "deployments": deployments,
    }

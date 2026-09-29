"""Phase 21 registry, governance, worker and failure-mode tests.

Datasets here are registered from controlled snapshots (the unit under test is
the lifecycle, not the analytics); the end-to-end test builds its dataset from
real analysed and reviewed runs.
"""

import threading
import time

import pytest

from qsmlops.core.errors import NotFoundError, PermissionDeniedError
from satsa.errors import DomainValidationError
from satsa.mlops import inference, jobs, registry
from satsa.mlops.datasets import register_snapshot
from satsa.mlops.jobs import MLJobWorker
from satsa.mlops.service import MLOpsService
from test_phase21_mlops_units import synthetic_snapshot

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


@pytest.fixture
def ml(api):
    db = api["db"]
    storage = api["client"].app.state.storage
    users = {
        role: db.query_one("SELECT id FROM satsa_users WHERE email=?", (f"{role}@example.test",))["id"]
        for role in ["viewer", "analyst", "supervisor", "auditor", "admin", "outsider"]
    }

    def svc(role, org=None):
        return MLOpsService(db, org or (api["other"] if role == "outsider" else api["org"]),
                            users[role], storage=storage, audit_service=api["audit"])

    worker = MLJobWorker(db, storage, worker_id="ml-test", audit_service=api["audit"])
    inference._CACHE.clear()
    return {"db": db, "storage": storage, "users": users, "svc": svc, "worker": worker,
            "org": api["org"], "other": api["other"]}


def drain(ml, limit=10):
    outcomes = []
    for _ in range(limit):
        outcome = ml["worker"].run_once()
        if outcome is None:
            return outcomes
        outcomes.append(outcome)
    return outcomes


def valid_dataset(ml, *, role="analyst", separable=True, name="controlled", seed=7):
    db = ml["db"]
    row, _ = register_snapshot(db, ml["storage"], ml["org"], ml["users"][role], name=name,
                               data_origin="synthetic",
                               document=synthetic_snapshot(seed=seed, separable=separable),
                               lineage={"source": "test_controlled_snapshot"})
    ml["svc"](role).validate_dataset(row["id"], f"validate-{row['id']}")
    drain(ml)
    return ml["svc"](role).get_dataset(row["id"])


def trained_model(ml, *, role="analyst", separable=True, name="controlled", seed=7, key=None):
    dataset = valid_dataset(ml, role=role, separable=separable, name=name, seed=seed)
    job = ml["svc"](role).start_training(dataset["id"], None, None, key or f"train-{name}-{seed}")
    assert drain(ml) == ["completed"]
    job = ml["svc"](role).get_job(job["id"])
    return ml["svc"](role).get_model(__import__("json").loads(job["result_json"])["model_id"])


def approved_model(ml, **kwargs):
    model = trained_model(ml, **kwargs)
    return ml["svc"]("supervisor").approve(model["id"], "holdout metrics reviewed")


# -- datasets and validation -------------------------------------------------

def test_dataset_versions_are_content_addressed_and_immutable(ml):
    db = ml["db"]
    a, created = register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"],
                                   name="d", data_origin="synthetic",
                                   document=synthetic_snapshot(seed=1), lineage={})
    again, created_again = register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"],
                                             name="d", data_origin="synthetic",
                                             document=synthetic_snapshot(seed=1), lineage={})
    b, _ = register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"], name="d",
                             data_origin="synthetic", document=synthetic_snapshot(seed=2), lineage={})
    assert created and not created_again and again["id"] == a["id"]
    assert (a["version"], b["version"]) == (1, 2)
    assert a["content_digest"] != b["content_digest"]
    with pytest.raises(DomainValidationError):
        register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"], name="d",
                          data_origin="real-soc", document=synthetic_snapshot(), lineage={})


def test_validation_is_a_job_and_persists_its_result(ml):
    dataset = valid_dataset(ml)
    assert dataset["status"] == "valid"
    report = __import__("json").loads(dataset["validation_json"])
    assert all(c["passed"] for c in report["checks"])


def test_training_refuses_invalid_and_unvalidated_datasets(ml):
    db = ml["db"]
    document = synthetic_snapshot()
    document["rows"] = document["rows"][:5]
    small, _ = register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"], name="small",
                                 data_origin="synthetic", document=document, lineage={})
    with pytest.raises(DomainValidationError, match="created"):
        ml["svc"]("analyst").start_training(small["id"], None, None, "t-unvalidated")
    ml["svc"]("analyst").validate_dataset(small["id"], "v-small")
    drain(ml)
    assert ml["svc"]("analyst").get_dataset(small["id"])["status"] == "invalid"
    with pytest.raises(DomainValidationError, match="invalid"):
        ml["svc"]("analyst").start_training(small["id"], None, None, "t-invalid")


def test_tampered_dataset_snapshot_fails_validation(ml):
    db = ml["db"]
    row, _ = register_snapshot(db, ml["storage"], ml["org"], ml["users"]["analyst"], name="t",
                               data_origin="synthetic", document=synthetic_snapshot(), lineage={})
    path = ml["storage"].root.joinpath(*row["storage_key"].split("/"))
    path.write_bytes(path.read_bytes().replace(b'"label":1', b'"label":0', 1))
    ml["svc"]("analyst").validate_dataset(row["id"], "v-tampered")
    drain(ml)
    dataset = ml["svc"]("analyst").get_dataset(row["id"])
    assert dataset["status"] == "invalid"
    assert "digest" in dataset["validation_json"]


# -- registration, passport, approval ----------------------------------------

def test_training_registers_a_verified_model_with_an_immutable_passport(ml):
    model = trained_model(ml)
    passport = model["passport"]
    assert model["state"] == "verified" and model["version"] == 1 and not model["deployed"]
    assert passport["dataset"]["data_origin"] == "synthetic"
    assert passport["artifact"]["sha3_256"] == model["artifact_digest"]
    assert passport["random_seed"] and passport["hyperparameters"]["C"] == 1.0
    assert passport["evaluation"]["supervised_metrics"] == "available"
    assert passport["verification"]["passed"] is True
    assert passport["environment"]["scikit_learn"]
    assert "approval" not in passport and "deployed" not in passport
    assert [e["to_state"] for e in model["events"]] == ["registered", "verified"]


def test_duplicate_registration_of_one_training_run_is_idempotent(ml):
    model = trained_model(ml)
    db = ml["db"]
    run = db.query_one("SELECT * FROM satsa_ml_training_runs WHERE id=?", (model["training_run_id"],))
    dataset = db.query_one("SELECT * FROM satsa_ml_datasets WHERE id=?", (model["dataset_id"],))
    from satsa.mlops.datasets import load_snapshot
    from satsa.mlops.training import train

    document, evaluation = train(load_snapshot(ml["storage"], dataset),
                                 hyperparameters=__import__("json").loads(run["hyperparameters_json"]),
                                 seed=run["seed"])
    again = registry.register(db, ml["storage"], ml["org"], training_run=run, dataset=dataset,
                              document=document, evaluation=evaluation, environment={})
    assert again["id"] == model["id"]
    assert db.query_one("SELECT COUNT(*) AS n FROM satsa_ml_models")["n"] == 1


def test_model_trained_on_noise_is_quarantined_and_cannot_be_approved(ml):
    model = trained_model(ml, separable=False, name="noise", seed=9)
    assert model["state"] == "quarantined"
    with pytest.raises(DomainValidationError, match="conflict"):
        ml["svc"]("supervisor").approve(model["id"], "trying anyway")


def test_approval_needs_role_justification_and_separation_of_duties(ml):
    model = trained_model(ml, role="analyst")
    for role in ["viewer", "analyst", "auditor"]:
        with pytest.raises(PermissionDeniedError):
            ml["svc"](role).approve(model["id"], "ok")
    with pytest.raises(DomainValidationError):
        ml["svc"]("supervisor").approve(model["id"], "   ")
    approved = ml["svc"]("supervisor").approve(model["id"], "metrics reviewed")
    assert approved["state"] == "approved"
    assert approved["approval"]["approved_by"] == ml["users"]["supervisor"]
    with pytest.raises(DomainValidationError, match="conflict"):
        ml["svc"]("admin").approve(model["id"], "again")
    # A supervisor who requested training cannot approve that model.
    own = trained_model(ml, role="supervisor", name="own", seed=8)
    with pytest.raises(PermissionDeniedError):
        ml["svc"]("supervisor").approve(own["id"], "self approval")
    assert ml["svc"]("admin").approve(own["id"], "second person")["state"] == "approved"


def test_lifecycle_transitions_are_audited(ml):
    model = approved_model(ml)
    ml["svc"]("supervisor").deploy(model["id"], "first")
    actions = {row["action"] for row in ml["db"].query_all("SELECT action FROM audit_events")}
    assert {"ml.dataset.validation_requested", "ml.validate_dataset.completed",
            "ml.training.requested", "ml.train.completed", "ml.model.approved",
            "ml.model.deployed"} <= actions


# -- deployment, rollback, retirement ----------------------------------------

def test_only_approved_intact_models_deploy(ml):
    model = trained_model(ml)
    with pytest.raises(DomainValidationError, match="approved"):
        ml["svc"]("supervisor").deploy(model["id"], "")
    for role in ["viewer", "analyst", "auditor"]:
        with pytest.raises(PermissionDeniedError):
            ml["svc"](role).deploy(model["id"], "")
    with pytest.raises(NotFoundError):
        ml["svc"]("supervisor").deploy("mlmodel_missing", "")


@pytest.mark.parametrize("damage", ["corrupt", "delete", "passport"])
def test_damaged_artifact_or_passport_blocks_deployment(ml, damage):
    model = approved_model(ml)
    path = ml["storage"].root.joinpath(*model["passport"]["artifact"]["storage_key"].split("/"))
    if damage == "corrupt":
        path.write_bytes(path.read_bytes().replace(b'"intercept":', b'"intercept": ', 1))
    elif damage == "delete":
        path.unlink()
    else:
        # Altered passport content no longer matches its recorded digest.
        ml["db"].execute("UPDATE satsa_ml_models SET passport_json=? WHERE id=?",
                         ('{"artifact":{"sha3_256":"x"}}', model["id"]))
    with pytest.raises(DomainValidationError, match="verification"):
        ml["svc"]("supervisor").deploy(model["id"], "")
    assert registry.active_deployment(ml["db"], ml["org"]) is None


def test_rollback_restores_previous_approved_model_without_rewriting_history(ml):
    first = approved_model(ml, name="a", seed=7)
    second = approved_model(ml, name="b", seed=21)
    svc = ml["svc"]("supervisor")
    with pytest.raises(DomainValidationError, match="no active"):
        svc.rollback(None, "nothing deployed")
    svc.deploy(first["id"], "v1")
    svc.deploy(second["id"], "v2")
    for role in ["viewer", "analyst", "auditor"]:
        with pytest.raises(PermissionDeniedError):
            ml["svc"](role).rollback(None, "not allowed")
    restored = svc.rollback(None, "v2 misbehaving")
    assert restored["model_id"] == first["id"] and restored["kind"] == "rollback"
    assert registry.active_deployment(ml["db"], ml["org"])["model_id"] == first["id"]
    assert svc.get_model(second["id"])["state"] == "approved"  # newer model kept
    history = ml["db"].query_all(
        "SELECT model_id, kind, active FROM satsa_ml_deployments ORDER BY created_at")
    assert [(h["model_id"], h["kind"], h["active"]) for h in history] == [
        (first["id"], "deploy", 0), (second["id"], "deploy", 0), (first["id"], "rollback", 1)]


def test_rollback_refuses_missing_unapproved_and_retired_targets(ml):
    svc = ml["svc"]("supervisor")
    active = approved_model(ml, name="a", seed=7)
    svc.deploy(active["id"], "")
    verified = trained_model(ml, name="c", seed=22)
    retired = approved_model(ml, name="d", seed=23)
    svc.retire(retired["id"], "superseded")
    with pytest.raises(NotFoundError):
        svc.rollback("mlmodel_missing", "x")
    with pytest.raises(DomainValidationError, match="approved"):
        svc.rollback(verified["id"], "x")
    with pytest.raises(DomainValidationError, match="approved"):
        svc.rollback(retired["id"], "x")
    with pytest.raises(DomainValidationError, match="already the active"):
        svc.rollback(active["id"], "x")
    with pytest.raises(DomainValidationError, match="no previously deployed"):
        svc.rollback(None, "x")


def test_active_model_cannot_be_retired_and_retired_model_cannot_deploy(ml):
    svc = ml["svc"]("supervisor")
    model = approved_model(ml)
    svc.deploy(model["id"], "")
    with pytest.raises(DomainValidationError, match="active model"):
        svc.retire(model["id"], "x")
    other = approved_model(ml, name="o", seed=31)
    svc.retire(other["id"], "no longer needed")
    with pytest.raises(DomainValidationError, match="approved"):
        svc.deploy(other["id"], "")


def test_concurrent_deployments_leave_exactly_one_active_model(ml):
    a = approved_model(ml, name="a", seed=7)
    b = approved_model(ml, name="b", seed=21)
    errors = []

    def deploy(model_id):
        try:
            ml["svc"]("supervisor").deploy(model_id, "race")
        except DomainValidationError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=deploy, args=(m,)) for m in (a["id"], b["id"])]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    active = ml["db"].query_all("SELECT model_id FROM satsa_ml_deployments WHERE active=1")
    assert len(active) == 1
    assert all("conflict" in e for e in errors)


# -- inference abstention ------------------------------------------------------

def test_inference_abstains_explicitly(ml, monkeypatch):
    db, org = ml["db"], ml["org"]
    assert inference.infer_run(db, ml["storage"], org, "run_a")["abstain_reason"] == "no_deployed_model"
    model = approved_model(ml)
    ml["svc"]("supervisor").deploy(model["id"], "")
    missing = inference.infer_run(db, ml["storage"], org, "run_without_risk")
    assert (missing["status"], missing["abstain_reason"]) == ("abstained", "missing_features")
    assert missing["model_id"] == model["id"] and missing["artifact_digest"] == model["artifact_digest"]
    snapshot = synthetic_snapshot()
    names = __import__("satsa.mlops.features", fromlist=["FEATURE_NAMES"]).FEATURE_NAMES

    def vector(values):
        monkeypatch.setattr(inference, "run_features", lambda *_: dict(zip(names, values)))

    vector([1e6] + snapshot["rows"][0]["features"][1:])
    assert inference.infer_run(db, ml["storage"], org, "run_ood")["abstain_reason"] == "out_of_distribution"
    vector(snapshot["rows"][0]["features"])
    scored = inference.infer_run(db, ml["storage"], org, "run_scored")
    if scored["status"] == "scored":
        assert 0.0 <= scored["score"] <= 1.0 and scored["abstain_reason"] is None
    else:
        assert scored["abstain_reason"] == "low_confidence"
    # Idempotent per run: a retry returns the recorded result.
    assert inference.infer_run(db, ml["storage"], org, "run_scored")["id"] == scored["id"]


def test_inference_abstains_when_deployed_artifact_disappears(ml):
    model = approved_model(ml)
    ml["svc"]("supervisor").deploy(model["id"], "")
    path = ml["storage"].root.joinpath(*model["passport"]["artifact"]["storage_key"].split("/"))
    path.unlink()
    inference._CACHE.clear()  # a fresh worker process
    result = inference.infer_run(ml["db"], ml["storage"], ml["org"], "run_after_delete")
    assert (result["status"], result["abstain_reason"]) == ("abstained", "model_unavailable")


# -- drift and retraining trigger ----------------------------------------------

def _score_population(ml, monkeypatch, prefix, rows, shift):
    from satsa.mlops.features import FEATURE_NAMES

    for i, row in enumerate(rows):
        values = [row["features"][0] * shift] + row["features"][1:]
        monkeypatch.setattr(inference, "run_features",
                            lambda *_a, v=values: dict(zip(FEATURE_NAMES, v)))
        inference.infer_run(ml["db"], ml["storage"], ml["org"], f"{prefix}_{i}")


def test_sustained_score_drift_recommends_but_never_starts_retraining(ml, monkeypatch):
    model = approved_model(ml)
    ml["svc"]("supervisor").deploy(model["id"], "")
    svc = ml["svc"]("analyst")
    # Too few observations: insufficient data, not "no drift".
    _score_population(ml, monkeypatch, "few", synthetic_snapshot(n=10, seed=40)["rows"], 1.0)
    svc.start_drift_check("drift-small", 500)
    assert drain(ml) == ["completed"]
    first = svc.list_drift_reports(50, 0)["items"][0]
    assert first["result"] == "insufficient_data" and first["current_count"] < 30
    # A population whose risk is compressed toward zero shifts the scores.
    _score_population(ml, monkeypatch, "shifted", synthetic_snapshot(n=80, seed=41)["rows"], 0.05)
    for key in ("drift-a", "drift-b"):
        svc.start_drift_check(key, 500)
        assert drain(ml) == ["completed"]
    reports = svc.list_drift_reports(50, 0)["items"]
    assert [r["result"] for r in reports[:2]] == ["drift", "drift"]
    detail = reports[0]
    assert detail["details"]["score_psi"] > detail["threshold"]
    assert detail["baseline_count"] == 80 and detail["current_count"] >= 30
    assert "risk_total" in detail["details"]["feature_psi"]
    requests = svc.list_retraining_requests(50, 0)["items"]
    assert [(r["trigger"], r["status"]) for r in requests] == [("drift", "open")]
    # Recommendation only: no training job, no new model, deployment unchanged.
    assert ml["db"].query_one("SELECT COUNT(*) AS n FROM satsa_ml_jobs WHERE kind='train'")["n"] == 1
    assert ml["db"].query_one("SELECT COUNT(*) AS n FROM satsa_ml_models")["n"] == 1
    assert registry.active_deployment(ml["db"], ml["org"])["model_id"] == model["id"]
    # A third drift result does not duplicate the open request.
    svc.start_drift_check("drift-c", 500)
    drain(ml)
    assert len(svc.list_retraining_requests(50, 0)["items"]) == 1
    # Dismissal is supervisory and recorded.
    with pytest.raises(PermissionDeniedError):
        svc.dismiss_retraining(requests[0]["id"], "no")
    dismissed = ml["svc"]("supervisor").dismiss_retraining(requests[0]["id"], "seasonal change")
    assert dismissed["status"] == "dismissed" and dismissed["resolution"] == "seasonal change"


# -- worker: idempotency, leases, retries, cancellation ------------------------

def test_job_idempotency_key_cannot_be_reused_for_another_request(ml):
    dataset = valid_dataset(ml)
    svc = ml["svc"]("analyst")
    job = svc.start_training(dataset["id"], None, None, "same-key")
    assert svc.start_training(dataset["id"], None, None, "same-key")["id"] == job["id"]
    with pytest.raises(DomainValidationError, match="already used"):
        svc.start_training(dataset["id"], {"C": 3}, None, "same-key")


def test_expired_lease_is_recovered_by_another_worker(ml):
    dataset = valid_dataset(ml)
    job = ml["svc"]("analyst").start_training(dataset["id"], None, None, "lease")
    queue = jobs.MLJobQueue(ml["db"], lease_seconds=0.01)
    claimed = queue.claim("dead-worker")  # claims, then "dies"
    assert claimed["id"] == job["id"] and claimed["status"] == "running"
    time.sleep(0.05)
    assert drain(ml) == ["completed"]
    finished = ml["svc"]("analyst").get_job(job["id"])
    assert finished["status"] == "completed" and finished["attempt_count"] == 2


def test_lease_exhaustion_fails_the_job_and_its_training_run(ml):
    dataset = valid_dataset(ml)
    job = ml["svc"]("analyst").start_training(dataset["id"], None, None, "exhaust")
    ml["db"].execute("UPDATE satsa_ml_jobs SET max_attempts=1 WHERE id=?", (job["id"],))
    queue = jobs.MLJobQueue(ml["db"], lease_seconds=0.01)
    claimed = queue.claim("dead-worker")
    ml["db"].execute(
        "INSERT INTO satsa_ml_training_runs (id,organization_id,job_id,dataset_id,feature_version,"
        "model_family,hyperparameters_json,seed,status,requested_by,started_at)"
        " VALUES ('tr_dead',?,?,?,'x','x','{}',1,'running',?,?)",
        (ml["org"], claimed["id"], dataset["id"], ml["users"]["analyst"], time.time()))
    time.sleep(0.05)
    assert queue.claim("other") is None
    failed = ml["svc"]("analyst").get_job(job["id"])
    assert failed["status"] == "failed" and failed["error"].startswith("lease_exhausted")
    assert ml["db"].query_one("SELECT status FROM satsa_ml_training_runs WHERE id='tr_dead'")[
        "status"] == "failed"


def test_transient_errors_retry_then_fail_without_a_model(ml, monkeypatch):
    dataset = valid_dataset(ml)
    job = ml["svc"]("analyst").start_training(dataset["id"], None, None, "transient")

    def boom(*_args, **_kwargs):
        raise OSError("object storage unavailable")

    monkeypatch.setattr("satsa.mlops.training.train", boom)
    outcomes = []
    for _ in range(3):
        ml["db"].execute("UPDATE satsa_ml_jobs SET available_at=0 WHERE id=?", (job["id"],))
        outcomes.append(ml["worker"].run_once())
    assert outcomes == ["retry_wait", "retry_wait", "failed"]
    assert ml["svc"]("analyst").get_job(job["id"])["status"] == "failed"
    assert ml["db"].query_one("SELECT COUNT(*) AS n FROM satsa_ml_models")["n"] == 0
    run = ml["db"].query_one("SELECT status FROM satsa_ml_training_runs WHERE job_id=?", (job["id"],))
    assert run["status"] == "failed"


def test_cancellation_of_queued_and_running_jobs(ml, monkeypatch):
    dataset = valid_dataset(ml)
    svc = ml["svc"]("analyst")
    queued = svc.start_training(dataset["id"], None, None, "cancel-queued")
    assert svc.cancel_job(queued["id"])["status"] == "cancelled"
    assert drain(ml) == []
    running = svc.start_training(dataset["id"], None, None, "cancel-running")
    from satsa.mlops import training

    real_train = training.train

    def train_then_cancel(*args, **kwargs):
        result = real_train(*args, **kwargs)
        svc.cancel_job(running["id"])  # arrives while the job is running
        return result

    monkeypatch.setattr(training, "train", train_then_cancel)
    assert drain(ml) == ["cancelled"]
    assert svc.get_job(running["id"])["status"] == "cancelled"
    assert ml["db"].query_one("SELECT COUNT(*) AS n FROM satsa_ml_models")["n"] == 0


# -- tenancy -------------------------------------------------------------------

def test_other_organization_cannot_see_or_act_on_models(ml):
    model = approved_model(ml)
    ml["svc"]("supervisor").deploy(model["id"], "")
    inference.infer_run(ml["db"], ml["storage"], ml["org"], "run_tenant")
    outsider = ml["svc"]("outsider")  # admin of the other organization
    with pytest.raises(NotFoundError):
        outsider.get_model(model["id"])
    with pytest.raises(NotFoundError):
        outsider.get_dataset(model["dataset_id"])
    with pytest.raises(NotFoundError):
        outsider.get_training_run(model["training_run_id"])
    with pytest.raises(NotFoundError):
        outsider.deploy(model["id"], "")
    with pytest.raises(NotFoundError):
        outsider.approve(model["id"], "x")
    with pytest.raises(NotFoundError):
        outsider.retire(model["id"], "x")
    # The other organization has no deployment of its own to roll back, and
    # cannot target this organization's model.
    with pytest.raises(DomainValidationError, match="no active"):
        outsider.rollback(model["id"], "x")
    assert outsider.list_models(50, 0)["items"] == []
    assert outsider.list_datasets(50, 0)["items"] == []
    assert outsider.monitoring()["status"] == "no_deployed_model"
    assert outsider.monitoring()["all_models"]["inferences"] == 0
    # A member of the model's organization with the wrong organization context
    # is refused before any lookup.
    with pytest.raises(PermissionDeniedError):
        ml["svc"]("analyst", org=ml["other"]).list_models(50, 0)

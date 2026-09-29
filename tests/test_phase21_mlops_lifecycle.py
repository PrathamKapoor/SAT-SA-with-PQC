"""Phase 21 end-to-end: the MLOps lifecycle over the real product path.

Population: synthetic CSE submissions (satsa.analysis.synth) uploaded through
the API, analysed by the real worker, then decided by a supervisor. The
decisions are synthetic (confirm the pathological cohort, dismiss the healthy
one) and the dataset is declared
``synthetic``; nothing here claims real supervisory behaviour.

Then, only through HTTP and the worker: dataset -> validation -> training ->
evaluation -> passport -> registration -> approval -> deployment -> inference
inside a LangGraph run -> TRUST-SAT binding -> monitoring -> drift ->
retraining decision -> retraining -> second approval -> deployment -> rollback.
"""

import io
import json
import statistics

import pytest
from fastapi.testclient import TestClient

from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.service import IdentityService
from satsa.analysis.synth import PERIOD_END, PERIOD_START, GenConfig, generate
from satsa.tenancy import TenantAdministration

pytest_plugins = ["test_tenant_schema"]

POPULATION = 36


@pytest.fixture
def world(engine, tmp_path):
    from satsa.analysis.execution import AnalysisExecutionWorker
    from satsa.api import create_app
    from satsa.api.settings import ApiSettings
    from satsa.mlops import inference
    from satsa.mlops.jobs import MLJobWorker
    from satsa.submissions.storage import LocalArtifactStorage

    inference._CACHE.clear()
    audit = AuditService(EvidenceLedger(tmp_path / "audit.jsonl"), database=engine)
    identities = IdentityService(engine, audit)
    admin = TenantAdministration(engine)
    org = admin.create_organization("CSE supervisor")
    tokens = {}
    for role in ["viewer", "analyst", "supervisor", "admin"]:
        identity = identities.create_identity("human", role, "owner", f"satsa_{role}")
        admin.add_membership(org, admin.create_user(identity.id, f"{role}@e2e.test"), f"satsa_{role}")
        tokens[role] = identities.issue_credential(identity.id)
    storage = LocalArtifactStorage(tmp_path / "artifacts")
    # Rate limits are exercised by the Phase 20 suite; this test uploads a
    # population and must not be throttled by them.
    app = create_app(engine, storage=storage, audit=audit, identity_service=identities,
                     settings=ApiSettings(secure_cookies=False, mutation_limit=100000,
                                          read_limit=100000),
                     trust_key_dir=tmp_path / "keys")
    worker = AnalysisExecutionWorker(engine, worker_id="e2e", audit=audit,
                                     trust_key_dir=str(tmp_path / "keys"), storage=storage)
    ml_worker = MLJobWorker(engine, storage, worker_id="e2e-ml", audit_service=audit)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield {"c": client, "db": engine, "org": org, "tokens": tokens, "worker": worker,
               "ml_worker": ml_worker, "tmp": tmp_path}


def h(w, role, key=None):
    headers = {"Authorization": f"Bearer {w['tokens'][role]}", "X-Organization-ID": w["org"]}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def conform(cse) -> None:
    """Make generated cases pass the hosted validator.

    The research generator (frozen with the paper's evidence, so not edited
    here) can emit a case with closed_at set and a non-closed status; the
    hosted validator rejects that inconsistency. Such a case is marked closed.
    """
    import csv

    path = cse / "cases.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row.get("closed_at") and row.get("status") != "closed":
            row["status"] = "closed"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def pathological(index: int) -> bool:
    return index % 2 == 1


def cohort_config(index: int) -> GenConfig:
    """Two synthetic cohorts: healthy practice and pathological practice."""
    if pathological(index):
        return GenConfig(seed=1000 + index, num_cse=1, num_alerts=24, num_cases=6,
                         fast_closure_rate=0.7, missing_investigation_rate=0.5,
                         escalation_rate=0.1, disposition_rate=0.4)
    return GenConfig(seed=1000 + index, num_cse=1, num_alerts=24, num_cases=6,
                     fast_closure_rate=0.0, missing_investigation_rate=0.0,
                     escalation_rate=0.9, disposition_rate=0.95)


def analyse(w, index: int, cfg: GenConfig, mode: str = "standard") -> str:
    """Upload one synthetic CSE, analyse it, and leave it awaiting review."""
    c = w["c"]
    cse = generate(cfg, w["tmp"] / f"cse{index}")[0]
    conform(cse)
    entity = ok(c.post("/api/v1/entities", headers=h(w, "analyst"),
                       json={"display_name": f"CSE {index}", "sector": "banking"}), 201)
    assessment = ok(c.post("/api/v1/assessments", headers=h(w, "analyst"),
                           json={"entity_id": entity["id"], "period_start": PERIOD_START,
                                 "period_end": PERIOD_END}), 201)
    submission = ok(c.post("/api/v1/submissions", headers=h(w, "analyst", f"s{index}"),
                           json={"assessment_id": assessment["id"]}), 201)
    version = ok(c.post(f"/api/v1/submissions/{submission['id']}/versions",
                        headers=h(w, "analyst", f"v{index}")), 201)
    for path in sorted(cse.iterdir()):
        ok(c.post(f"/api/v1/versions/{version['id']}/artifacts?category={path.stem}",
                  headers=h(w, "analyst", f"a{index}{path.stem}"),
                  files={"file": (path.name, io.BytesIO(path.read_bytes()), "text/csv")}), 201)
    ok(c.post(f"/api/v1/versions/{version['id']}/complete", headers=h(w, "analyst")))
    ok(c.post(f"/api/v1/versions/{version['id']}/validate", headers=h(w, "analyst")))
    run = ok(c.post("/api/v1/runs", headers=h(w, "analyst", f"r{index}"),
                    json={"submission_version_id": version["id"], "execution_mode": mode}), 202)
    assert w["worker"].run_once() == "awaiting_review"
    return run["id"]


def decide(w, run_id: str, action: str) -> None:
    ok(w["c"].post(f"/api/v1/runs/{run_id}/decision", headers=h(w, "supervisor"),
                   json={"action": action, "reason": "synthetic label for lifecycle test"}), 201)
    assert w["worker"].run_once() in {"completed", "partial"}


def ml_job(w, response) -> dict:
    job = ok(response, 202)
    assert w["ml_worker"].run_once() == "completed"
    return ok(w["c"].get(f"/api/v1/ml/jobs/{job['id']}", headers=h(w, "viewer")))


def test_full_mlops_lifecycle_over_the_product_path(world):
    w, c = world, world["c"]

    # -- population: real ingestion, analysis and (synthetic) human review ----
    runs, risks = [], {}
    for i in range(POPULATION):
        cfg = cohort_config(i)
        run_id = analyse(w, i, cfg)
        # Before any model exists every run records an explicit abstention.
        inf = ok(c.get(f"/api/v1/runs/{run_id}/model-inference", headers=h(w, "viewer")))
        assert (inf["status"], inf["abstain_reason"]) == ("abstained", "no_deployed_model")
        risks[run_id] = ok(c.get(f"/api/v1/runs/{run_id}/risk", headers=h(w, "viewer")))[
            "profile"]["total_score"]
        runs.append(run_id)
    healthy = [risks[r] for i, r in enumerate(runs) if not pathological(i)]
    flawed = [risks[r] for i, r in enumerate(runs) if pathological(i)]
    assert statistics.median(flawed) > statistics.median(healthy), "cohorts must differ"
    for i, run_id in enumerate(runs):
        # Synthetic supervisor: confirms the pathological cohort, dismisses the healthy one.
        # No label noise here: the holdout depends on random run ids, and a
        # noisy few-row holdout would make the verification gate (correctly)
        # fail at random. Noisy and uninformative training is covered by the
        # unit tests, where a noise-trained model must fail the gate.
        actionable = pathological(i)
        decide(w, run_id, "confirm" if actionable else "dismiss")

    # -- honest empty states ---------------------------------------------------
    monitoring = ok(c.get("/api/v1/ml/monitoring", headers=h(w, "viewer")))
    assert monitoring["status"] == "no_deployed_model"
    assert monitoring["all_models"]["abstentions_by_reason"] == {"no_deployed_model": POPULATION}

    # -- dataset registry and validation ---------------------------------------
    assert c.post("/api/v1/ml/datasets", headers=h(w, "viewer"),
                  json={"name": "review-outcome", "data_origin": "synthetic"}).status_code == 403
    dataset = ok(c.post("/api/v1/ml/datasets", headers=h(w, "analyst"),
                        json={"name": "review-outcome", "data_origin": "synthetic"}), 201)
    assert dataset["record_count"] == POPULATION and dataset["status"] == "created"
    assert dataset["lineage"]["source"] == "satsa_run_review_decisions"
    same = ok(c.post("/api/v1/ml/datasets", headers=h(w, "analyst"),
                     json={"name": "review-outcome", "data_origin": "synthetic"}), 200)
    assert same["id"] == dataset["id"]
    job = ml_job(w, c.post(f"/api/v1/ml/datasets/{dataset['id']}/validate",
                           headers=h(w, "analyst", "validate-1")))
    assert job["result"]["status"] == "valid", job["result"]
    assert ok(c.get(f"/api/v1/ml/datasets/{dataset['id']}", headers=h(w, "viewer")))["status"] == "valid"

    # -- training, evaluation, passport, registration ---------------------------
    job = ml_job(w, c.post("/api/v1/ml/training-runs", headers=h(w, "analyst", "train-1"),
                           json={"dataset_id": dataset["id"], "seed": 7}))
    model_id = job["result"]["model_id"]
    model = ok(c.get(f"/api/v1/ml/models/{model_id}", headers=h(w, "viewer")))
    evaluation = model["passport"]["evaluation"]
    assert model["state"] == "verified", evaluation
    assert evaluation["supervised_metrics"] == "available"
    assert evaluation["roc_auc"] >= 0.6 and evaluation["holdout_rows"] >= 8
    assert model["passport"]["dataset"]["data_origin"] == "synthetic"
    assert model["passport"]["training_population"].endswith("declared data origin: synthetic")
    training = ok(c.get(f"/api/v1/ml/training-runs/{model['training_run_id']}", headers=h(w, "viewer")))
    assert training["status"] == "completed" and training["seed"] == 7

    # -- approval and deployment (server-side authorization) ---------------------
    assert c.post(f"/api/v1/ml/models/{model_id}/approve", headers=h(w, "analyst"),
                  json={"justification": "x"}).status_code == 403
    assert c.post(f"/api/v1/ml/models/{model_id}/deploy", headers=h(w, "supervisor")).status_code == 409
    ok(c.post(f"/api/v1/ml/models/{model_id}/approve", headers=h(w, "supervisor"),
              json={"justification": "holdout ROC-AUC and calibration reviewed"}))
    deployment = ok(c.post(f"/api/v1/ml/models/{model_id}/deploy", headers=h(w, "supervisor"),
                           json={"reason": "first deployment"}))
    assert deployment["active"] and deployment["model_id"] == model_id
    assert ok(c.get("/api/v1/ml/monitoring", headers=h(w, "viewer")))["status"] == "no_observations"

    # -- inference inside a LangGraph supervisory run, bound into TRUST-SAT ------
    scored_run = analyse(w, 900, GenConfig(seed=4242, num_cse=1, num_alerts=24, num_cases=6,
                                           fast_closure_rate=0.5, missing_investigation_rate=0.3),
                         mode="graph")
    inf = ok(c.get(f"/api/v1/runs/{scored_run}/model-inference", headers=h(w, "viewer")))
    assert inf["model_id"] == model_id and inf["artifact_digest"] == model["artifact_digest"]
    assert inf["feature_version"] == model["feature_version"]
    assert inf["status"] in {"scored", "abstained"}
    if inf["status"] == "scored":
        assert 0.0 <= inf["score"] <= 1.0 and len(inf["features"]) == 11
    else:
        assert inf["abstain_reason"] in {"out_of_distribution", "low_confidence"}
    decide(w, scored_run, "confirm")
    verification = ok(c.post(f"/api/v1/runs/{scored_run}/verify", headers=h(w, "viewer")))
    assert verification["status"] == "verified"
    final = w["db"].query_one(
        "SELECT canonical_json FROM satsa_trust_finalizations WHERE run_id=?", (scored_run,))
    bound = json.loads(final["canonical_json"])["model_inference"]
    assert (bound["model_id"], bound["artifact_digest"], bound["content_digest"]) == (
        model_id, model["artifact_digest"], inf["content_digest"])

    monitoring = ok(c.get("/api/v1/ml/monitoring", headers=h(w, "viewer")))
    assert monitoring["status"] == "observed"
    assert monitoring["active_model"]["inferences"] == 1
    assert monitoring["active_model"]["realized_performance"]["status"] == "insufficient_labels"

    # -- drift: one observation is not evidence of anything -----------------------
    job = ml_job(w, c.post("/api/v1/ml/drift-checks", headers=h(w, "analyst", "drift-1"), json={}))
    assert job["result"]["status"] == "insufficient_data"
    report = ok(c.get("/api/v1/ml/drift-reports", headers=h(w, "viewer")))["items"][0]
    assert report["current_count"] == 1 and report["baseline_count"] == POPULATION
    assert ok(c.get("/api/v1/ml/retraining-requests", headers=h(w, "viewer")))["items"] == []

    # -- retraining decision -> retraining -> second approval -> deployment -------
    request = ok(c.post("/api/v1/ml/retraining-requests", headers=h(w, "analyst"),
                        json={"reason": "new decisions recorded"}), 201)
    assert request["status"] == "open" and request["trigger"] == "operator"
    dataset2 = ok(c.post("/api/v1/ml/datasets", headers=h(w, "analyst"),
                         json={"name": "review-outcome", "data_origin": "synthetic"}), 201)
    assert dataset2["version"] == 2 and dataset2["record_count"] == POPULATION + 1
    ml_job(w, c.post(f"/api/v1/ml/datasets/{dataset2['id']}/validate",
                     headers=h(w, "analyst", "validate-2")))
    assert c.post(f"/api/v1/ml/retraining-requests/{request['id']}/accept",
                  headers=h(w, "analyst", "accept"), json={"dataset_id": dataset2["id"]}
                  ).status_code == 403
    job = ml_job(w, c.post(f"/api/v1/ml/retraining-requests/{request['id']}/accept",
                           headers=h(w, "supervisor", "accept"), json={"dataset_id": dataset2["id"]}))
    second_id = job["result"]["model_id"]
    assert ok(c.get(f"/api/v1/ml/models/{second_id}", headers=h(w, "viewer")))["version"] == 2
    # The supervisor who started retraining may not approve its result.
    assert c.post(f"/api/v1/ml/models/{second_id}/approve", headers=h(w, "supervisor"),
                  json={"justification": "self"}).status_code == 403
    second = ok(c.post(f"/api/v1/ml/models/{second_id}/approve", headers=h(w, "admin"),
                       json={"justification": "independent review"}))
    assert second["state"] == "approved"
    ok(c.post(f"/api/v1/ml/models/{second_id}/deploy", headers=h(w, "supervisor"),
              json={"reason": "retrained"}))

    # -- rollback ------------------------------------------------------------------
    rollback = ok(c.post("/api/v1/ml/rollback", headers=h(w, "supervisor"),
                         json={"reason": "restore v1"}))
    assert rollback["model_id"] == model_id and rollback["kind"] == "rollback"
    models = {m["id"]: m for m in ok(c.get("/api/v1/ml/models", headers=h(w, "viewer")))["items"]}
    assert models[model_id]["deployed"] and not models[second_id]["deployed"]
    assert models[second_id]["state"] == "approved"
    history = ok(c.get("/api/v1/ml/deployments", headers=h(w, "viewer")))["items"]
    assert [d["kind"] for d in reversed(history)] == ["deploy", "deploy", "rollback"]

    # -- the recorded inference is tamper-evident after finalization --------------
    w["db"].execute("UPDATE satsa_ml_inferences SET score=0.999, status='scored' WHERE run_id=?",
                    (scored_run,))
    assert ok(c.post(f"/api/v1/runs/{scored_run}/verify", headers=h(w, "viewer")))[
        "status"] == "inconsistent"

    actions = {r["action"] for r in w["db"].query_all("SELECT action FROM audit_events")}
    assert {"ml.dataset.created", "ml.validate_dataset.completed", "ml.train.completed",
            "ml.model.approved", "ml.model.deployed", "ml.drift.completed",
            "ml.retraining.requested", "ml.retraining.accepted",
            "ml.model.rolled_back"} <= actions

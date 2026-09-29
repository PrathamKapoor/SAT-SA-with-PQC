"""MLOps routes of the hosted API (Phase 21).

Same conventions as every other route: /api/v1, session or bearer auth,
X-Organization-ID tenancy, server-side role checks (in MLOpsService),
Idempotency-Key on job-creating POSTs, limit/offset pagination and the
standard error envelope. Long work (validation, training, drift) is queued
for the worker and answered with 202 and the job.
"""

# No `from __future__ import annotations`: FastAPI must see the injected
# Tenant/Key/Limit/Offset dependency types as objects, not strings.
import json

from fastapi import Response

from satsa.mlops.service import MLOpsService

from . import schemas as s


def _json(value, default=None):
    return json.loads(value) if value else default


def dataset_view(row: dict) -> dict:
    return {
        **row,
        "label_counts": _json(row["label_counts_json"], {}),
        "validation": _json(row["validation_json"]),
        "lineage": _json(row["lineage_json"], {}),
    }


def job_view(row: dict) -> dict:
    return {**row, "params": _json(row["params_json"], {}), "result": _json(row["result_json"])}


def training_view(row: dict) -> dict:
    return {
        **row,
        "hyperparameters": _json(row["hyperparameters_json"], {}),
        "environment": _json(row["environment_json"]),
    }


def deployment_view(row: dict | None) -> dict | None:
    return None if row is None else {**row, "active": bool(row["active"])}


def inference_view(row: dict) -> dict:
    return {**row, "features": _json(row["features_json"])}


def page(result: dict, view) -> dict:
    return {**result, "items": [view(item) for item in result["items"]]}


def register(app, *, engine, storage, audit, Tenant, Key, Limit, Offset) -> None:
    def ml(t) -> MLOpsService:
        return MLOpsService(engine, t.organization_id, t.user_id, storage=storage, audit_service=audit)

    # -- datasets -----------------------------------------------------------
    @app.get("/api/v1/ml/datasets", response_model=s.Page[s.MLDataset], tags=["mlops"],
             operation_id="list_ml_datasets")
    def list_datasets(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return page(ml(t).list_datasets(limit, offset), dataset_view)

    @app.post("/api/v1/ml/datasets", response_model=s.MLDataset, status_code=201, tags=["mlops"],
              operation_id="create_ml_dataset")
    def create_dataset(body: s.MLDatasetInput, t: Tenant, response: Response):
        # Content-addressed: identical content returns the existing version (200).
        row, created = ml(t).create_dataset(body.name, body.data_origin)
        if not created:
            response.status_code = 200
        return dataset_view(row)

    @app.get("/api/v1/ml/datasets/{dataset_id}", response_model=s.MLDataset, tags=["mlops"],
             operation_id="get_ml_dataset")
    def get_dataset(dataset_id: str, t: Tenant):
        return dataset_view(ml(t).get_dataset(dataset_id))

    @app.post("/api/v1/ml/datasets/{dataset_id}/validate", response_model=s.MLJob, status_code=202,
              tags=["mlops"], operation_id="validate_ml_dataset")
    def validate_dataset(dataset_id: str, t: Tenant, key: Key):
        return job_view(ml(t).validate_dataset(dataset_id, key))

    # -- training -----------------------------------------------------------
    @app.post("/api/v1/ml/training-runs", response_model=s.MLJob, status_code=202, tags=["mlops"],
              operation_id="start_ml_training")
    def start_training(body: s.MLTrainingInput, t: Tenant, key: Key):
        return job_view(ml(t).start_training(body.dataset_id, body.hyperparameters, body.seed, key))

    @app.get("/api/v1/ml/training-runs", response_model=s.Page[s.MLTrainingRun], tags=["mlops"],
             operation_id="list_ml_training_runs")
    def list_training(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return page(ml(t).list_training_runs(limit, offset), training_view)

    @app.get("/api/v1/ml/training-runs/{training_run_id}", response_model=s.MLTrainingRun,
             tags=["mlops"], operation_id="get_ml_training_run")
    def get_training(training_run_id: str, t: Tenant):
        return training_view(ml(t).get_training_run(training_run_id))

    # -- jobs ---------------------------------------------------------------
    @app.get("/api/v1/ml/jobs/{job_id}", response_model=s.MLJob, tags=["mlops"],
             operation_id="get_ml_job")
    def get_job(job_id: str, t: Tenant):
        return job_view(ml(t).get_job(job_id))

    @app.post("/api/v1/ml/jobs/{job_id}/cancel", response_model=s.MLJob, tags=["mlops"],
              operation_id="cancel_ml_job")
    def cancel_job(job_id: str, t: Tenant):
        return job_view(ml(t).cancel_job(job_id))

    # -- models -------------------------------------------------------------
    @app.get("/api/v1/ml/models", response_model=s.Page[s.MLModel], tags=["mlops"],
             operation_id="list_ml_models")
    def list_models(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ml(t).list_models(limit, offset)

    @app.get("/api/v1/ml/models/{model_id}", response_model=s.MLModel, tags=["mlops"],
             operation_id="get_ml_model")
    def get_model(model_id: str, t: Tenant):
        return ml(t).get_model(model_id)

    @app.post("/api/v1/ml/models/{model_id}/approve", response_model=s.MLModel, tags=["mlops"],
              operation_id="approve_ml_model")
    def approve(model_id: str, body: s.MLApprovalInput, t: Tenant):
        return ml(t).approve(model_id, body.justification)

    @app.post("/api/v1/ml/models/{model_id}/deploy", response_model=s.MLDeployment, tags=["mlops"],
              operation_id="deploy_ml_model")
    def deploy(model_id: str, t: Tenant, body: s.MLDeployInput | None = None):
        return deployment_view(ml(t).deploy(model_id, body.reason if body else ""))

    @app.post("/api/v1/ml/models/{model_id}/retire", response_model=s.MLModel, tags=["mlops"],
              operation_id="retire_ml_model")
    def retire(model_id: str, body: s.MLReasonInput, t: Tenant):
        return ml(t).retire(model_id, body.reason)

    @app.post("/api/v1/ml/rollback", response_model=s.MLDeployment, tags=["mlops"],
              operation_id="rollback_ml_model")
    def rollback(body: s.MLRollbackInput, t: Tenant):
        return deployment_view(ml(t).rollback(body.target_model_id, body.reason))

    @app.get("/api/v1/ml/deployments", response_model=s.Page[s.MLDeployment], tags=["mlops"],
             operation_id="list_ml_deployments")
    def deployments(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return page(ml(t).list_deployments(limit, offset), deployment_view)

    # -- monitoring / drift / retraining -------------------------------------
    @app.get("/api/v1/ml/monitoring", response_model=s.MLMonitoring, tags=["mlops"],
             operation_id="get_ml_monitoring")
    def monitoring(t: Tenant):
        result = ml(t).monitoring()
        return {**result, "active_deployment": deployment_view(result["active_deployment"])}

    @app.post("/api/v1/ml/drift-checks", response_model=s.MLJob, status_code=202, tags=["mlops"],
              operation_id="start_ml_drift_check")
    def drift_check(t: Tenant, key: Key, body: s.MLDriftInput | None = None):
        return job_view(ml(t).start_drift_check(key, (body or s.MLDriftInput()).window))

    @app.get("/api/v1/ml/drift-reports", response_model=s.Page[s.MLDriftReport], tags=["mlops"],
             operation_id="list_ml_drift_reports")
    def drift_reports(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ml(t).list_drift_reports(limit, offset)

    @app.get("/api/v1/ml/retraining-requests", response_model=s.Page[s.MLRetrainingRequest],
             tags=["mlops"], operation_id="list_ml_retraining_requests")
    def retraining_requests(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ml(t).list_retraining_requests(limit, offset)

    @app.post("/api/v1/ml/retraining-requests", response_model=s.MLRetrainingRequest,
              status_code=201, tags=["mlops"], operation_id="request_ml_retraining")
    def request_retraining(body: s.MLReasonInput, t: Tenant):
        row = ml(t).request_retraining(body.reason)
        return {**row, "evidence": _json(row["evidence_json"], {})}

    @app.post("/api/v1/ml/retraining-requests/{request_id}/accept", response_model=s.MLJob,
              status_code=202, tags=["mlops"], operation_id="accept_ml_retraining")
    def accept_retraining(request_id: str, body: s.MLAcceptRetrainingInput, t: Tenant, key: Key):
        return job_view(ml(t).accept_retraining(request_id, body.dataset_id, key))

    @app.post("/api/v1/ml/retraining-requests/{request_id}/dismiss",
              response_model=s.MLRetrainingRequest, tags=["mlops"],
              operation_id="dismiss_ml_retraining")
    def dismiss_retraining(request_id: str, body: s.MLReasonInput, t: Tenant):
        row = ml(t).dismiss_retraining(request_id, body.reason)
        return {**row, "evidence": _json(row["evidence_json"], {})}

    # -- run inference ------------------------------------------------------
    @app.get("/api/v1/runs/{run_id}/model-inference", response_model=s.MLInference,
             tags=["mlops"], operation_id="get_run_model_inference")
    def run_inference(run_id: str, t: Tenant):
        return inference_view(ml(t).run_inference(run_id))

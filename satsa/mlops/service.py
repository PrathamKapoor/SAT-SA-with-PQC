"""Tenant-scoped MLOps operations for the hosted API.

Every method checks the caller's organization role server-side before touching
data, and every query is filtered by the organization, so identifiers from
another organization resolve as not found. Lifecycle transitions are appended
to the platform audit log.
"""

from __future__ import annotations

import json

from qsmlops.core.errors import NotFoundError
from qsmlops.security.permissions.model import (
    MODEL_APPROVE,
    MODEL_DEPLOY,
    MODEL_READ,
    MODEL_ROLLBACK,
    MODEL_TRAIN,
)
from satsa.errors import DomainValidationError
from satsa.mlops import datasets, jobs, monitoring, registry
from satsa.mlops.common import MODEL_NAME, audit
from satsa.mlops.inference import get_inference
from satsa.tenancy import TenantRepository


def _page(rows: list[dict], limit: int, offset: int) -> dict:
    return {"items": rows[:limit], "limit": limit, "offset": offset, "has_more": len(rows) > limit}


def _is_conflict(exc: Exception) -> bool:
    return "unique" in str(exc).lower() or "duplicate" in str(exc).lower()


class MLOpsService:
    def __init__(self, engine, organization_id: str, user_id: str, *, storage, audit_service) -> None:
        self.db = engine
        self.org = organization_id
        self.user = user_id
        self.storage = storage
        self.audit_service = audit_service
        self.tenant = TenantRepository(engine, organization_id, user_id)

    def _require(self, permission: str) -> None:
        self.tenant._require(permission)

    def _audit(self, action: str, resource: str, **metadata) -> None:
        audit(self.db, self.audit_service, user_id=self.user, organization_id=self.org,
              action=action, resource=resource, **metadata)

    def _list(self, sql: str, params: tuple, limit: int, offset: int) -> dict:
        rows = self.db.query_all(sql + " LIMIT ? OFFSET ?", (*params, limit + 1, offset))
        return _page(rows, limit, offset)

    # -- datasets -----------------------------------------------------------
    def list_datasets(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        return self._list(
            "SELECT * FROM satsa_ml_datasets WHERE organization_id=? ORDER BY created_at DESC, id",
            (self.org,), limit, offset)

    def get_dataset(self, dataset_id: str) -> dict:
        self._require(MODEL_READ)
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_datasets WHERE organization_id=? AND id=?", (self.org, dataset_id))
        if row is None:
            raise NotFoundError("dataset not found")
        return row

    def create_dataset(self, name: str, data_origin: str) -> tuple[dict, bool]:
        self._require(MODEL_TRAIN)
        try:
            row, created = datasets.create_dataset(
                self.db, self.storage, self.org, self.user, name=name, data_origin=data_origin)
        except Exception as exc:
            if not _is_conflict(exc):
                raise
            # A concurrent identical build won; return the version it created.
            row = self.db.query_one(
                "SELECT * FROM satsa_ml_datasets WHERE organization_id=? AND name=?"
                " ORDER BY version DESC LIMIT 1", (self.org, name))
            created = False
        if created:
            self._audit("ml.dataset.created", f"ml_dataset:{row['id']}", version=row["version"],
                        content_digest=row["content_digest"], data_origin=row["data_origin"])
        return row, created

    def validate_dataset(self, dataset_id: str, key: str) -> dict:
        self._require(MODEL_TRAIN)
        self.get_dataset(dataset_id)
        job, created = jobs.enqueue(self.db, self.org, self.user, kind="validate_dataset",
                                    subject_id=dataset_id, params={}, idempotency_key=key)
        if created:
            self._audit("ml.dataset.validation_requested", f"ml_dataset:{dataset_id}", ml_job_id=job["id"])
        return job

    # -- training -----------------------------------------------------------
    def start_training(self, dataset_id: str, hyperparameters: dict | None, seed: int | None,
                       key: str) -> dict:
        from satsa.mlops.training import normalize_hyperparameters

        self._require(MODEL_TRAIN)
        dataset = self.get_dataset(dataset_id)
        if dataset["status"] != "valid":
            raise DomainValidationError(f"dataset is {dataset['status']}; training needs a valid dataset")
        params = {"hyperparameters": normalize_hyperparameters(hyperparameters)}
        if seed is not None:
            params["seed"] = seed
        job, created = jobs.enqueue(self.db, self.org, self.user, kind="train",
                                    subject_id=dataset_id, params=params, idempotency_key=key)
        if created:
            self._audit("ml.training.requested", f"ml_dataset:{dataset_id}", ml_job_id=job["id"])
        return job

    def list_training_runs(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        return self._list(
            "SELECT * FROM satsa_ml_training_runs WHERE organization_id=? ORDER BY started_at DESC, id",
            (self.org,), limit, offset)

    def get_training_run(self, run_id: str) -> dict:
        self._require(MODEL_READ)
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_training_runs WHERE organization_id=? AND id=?", (self.org, run_id))
        if row is None:
            raise NotFoundError("training run not found")
        return row

    # -- jobs ---------------------------------------------------------------
    def get_job(self, job_id: str) -> dict:
        self._require(MODEL_READ)
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_jobs WHERE organization_id=? AND id=?", (self.org, job_id))
        if row is None:
            raise NotFoundError("job not found")
        return row

    def cancel_job(self, job_id: str) -> dict:
        self._require(MODEL_TRAIN)
        job = jobs.cancel(self.db, self.org, job_id)
        self._audit("ml.job.cancel_requested", f"ml_job:{job_id}", status=job["status"])
        return job

    # -- models -------------------------------------------------------------
    def list_models(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        page = self._list(
            "SELECT * FROM satsa_ml_models WHERE organization_id=? ORDER BY version DESC",
            (self.org,), limit, offset)
        page["items"] = [registry.model_view(self.db, self.org, m) for m in page["items"]]
        return page

    def get_model(self, model_id: str) -> dict:
        self._require(MODEL_READ)
        return registry.model_view(self.db, self.org, registry.get_model(self.db, self.org, model_id))

    def approve(self, model_id: str, justification: str) -> dict:
        self._require(MODEL_APPROVE)
        registry.approve(self.db, self.org, model_id, self.user, justification)
        self._audit("ml.model.approved", f"ml_model:{model_id}", justification=justification)
        return self.get_model(model_id)

    def deploy(self, model_id: str, reason: str) -> dict:
        self._require(MODEL_DEPLOY)
        try:
            deployment = registry.deploy(self.db, self.storage, self.org, model_id, self.user,
                                         reason=reason)
        except DomainValidationError:
            raise
        except Exception as exc:
            if _is_conflict(exc):
                raise DomainValidationError("model conflict: a concurrent deployment won") from exc
            raise
        self._audit("ml.model.deployed", f"ml_model:{model_id}", deployment_id=deployment["id"])
        return deployment

    def rollback(self, target_model_id: str | None, reason: str) -> dict:
        self._require(MODEL_ROLLBACK)
        if not reason.strip():
            raise DomainValidationError("rollback requires a reason")
        try:
            deployment = registry.rollback(self.db, self.storage, self.org, self.user,
                                           target_model_id=target_model_id, reason=reason.strip())
        except DomainValidationError:
            raise
        except Exception as exc:
            if _is_conflict(exc):
                raise DomainValidationError("model conflict: a concurrent deployment won") from exc
            raise
        self._audit("ml.model.rolled_back", f"ml_model:{deployment['model_id']}",
                    deployment_id=deployment["id"], reason=reason.strip())
        return deployment

    def retire(self, model_id: str, reason: str) -> dict:
        self._require(MODEL_APPROVE)
        registry.retire(self.db, self.org, model_id, self.user, reason)
        self._audit("ml.model.retired", f"ml_model:{model_id}", reason=reason)
        return self.get_model(model_id)

    def list_deployments(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        return self._list(
            "SELECT * FROM satsa_ml_deployments WHERE organization_id=? ORDER BY created_at DESC, id",
            (self.org,), limit, offset)

    # -- monitoring / drift / retraining -------------------------------------
    def monitoring(self) -> dict:
        self._require(MODEL_READ)
        return monitoring.summary(self.db, self.org)

    def start_drift_check(self, key: str, window: int) -> dict:
        self._require(MODEL_TRAIN)
        deployment = registry.active_deployment(self.db, self.org)
        if deployment is None:
            raise DomainValidationError("no deployed model to check for drift")
        job, created = jobs.enqueue(self.db, self.org, self.user, kind="drift",
                                    subject_id=deployment["model_id"], params={"window": window},
                                    idempotency_key=key)
        if created:
            self._audit("ml.drift.requested", f"ml_model:{deployment['model_id']}", ml_job_id=job["id"])
        return job

    def list_drift_reports(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        page = self._list(
            "SELECT * FROM satsa_ml_drift_reports WHERE organization_id=? ORDER BY created_at DESC, id",
            (self.org,), limit, offset)
        for row in page["items"]:
            row["details"] = json.loads(row.pop("details_json"))
        return page

    def list_retraining_requests(self, limit: int, offset: int) -> dict:
        self._require(MODEL_READ)
        page = self._list(
            "SELECT * FROM satsa_ml_retraining_requests WHERE organization_id=?"
            " ORDER BY created_at DESC, id", (self.org,), limit, offset)
        for row in page["items"]:
            row["evidence"] = json.loads(row.pop("evidence_json"))
        return page

    def request_retraining(self, reason: str) -> dict:
        self._require(MODEL_TRAIN)
        if not reason.strip():
            raise DomainValidationError("a retraining request needs a reason")
        active = registry.active_deployment(self.db, self.org)
        row = monitoring.open_request(
            self.db, self.org, trigger="operator", model_id=active["model_id"] if active else None,
            user_id=self.user, evidence={"reason": reason.strip()})
        self._audit("ml.retraining.requested", f"ml_retraining:{row['id']}", trigger="operator")
        return row

    def _open_request(self, request_id: str) -> dict:
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_retraining_requests WHERE organization_id=? AND id=?",
            (self.org, request_id))
        if row is None:
            raise NotFoundError("retraining request not found")
        if row["status"] != "open":
            raise DomainValidationError(f"retraining request already {row['status']}")
        return row

    def accept_retraining(self, request_id: str, dataset_id: str, key: str) -> dict:
        """Accepting starts retraining; the resulting model still needs approval."""
        self._require(MODEL_APPROVE)
        self._open_request(request_id)
        job = self.start_training(dataset_id, None, None, key)
        import time

        self.db.execute(
            "UPDATE satsa_ml_retraining_requests SET status='accepted',resolved_by=?,resolved_at=?,"
            "training_job_id=?,resolution='retraining started' WHERE organization_id=? AND id=?"
            " AND status='open'",
            (self.user, time.time(), job["id"], self.org, request_id))
        self._audit("ml.retraining.accepted", f"ml_retraining:{request_id}", ml_job_id=job["id"])
        return job

    def dismiss_retraining(self, request_id: str, reason: str) -> dict:
        import time

        self._require(MODEL_APPROVE)
        self._open_request(request_id)
        if not reason.strip():
            raise DomainValidationError("dismissal requires a reason")
        self.db.execute(
            "UPDATE satsa_ml_retraining_requests SET status='dismissed',resolved_by=?,resolved_at=?,"
            "resolution=? WHERE organization_id=? AND id=? AND status='open'",
            (self.user, time.time(), reason.strip(), self.org, request_id))
        self._audit("ml.retraining.dismissed", f"ml_retraining:{request_id}", reason=reason.strip())
        return self.db.query_one(
            "SELECT * FROM satsa_ml_retraining_requests WHERE organization_id=? AND id=?",
            (self.org, request_id))

    # -- run inference ------------------------------------------------------
    def run_inference(self, run_id: str) -> dict:
        self._require(MODEL_READ)
        if self.db.query_one(
            "SELECT id FROM satsa_runs WHERE organization_id=? AND id=?", (self.org, run_id)
        ) is None:
            raise NotFoundError("run not found")
        row = get_inference(self.db, self.org, run_id)
        if row is None:
            raise NotFoundError("no model inference recorded for this run")
        return row


__all__ = ["MLOpsService", "MODEL_NAME"]

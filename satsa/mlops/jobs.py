"""Background MLOps jobs: dataset validation, training, drift detection.

These run in the existing worker process (``sat-sa-worker``), never inside an
HTTP request. The queue follows the analysis execution queue's rules:

* a job is claimed under a lease with a generation number; a worker that
  loses its lease cannot commit results;
* a worker that dies leaves an expired lease, which another worker reclaims
  until ``max_attempts`` is reached, after which the job fails as
  ``lease_exhausted`` instead of staying stuck;
* transient errors retry with backoff; validation errors fail immediately;
* cancellation of a queued job is immediate, of a running job is honoured
  at the next boundary (before results are committed);
* every handler is idempotent: row identifiers derive from the job id, so a
  retried job finds and reuses what an earlier attempt already wrote.
"""

from __future__ import annotations

import json
import time

from qsmlops.core.errors import NotFoundError
from satsa.errors import DomainValidationError
from satsa.mlops import registry
from satsa.mlops.common import audit, dumps, log, stable_id
from satsa.mlops.datasets import load_snapshot, validate_snapshot

JOB_KINDS = ("validate_dataset", "train", "drift")


class JobCancelled(Exception):
    pass


class LeaseLost(Exception):
    pass


def enqueue(db, org: str, user_id: str, *, kind: str, subject_id: str, params: dict,
            idempotency_key: str) -> tuple[dict, bool]:
    if kind not in JOB_KINDS:
        raise DomainValidationError("unknown ML job kind")
    existing = db.query_one(
        "SELECT * FROM satsa_ml_jobs WHERE organization_id=? AND kind=? AND idempotency_key=?",
        (org, kind, idempotency_key),
    )
    if existing is not None:
        if existing["subject_id"] != subject_id or json.loads(existing["params_json"]) != params:
            raise DomainValidationError("idempotency key already used for a different request")
        return existing, False
    now = time.time()
    job_id = stable_id("mljob", org, kind, idempotency_key)
    db.execute(
        "INSERT INTO satsa_ml_jobs (id,organization_id,kind,subject_id,status,params_json,"
        "available_at,idempotency_key,requested_by,created_at,updated_at)"
        " VALUES (?,?,?,?,'queued',?,?,?,?,?,?)",
        (job_id, org, kind, subject_id, dumps(params), now, idempotency_key, user_id, now, now),
    )
    return db.query_one("SELECT * FROM satsa_ml_jobs WHERE id=?", (job_id,)), True


def cancel(db, org: str, job_id: str) -> dict:
    now = time.time()
    with db.transaction():
        job = db.query_one(
            "SELECT * FROM satsa_ml_jobs WHERE organization_id=? AND id=?", (org, job_id)
        )
        if job is None:
            raise NotFoundError("job not found")
        if job["status"] in ("queued", "retry_wait"):
            db.execute(
                "UPDATE satsa_ml_jobs SET status='cancelled',updated_at=?,completed_at=? WHERE id=?",
                (now, now, job_id),
            )
        elif job["status"] == "running":
            db.execute(
                "UPDATE satsa_ml_jobs SET status='cancel_requested',updated_at=? WHERE id=?",
                (now, job_id),
            )
    return db.query_one("SELECT * FROM satsa_ml_jobs WHERE id=?", (job_id,))


class MLJobQueue:
    def __init__(self, db, *, lease_seconds: float = 300.0) -> None:
        self.db = db
        self.lease_seconds = lease_seconds

    def claim(self, worker_id: str) -> dict | None:
        now = time.time()
        with self.db.transaction():
            self.db.execute(
                "UPDATE satsa_ml_jobs SET status='failed',error=?,lease_owner='',updated_at=?,"
                "completed_at=? WHERE status IN ('running','cancel_requested') AND lease_expires_at<=?"
                " AND attempt_count>=max_attempts",
                ("lease_exhausted: worker stopped before completion after the maximum attempts",
                 now, now, now),
            )
            # Nothing a dead worker started may stay 'running' or 'validating'.
            self.db.execute(
                "UPDATE satsa_ml_training_runs SET status='failed',error='lease_exhausted',"
                "finished_at=? WHERE status='running' AND job_id IN (SELECT id FROM satsa_ml_jobs"
                " WHERE kind='train' AND status='failed')",
                (now,),
            )
            self.db.execute(
                "UPDATE satsa_ml_datasets SET status='created' WHERE status='validating' AND id IN"
                " (SELECT subject_id FROM satsa_ml_jobs WHERE kind='validate_dataset'"
                " AND status='failed' AND organization_id=satsa_ml_datasets.organization_id)"
                " AND NOT EXISTS (SELECT 1 FROM satsa_ml_jobs a WHERE a.kind='validate_dataset'"
                " AND a.subject_id=satsa_ml_datasets.id AND a.status IN ('queued','running',"
                "'retry_wait','cancel_requested'))",
            )
            lock = " FOR UPDATE SKIP LOCKED" if self.db.dialect == "postgresql" else ""
            candidate = self.db.query_one(
                "SELECT * FROM satsa_ml_jobs WHERE"
                " (status IN ('queued','retry_wait') AND available_at<=? AND attempt_count<max_attempts)"
                " OR (status IN ('running','cancel_requested') AND lease_expires_at<=?"
                " AND attempt_count<max_attempts)"
                " ORDER BY available_at, created_at LIMIT 1" + lock,
                (now, now),
            )
            if candidate is None:
                return None
            generation = int(candidate["lease_generation"]) + 1
            status = "cancel_requested" if candidate["status"] == "cancel_requested" else "running"
            self.db.execute(
                "UPDATE satsa_ml_jobs SET status=?,attempt_count=attempt_count+1,lease_owner=?,"
                "lease_generation=?,lease_expires_at=?,updated_at=? WHERE id=?",
                (status, worker_id, generation, now + self.lease_seconds, now, candidate["id"]),
            )
            return self.db.query_one("SELECT * FROM satsa_ml_jobs WHERE id=?", (candidate["id"],))

    def _owned(self, job: dict) -> dict:
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_jobs WHERE id=? AND lease_owner=? AND lease_generation=?",
            (job["id"], job["lease_owner"], job["lease_generation"]),
        )
        if row is None or row["status"] not in ("running", "cancel_requested"):
            raise LeaseLost(job["id"])
        return row

    def boundary(self, job: dict) -> None:
        """Raise if the lease was lost or cancellation was requested."""
        if self._owned(job)["status"] == "cancel_requested":
            raise JobCancelled(job["id"])

    def finish(self, job: dict, status: str, *, result=None, error: str = "") -> bool:
        now = time.time()
        with self.db.transaction():
            self._owned(job)
            self.db.execute(
                "UPDATE satsa_ml_jobs SET status=?,result_json=?,error=?,lease_owner='',"
                "lease_expires_at=NULL,updated_at=?,completed_at=? WHERE id=? AND lease_generation=?",
                (status, dumps(result) if result is not None else None, error, now, now,
                 job["id"], job["lease_generation"]),
            )
        return True

    def retry(self, job: dict, error: str) -> str:
        now = time.time()
        exhausted = int(job["attempt_count"]) >= int(job["max_attempts"])
        status = "failed" if exhausted else "retry_wait"
        self.db.execute(
            "UPDATE satsa_ml_jobs SET status=?,error=?,lease_owner='',lease_expires_at=NULL,"
            "available_at=?,updated_at=?,completed_at=? WHERE id=? AND lease_generation=?",
            (status, error, now + 5.0 * int(job["attempt_count"]), now,
             now if exhausted else None, job["id"], job["lease_generation"]),
        )
        return status


class MLJobWorker:
    """Executes one claimed job per call; used by ``sat-sa-worker``'s loop."""

    def __init__(self, db, storage, *, worker_id: str, audit_service=None,
                 lease_seconds: float = 300.0) -> None:
        self.db = db
        self.storage = storage
        self.worker_id = worker_id
        self.audit = audit_service
        self.queue = MLJobQueue(db, lease_seconds=lease_seconds)

    def run_once(self) -> str | None:
        job = self.queue.claim(self.worker_id)
        if job is None:
            return None
        org = job["organization_id"]
        context = {"ml_job_id": job["id"], "kind": job["kind"], "organization_id": org}
        try:
            self.queue.boundary(job)
            handler = {"validate_dataset": self._validate, "train": self._train,
                       "drift": self._drift}[job["kind"]]
            result = handler(job)
            self.queue.boundary(job)
            self.queue.finish(job, "completed", result=result)
            self._audit(job, f"ml.{job['kind']}.completed", result)
            log.info("ml job completed", extra=context)
            return "completed"
        except JobCancelled:
            self._on_cancel(job)
            self.queue.finish(job, "cancelled", error="cancelled on request")
            self._audit(job, f"ml.{job['kind']}.cancelled", None)
            return "cancelled"
        except LeaseLost:
            log.warning("ml job lease lost", extra=context)
            return "lease_lost"
        except (DomainValidationError, NotFoundError) as exc:
            self._on_failure(job, str(exc))
            self.queue.finish(job, "failed", error=str(exc))
            self._audit(job, f"ml.{job['kind']}.failed", {"error": str(exc)})
            return "failed"
        except Exception as exc:  # transient: storage, database, interpreter errors
            log.exception("ml job attempt failed", extra=context)
            outcome = self.queue.retry(job, f"{type(exc).__name__}: {exc}")
            if outcome == "failed":
                self._on_failure(job, f"{type(exc).__name__}: {exc}")
                self._audit(job, f"ml.{job['kind']}.failed", {"error": type(exc).__name__})
            return outcome

    def _audit(self, job: dict, action: str, result) -> None:
        try:
            audit(self.db, self.audit, user_id=job["requested_by"],
                  organization_id=job["organization_id"], action=action,
                  resource=f"ml_job:{job['id']}", subject_id=job["subject_id"],
                  worker_id=self.worker_id,
                  outcome=(result or {}).get("status") if isinstance(result, dict) else None)
        except Exception:
            log.exception("ml audit append failed", extra={"ml_job_id": job["id"]})

    def _dataset(self, org: str, dataset_id: str) -> dict:
        row = self.db.query_one(
            "SELECT * FROM satsa_ml_datasets WHERE organization_id=? AND id=?", (org, dataset_id)
        )
        if row is None:
            raise NotFoundError("dataset not found")
        return row

    # -- validation ---------------------------------------------------------
    def _validate(self, job: dict) -> dict:
        org = job["organization_id"]
        dataset = self._dataset(org, job["subject_id"])
        if dataset["status"] in ("valid", "invalid"):
            return json.loads(dataset["validation_json"])  # already decided; immutable
        self.db.execute(
            "UPDATE satsa_ml_datasets SET status='validating' WHERE organization_id=? AND id=?"
            " AND status='created'",
            (org, dataset["id"]),
        )
        try:
            snapshot = load_snapshot(self.storage, dataset)
        except DomainValidationError as exc:
            report = {"status": "invalid", "checks": [
                {"check": "integrity", "passed": False, "detail": str(exc)}]}
        else:
            report = validate_snapshot(snapshot)
        self.queue.boundary(job)
        self.db.execute(
            "UPDATE satsa_ml_datasets SET status=?,validation_json=?,validated_at=?"
            " WHERE organization_id=? AND id=? AND status='validating'",
            (report["status"], dumps(report), time.time(), org, dataset["id"]),
        )
        return report

    # -- training -----------------------------------------------------------
    def _train(self, job: dict) -> dict:
        from satsa.mlops import training

        org = job["organization_id"]
        params = json.loads(job["params_json"])
        dataset = self._dataset(org, job["subject_id"])
        if dataset["status"] != "valid":
            raise DomainValidationError(f"dataset is {dataset['status']}; training needs a valid dataset")
        run_id = stable_id("mltrain", job["id"])
        run = self.db.query_one(
            "SELECT * FROM satsa_ml_training_runs WHERE organization_id=? AND id=?", (org, run_id)
        )
        if run is not None and run["status"] == "completed":
            return {"status": "completed", "training_run_id": run_id, "model_id": run["model_id"]}
        hyperparameters = training.normalize_hyperparameters(params.get("hyperparameters"))
        seed = int(params.get("seed", training.DEFAULT_SEED))
        env = training.environment()
        if run is None:
            self.db.execute(
                "INSERT INTO satsa_ml_training_runs (id,organization_id,job_id,dataset_id,"
                "feature_version,model_family,hyperparameters_json,seed,environment_json,status,"
                "requested_by,started_at) VALUES (?,?,?,?,?,?,?,?,?,'running',?,?)",
                (run_id, org, job["id"], dataset["id"], dataset["feature_version"],
                 training.MODEL_FAMILY, dumps(hyperparameters), seed, dumps(env),
                 job["requested_by"], time.time()),
            )
        snapshot = load_snapshot(self.storage, dataset)
        document, evaluation = training.train(snapshot, hyperparameters=hyperparameters, seed=seed)
        # Last cancellation point: nothing below is visible until committed.
        self.queue.boundary(job)
        run = self.db.query_one("SELECT * FROM satsa_ml_training_runs WHERE id=?", (run_id,))
        model = registry.register(self.db, self.storage, org, training_run=run, dataset=dataset,
                                  document=document, evaluation=evaluation, environment=env)
        self.db.execute(
            "UPDATE satsa_ml_training_runs SET status='completed',finished_at=? WHERE id=?",
            (time.time(), run_id),
        )
        return {"status": "completed", "training_run_id": run_id, "model_id": model["id"],
                "model_state": model["state"]}

    def _drift(self, job: dict) -> dict:
        from satsa.mlops.monitoring import detect_drift

        report = detect_drift(self.db, self.storage, job["organization_id"], job)
        return {"status": report["result"], "drift_report_id": report["id"]}

    def _on_cancel(self, job: dict) -> None:
        if job["kind"] == "train":
            self.db.execute(
                "UPDATE satsa_ml_training_runs SET status='cancelled',finished_at=?"
                " WHERE organization_id=? AND job_id=? AND status='running'",
                (time.time(), job["organization_id"], job["id"]),
            )
        elif job["kind"] == "validate_dataset":
            self._reset_validating(job)

    def _on_failure(self, job: dict, error: str) -> None:
        if job["kind"] == "train":
            self.db.execute(
                "UPDATE satsa_ml_training_runs SET status='failed',error=?,finished_at=?"
                " WHERE organization_id=? AND job_id=? AND status='running'",
                (error, time.time(), job["organization_id"], job["id"]),
            )
        elif job["kind"] == "validate_dataset":
            self._reset_validating(job)

    def _reset_validating(self, job: dict) -> None:
        self.db.execute(
            "UPDATE satsa_ml_datasets SET status='created' WHERE organization_id=? AND id=?"
            " AND status='validating'",
            (job["organization_id"], job["subject_id"]),
        )

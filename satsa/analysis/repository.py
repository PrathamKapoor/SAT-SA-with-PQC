"""Persistence for AnalysisRun, Observation, Finding, Job (Phase 4)."""
from __future__ import annotations

import json
import time

from qsmlops.crypto.hashing import canonical_json, digest_document
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
    Observation,
    SourceRecord,
)
from satsa.domain.runs import AnalysisRun


def _j(value, default="[]"):
    """JSON-encode a value for SQLite storage. MUST use
    ``ensure_ascii=False`` and ``sort_keys=True`` to produce the
    same byte sequence as ``canonical_json`` (otherwise
    non-ASCII strings would be escaped as ``\\uXXXX`` here but
    kept as raw UTF-8 in the digest, breaking round-trip
    verification)."""
    return json.dumps(
        value if value is not None else json.loads(default),
        sort_keys=True, ensure_ascii=False, default=str,
        separators=(",", ":"),
        allow_nan=False,
    )


def _d(obj) -> str:
    """Content digest of a domain object. Single source of truth.

    For Findings: builds the exact fake-row the storage path will
    write and digests it via ``live_finding_digest`` (the same
    function the verification path uses). This guarantees the
    stored content_digest equals the live digest whenever the
    round-trip through the row's JSON columns is exact.

    For AnalysisRuns: same idea, using ``canonical_run_dict_from_row``.

    For other objects (Observation, Job): the original
    ``to_dict()`` is used directly."""
    from satsa.analysis.canonical import (
        canonical_run_dict_from_row,
        live_finding_digest,
    )
    if isinstance(obj, Finding):
        fake_row = {
            "id": obj.id,
            "observation_id": obj.observation_id,
            "rule_or_category": obj.rule_or_category,
            "state": obj.state,
            "rationale": obj.rationale,
            "scoped_subjects_json": _j(obj.scoped_subjects),
            "statistic": obj.statistic,
            "effect": obj.effect,
            "threshold": obj.threshold,
            "limitations": obj.limitations,
            "confidence_json": _j(
                obj.confidence.to_dict() if obj.confidence else {}, "{}"
            ),
            "evidence_refs_json": _j(obj.evidence_refs),
        }
        return live_finding_digest(fake_row)
    if isinstance(obj, AnalysisRun):
        fake_row = {
            "id": obj.id,
            "entity_id": obj.entity_id,
            "assessment_id": obj.assessment_id,
            "snapshot_digest": obj.snapshot_digest,
            "code_version": obj.code_version,
            "analytics_version": obj.analytics_version,
            "model_version": obj.model_version,
            "status": obj.status,
            "started_at": obj.started_at,
            "finished_at": obj.finished_at,
            "error": obj.error or "",
            "observation_ids_json": _j(obj.observation_ids or [], "[]"),
        }
        # The stored content_digest is the seed: SHA3-256 over
        # the canonical run dict EXCLUDING the content_digest
        # field. Verification re-derives the same seed from
        # the row and compares; a tampered content_digest column
        # therefore diverges from the live seed and is detected.
        return digest_document(canonical_run_dict_from_row(fake_row))
    return digest_document(obj.to_dict())


class RunStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, run: AnalysisRun, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_runs (id, entity_id, assessment_id, snapshot_digest,"
            " baseline_digests_json, code_version, analytics_version, model_version,"
            " status, started_at, finished_at, observation_ids_json, finding_ids_json,"
            " error, summary_json, content_digest, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run.id, run.entity_id, run.assessment_id, run.snapshot_digest,
             _j(run.baseline_digests, "{}"), run.code_version, run.analytics_version,
             run.model_version, run.status, run.started_at, run.finished_at,
             _j(run.observation_ids), "[]", run.error, "{}", _d(run), created_at),
        )

    def set_status(self, run_id: str, status: str, *,
                   finished_at: float | None = None,
                   observation_ids: list | None = None,
                   finding_ids: list | None = None,
                   error: str = "",
                   summary: dict | None = None) -> None:
        sets, params = ["status=?", "error=?"], [status, error]
        if finished_at is not None:
            sets.append("finished_at=?")
            params.append(finished_at)
        if observation_ids is not None:
            sets.append("observation_ids_json=?")
            params.append(_j(observation_ids))
        if finding_ids is not None:
            sets.append("finding_ids_json=?")
            params.append(_j(finding_ids))
        if summary is not None:
            sets.append("summary_json=?")
            params.append(_j(summary, "{}"))
        params.append(run_id)
        self._db.execute(
            f"UPDATE satsa_runs SET {', '.join(sets)} WHERE id=?", params)

    def get(self, run_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM satsa_runs WHERE id=?", (run_id,))
        return dict(row) if row else None

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_runs WHERE entity_id=? AND assessment_id=?"
            " ORDER BY created_at", (entity_id, assessment_id))]


class ObservationStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, obs: Observation, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_observations (id, run_id, worker_name,"
            " detector_version, entity_id, assessment_id, scope_json, state,"
            " created_at, content_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (obs.id, obs.run_id, obs.worker_name, obs.detector_version,
             obs.entity_id, obs.assessment_id, _j(obs.scope), "",
             created_at, _d(obs)),
        )

    def list_for_run(self, run_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_observations WHERE run_id=?"
            " ORDER BY created_at", (run_id,))]

    def set_state(self, observation_id: str, state: str) -> None:
        self._db.execute(
            "UPDATE satsa_observations SET state=? WHERE id=?",
            (state, observation_id))


class FindingStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, f: Finding, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_findings (id, observation_id, rule_or_category,"
            " state, rationale, scoped_subjects_json, statistic, effect, threshold,"
            " confidence_json, evidence_refs_json, limitations, created_at,"
            " content_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f.id, f.observation_id, f.rule_or_category, f.state, f.rationale,
             _j(f.scoped_subjects), f.statistic, f.effect, f.threshold,
             _j(f.confidence.to_dict() if f.confidence else {}, "{}"),
             _j(f.evidence_refs), f.limitations, created_at, _d(f)),
        )

    def list_for_run(self, run_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_findings WHERE observation_id IN"
            " (SELECT id FROM satsa_observations WHERE run_id=?)"
            " ORDER BY created_at", (run_id,))]


class JobStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, j, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_jobs (id, run_id, worker_name, status,"
            " started_at, finished_at, error, result_json, created_at,"
            " content_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (j.id, j.run_id, j.worker_name, j.status, j.started_at,
             j.finished_at, j.error,
             _j(j.result.to_dict() if j.result else {}, "{}"),
             created_at, _d(j)),
        )

    def list_for_run(self, run_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_jobs WHERE run_id=?"
            " ORDER BY created_at", (run_id,))]


class SourceRecordRefStore:
    """Lightweight source-record lookup by submission+locator so workers
    can attach evidence_refs (SourceRecord IDs) to Findings."""

    def __init__(self, engine) -> None:
        self._db = engine

    def find_by_locator(self, submission_id: str, locator: str) -> str | None:
        row = self._db.query_one(
            "SELECT id FROM satsa_source_records"
            " WHERE submission_id=? AND locator=? LIMIT 1",
            (submission_id, locator))
        return row["id"] if row else None

    def list_for_submission(self, submission_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_source_records WHERE submission_id=?",
            (submission_id,))]

"""Single authoritative canonicalization for SAT-SA trust digests.

The trust layer signs the canonical JSON of a domain object's
``to_dict()``. Verification re-derives the same canonical JSON
from the persisted row and checks the signature. This module
owns the canonical reconstruction so insert-time and
verification-time cannot drift.

Three rules, enforced here and nowhere else:

1. **One encoding**: ``canonical_json`` from ``qsmlops.crypto.hashing``,
   which uses ``sort_keys=True``, ``ensure_ascii=False``,
   ``separators=(",", ":")``, ``allow_nan=False``.

2. **One source of truth for the Finding dict shape**: every
   persisted Finding column maps to exactly one key in
   ``canonical_finding_dict_from_row``; every key the live
   reconstruction emits is also in that mapping. There is no
   other place that builds a Finding's content digest.

3. **One source of truth for the AnalysisRun dict shape**: same
   idea — the run path round-trips through ``AnalysisRun.from_dict``
   (which is the same constructor the insert path used to build
   the object that was digested). The run reconstruction lives
   here too for symmetry.

The previous design had two paths (insert and live) independently
build the dict, and the ``_j`` helper used ``json.dumps`` with
``ensure_ascii=True`` (the default) while the digest used
``canonical_json`` with ``ensure_ascii=False`` — a Unicode
character in any string field (e.g. an em-dash in a rationale)
broke the round-trip. The ``_j`` helper has been corrected to use
the same ``ensure_ascii=False`` so the two paths now produce
byte-equivalent canonical JSON.
"""

from __future__ import annotations

import json

from qsmlops.core.errors import PermissionDeniedError
from qsmlops.crypto.hashing import digest_document

# ---------------------------------------------------------------------------
# Finding canonicalization
# ---------------------------------------------------------------------------

# Single column → field mapping. Every Finding column the
# repository writes (see ``FindingStore.insert``) is listed here;
# any field not in this table is a bug.
_FINDING_COLUMN_TO_KEY: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("observation_id", "observation_id"),
    ("rule_or_category", "rule_or_category"),
    ("state", "state"),
    ("rationale", "rationale"),
    ("statistic", "statistic"),
    ("effect", "effect"),
    ("threshold", "threshold"),
    ("limitations", "limitations"),
)


def _parse_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            data = json.loads(value)
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []
    return []


def _parse_json_confidence(value) -> dict | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            data = json.loads(value)
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None
    return None


def canonical_finding_dict_from_row(row: dict) -> dict:
    """Reconstruct the exact ``Finding.to_dict()`` shape from a
    persisted row. This is the single authoritative
    reconstruction path used by the trust verification layer.

    The returned dict has the same keys in the same canonical
    order as ``Finding.to_dict()`` so that the SHA3-256 digest is
    byte-equivalent to the one computed at insert time."""
    d: dict = {}
    for column, key in _FINDING_COLUMN_TO_KEY:
        d[key] = row.get(column)
    d["scoped_subjects"] = _parse_json_list(
        row.get("scoped_subjects_json") or row.get("scoped_subjects")
    )
    d["evidence_refs"] = _parse_json_list(
        row.get("evidence_refs_json") or row.get("evidence_refs")
    )
    confidence = _parse_json_confidence(row.get("confidence_json"))
    d["confidence"] = confidence
    d["schema_version"] = row.get("schema_version", 1)
    return d


def live_finding_digest(row: dict) -> str:
    """The content digest of a persisted Finding row, recomputed
    from the row's columns. Byte-equivalent to the digest
    produced at insert time."""
    return digest_document(canonical_finding_dict_from_row(row))


# ---------------------------------------------------------------------------
# Run canonicalization
# ---------------------------------------------------------------------------

_RUN_COLUMN_TO_KEY: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("entity_id", "entity_id"),
    ("assessment_id", "assessment_id"),
    ("snapshot_digest", "snapshot_digest"),
    ("code_version", "code_version"),
    ("analytics_version", "analytics_version"),
    ("model_version", "model_version"),
    ("status", "status"),
    ("started_at", "started_at"),
    ("finished_at", "finished_at"),
    ("error", "error"),
)


def canonical_run_dict_from_row(row: dict) -> dict:
    """Reconstruct the exact ``AnalysisRun.to_dict()`` shape from a
    persisted row. Same single-source-of-truth rule as for
    findings."""
    d: dict = {}
    for column, key in _RUN_COLUMN_TO_KEY:
        d[key] = row.get(column)
    obs_ids_raw = row.get("observation_ids_json") or "[]"
    if isinstance(obs_ids_raw, str):
        try:
            obs_ids = json.loads(obs_ids_raw)
        except (TypeError, ValueError):
            obs_ids = []
    else:
        obs_ids = obs_ids_raw or []
    d["observation_ids"] = list(obs_ids) if isinstance(obs_ids, list) else []
    d["baseline_digests"] = {}  # never persisted (always {})
    d["schema_version"] = row.get("schema_version", 1)
    return d


def live_run_digest(row: dict) -> str:
    """The content digest of a persisted AnalysisRun row.

    The persisted ``content_digest`` column is the seed digest
    of every column EXCEPT itself (see ``RunStore.insert`` /
    ``_d(AnalysisRun)``). Verification re-derives the seed from
    the row's other columns and compares it to the stored
    column. If a tamper modifies the stored column, the
    comparison fails because the live seed (from the other
    columns) and the stored column diverge.
    """
    return digest_document(canonical_run_dict_from_row(row))


def live_run_seed(row: dict) -> str:
    """The content digest of a persisted AnalysisRun row
    *excluding* the stored ``content_digest`` column. This is
    the value the receipt was signed over and is the value
    that should match the stored column on any row that has
    not been tampered with."""
    d = canonical_run_dict_from_row(row)
    d.pop("content_digest", None)
    return digest_document(d)


def _strict_json(value: str, expected: type, *, nullable: bool = False):
    """Supervisory records reject malformed/ambiguous structured fields."""

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate canonical JSON field")
            result[key] = item
        return result

    def constant(_value):
        raise ValueError("non-finite canonical JSON number")

    parsed = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    if parsed is None and nullable:
        return None
    if not isinstance(parsed, expected):
        raise TypeError("invalid canonical JSON field type")
    return parsed


def supervisory_document(engine, organization_id: str, run_id: str) -> dict:
    """Versioned, deliberate final-state commitment reconstructed from live data.

    No operational queue/checkpoint fields or stored verified flags are signed.
    Digest sets commit to the complete persisted population, including missing
    or added rows. They keep the receipt small without embedding raw evidence.
    """
    run = engine.query_one(
        "SELECT r.*,c.submission_id,c.submission_version_id FROM satsa_runs r"
        " JOIN satsa_run_context c ON c.run_id=r.id AND c.organization_id=r.organization_id"
        " JOIN satsa_submissions s ON s.id=c.submission_id AND s.organization_id=c.organization_id"
        " AND s.entity_id=r.entity_id AND s.assessment_id=r.assessment_id"
        " JOIN satsa_entities e ON e.id=s.entity_id AND e.organization_id=c.organization_id"
        " JOIN satsa_assessments a ON a.id=s.assessment_id AND a.entity_id=e.id"
        " AND a.organization_id=c.organization_id"
        " JOIN satsa_submission_versions v ON v.id=c.submission_version_id"
        " AND v.organization_id=c.organization_id AND v.submission_id=s.id"
        " WHERE r.organization_id=? AND r.id=? AND v.status='valid'",
        (organization_id, run_id),
    )
    if run is None:
        raise PermissionDeniedError("run context does not belong to organization")
    decision = engine.query_one(
        "SELECT * FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=?",
        (organization_id, run_id),
    )
    if decision is None:
        raise ValueError("authoritative supervisory decision missing")
    user = engine.query_one(
        "SELECT identity_id FROM satsa_users WHERE id=?", (decision["user_id"],)
    )
    if user is None or user["identity_id"] != decision["principal_identity_id"]:
        raise ValueError("decision reviewer relationship mismatch")
    decision_doc = {
        key: decision[key]
        for key in (
            "id",
            "organization_id",
            "run_id",
            "finding_id",
            "user_id",
            "principal_identity_id",
            "action",
            "reason",
            "finding_content_digest",
            "created_at",
        )
    }
    # Preserve the established decision float epoch, not a rounded timestamp.
    original = {
        key: value
        for key, value in decision_doc.items()
        if key not in {"id", "user_id"}
    }
    if digest_document(original) != decision["content_digest"]:
        raise ValueError("decision digest mismatch")
    findings = engine.query_all(
        "SELECT f.* FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id"
        " WHERE o.run_id=? ORDER BY f.id",
        (run_id,),
    )
    finding_ids = {row["id"] for row in findings}
    for row in findings:
        _strict_json(row["scoped_subjects_json"], list)
        _strict_json(row["evidence_refs_json"], list)
        _strict_json(row["confidence_json"], dict, nullable=True)
    if decision["finding_id"] is not None and decision["finding_id"] not in finding_ids:
        raise ValueError("decision finding relationship mismatch")
    finding_refs = [
        {"id": row["id"], "digest": live_finding_digest(row)} for row in findings
    ]
    if any(live_finding_digest(row) != row["content_digest"] for row in findings):
        raise ValueError("finding digest mismatch")
    if decision["finding_id"] is not None:
        selected = next(
            item for item in finding_refs if item["id"] == decision["finding_id"]
        )
        if selected["digest"] != decision["finding_content_digest"]:
            raise ValueError("decision finding digest mismatch")
    observations = engine.query_all(
        "SELECT * FROM satsa_observations WHERE run_id=? ORDER BY id", (run_id,)
    )
    obs_refs = []
    for row in observations:
        if (
            row["entity_id"] != run["entity_id"]
            or row["assessment_id"] != run["assessment_id"]
        ):
            raise ValueError("observation ownership mismatch")
        doc = {
            key: row[key]
            for key in (
                "id",
                "run_id",
                "worker_name",
                "detector_version",
                "entity_id",
                "assessment_id",
                "state",
                "created_at",
            )
        }
        doc["scope"] = _strict_json(row["scope_json"], dict)
        obs_refs.append({"id": row["id"], "digest": digest_document(doc)})
    risk = engine.query_one(
        "SELECT * FROM satsa_run_risk WHERE organization_id=? AND run_id=?",
        (organization_id, run_id),
    )
    if risk is None:
        raise ValueError("risk record missing")
    risk_doc = {
        "profile": _strict_json(risk["profile_json"], dict),
        "algorithm_version": risk["algorithm_version"],
    }
    if digest_document(risk_doc["profile"]) != risk["content_digest"]:
        raise ValueError("risk digest mismatch")
    recs = engine.query_all(
        "SELECT * FROM satsa_run_recommendations WHERE organization_id=? AND run_id=? ORDER BY id",
        (organization_id, run_id),
    )
    if {row["finding_id"] for row in recs} != finding_ids:
        raise ValueError("recommendation finding relationship mismatch")
    if any(
        digest_document(_strict_json(row["recommendation_json"], dict))
        != row["content_digest"]
        for row in recs
    ):
        raise ValueError("recommendation digest mismatch")
    rec_refs = [
        {
            "id": row["id"],
            "digest": digest_document(
                {
                    "finding_id": row["finding_id"],
                    "action": row["action"],
                    "recommendation": _strict_json(row["recommendation_json"], dict),
                }
            ),
        }
        for row in recs
    ]
    version = run["submission_version_id"]
    records = engine.query_all(
        "SELECT r.*,s.submission_id,s.version_id AS source_version,s.artifact_id,s.file_digest,"
        "s.format,s.locator,s.original_record_digest FROM satsa_version_records r"
        " JOIN satsa_source_records s ON s.id=r.source_record_id"
        " WHERE r.organization_id=? AND r.version_id=? ORDER BY r.record_id",
        (organization_id, version),
    )
    artifacts = engine.query_all(
        "SELECT * FROM satsa_artifacts WHERE organization_id=? AND submission_version_id=? ORDER BY id",
        (organization_id, version),
    )
    artifact_ids = {row["id"] for row in artifacts}
    snapshot = digest_document(
        {
            "organization_id": organization_id,
            "version_id": version,
            "artifact_digests": {
                row["category"]: row["sha3_256_digest"] for row in artifacts
            },
            "records": sorted(
                digest_document(_strict_json(row["payload_json"], dict))
                for row in records
            ),
        }
    )
    version_row = engine.query_one(
        "SELECT snapshot_digest FROM satsa_submission_versions WHERE organization_id=? AND id=?",
        (organization_id, version),
    )
    if snapshot != run["snapshot_digest"] or snapshot != version_row["snapshot_digest"]:
        raise ValueError("submission snapshot mismatch")
    record_refs = []
    source_ids = set()
    artifact_by_id = {row["id"]: row for row in artifacts}
    for row in records:
        if (
            row["submission_id"] != run["submission_id"]
            or row["source_version"] != version
            or row["artifact_id"] not in artifact_ids
        ):
            raise ValueError("source provenance relationship mismatch")
        source_ids.add(row["source_record_id"])
        artifact = artifact_by_id[row["artifact_id"]]
        payload = _strict_json(row["payload_json"], dict)
        if (
            row["file_digest"] != artifact["sha3_256_digest"]
            or row["format"] != artifact["format"]
        ):
            raise ValueError("source artifact provenance mismatch")
        if (
            payload.get("id") != row["record_id"]
            or payload.get("entity_id", run["entity_id"]) != run["entity_id"]
            or payload.get("assessment_id", run["assessment_id"])
            != run["assessment_id"]
        ):
            raise ValueError("canonical record ownership mismatch")
        record_refs.append(
            {
                "id": row["record_id"],
                "digest": digest_document(
                    {
                        "category": row["category"],
                        "payload": payload,
                        "source": {
                            key: row[key]
                            for key in (
                                "source_record_id",
                                "artifact_id",
                                "file_digest",
                                "format",
                                "locator",
                                "original_record_digest",
                            )
                        },
                    }
                ),
            }
        )
    for finding in findings:
        for ref in _strict_json(finding["evidence_refs_json"], list):
            if (
                isinstance(ref, str)
                and ref.startswith("srcrec_")
                and ref not in source_ids
            ):
                raise ValueError("finding evidence reference missing from version")
    artifact_refs = [
        {
            "id": row["id"],
            "digest": digest_document(
                {
                    key: row[key]
                    for key in (
                        "storage_key",
                        "content_type",
                        "size_bytes",
                        "sha3_256_digest",
                        "category",
                        "format",
                    )
                }
            ),
        }
        for row in artifacts
    ]

    def commitment(refs):
        return {"count": len(refs), "digest": digest_document(refs)}

    document = {
        "schema_version": 1,
        "subject_type": "supervisory_finalization",
        "organization_id": organization_id,
        "run": {
            key: run[key]
            for key in (
                "id",
                "entity_id",
                "assessment_id",
                "submission_id",
                "submission_version_id",
                "snapshot_digest",
                "code_version",
                "analytics_version",
                "model_version",
            )
        },
        "decision": decision_doc,
        "findings": commitment(finding_refs),
        "observations": commitment(obs_refs),
        "risk": digest_document(risk_doc),
        "recommendations": commitment(rec_refs),
        "canonical_records": commitment(record_refs),
        "artifacts": commitment(artifact_refs),
    }
    review_context = decision.get("review_context_digest")
    if review_context is not None and review_context != digest_document(document):
        raise ValueError("reviewed context changed before finalization")
    document["review_context_digest"] = review_context
    return document

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
from typing import Optional

from qsmlops.crypto.hashing import digest_document
from satsa.domain.evidence import Finding, SourceRecord
from satsa.domain.runs import AnalysisRun


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


def _parse_json_confidence(value) -> Optional[dict]:
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

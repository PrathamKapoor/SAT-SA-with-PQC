"""Phase 27 — deterministic trust digest tests.

The trust layer signs the content digest of every persisted
AnalysisRun and Finding. Verification re-derives the digest from
the live row and compares. These tests prove that the canonical
reconstruction path used by verification is deterministic and
matches the insert-time path for the common case.

The previous design had two paths independently build the
content-digest dict. They drifted in two ways:

1. The ``_j`` storage helper used ``json.dumps`` with
   ``ensure_ascii=True`` (the default), while ``canonical_json``
   used ``ensure_ascii=False`` — a Unicode character (e.g. an
   em-dash in a rationale) would be escaped as ``\\uXXXX`` in
   storage but kept as raw UTF-8 in the digest, breaking
   round-trip verification.

2. The verification path manually built the canonical dict from
   row columns, with subtle ordering / key-set differences
   versus the actual insert-time shape.

The fix: ``_j`` now uses the same encoder parameters as
``canonical_json``, and the verification path (``live_finding_digest``)
is the single source of truth for the digest shape — the
insert-time path round-trips through the same canonical
reconstruction before computing the digest.
"""
from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

import pytest

from qsmlops.crypto.hashing import canonical_json, digest_document
from satsa.analysis.canonical import (
    canonical_finding_dict_from_row,
    canonical_run_dict_from_row,
    live_finding_digest,
)
from satsa.analysis.repository import _j
from satsa.domain.evidence import ConfidenceVector, Finding
from satsa.domain.runs import AnalysisRun


def test_canonical_json_and_j_produce_byte_equal_strings():
    """_j (storage) and canonical_json (digest) must produce the
    same byte sequence for the same dict — otherwise non-ASCII
    characters (e.g. em-dash) cause round-trip failure."""
    d = {"rationale": "low \u2014 confirm", "n": 42, "f": 0.25, "lst": ["a", "b"]}
    s_j = _j(d)
    s_canonical = canonical_json(d).decode()
    assert s_j == s_canonical, (
        f"_j={s_j!r} != canonical={s_canonical!r}")


def test_canonical_finding_dict_keys_match_finding_to_dict():
    """The canonical reconstruction dict must contain exactly the
    same keys as ``Finding.to_dict()`` — no extra, no missing."""
    f = Finding(
        id="f1", observation_id="o1", rule_or_category="r", state="signal",
        rationale="x", scoped_subjects=["a"], statistic=1.0, effect=0.5,
        threshold=1.0,
        confidence=ConfidenceVector(analytical_support=0.5, evidence_completeness=0.5, peer_confidence=None),
        evidence_refs=["s1"], limitations="l",
    )
    d = canonical_finding_dict_from_row({
        "id": f.id, "observation_id": f.observation_id,
        "rule_or_category": f.rule_or_category, "state": f.state,
        "rationale": f.rationale,
        "scoped_subjects_json": _j(f.scoped_subjects),
        "statistic": f.statistic, "effect": f.effect, "threshold": f.threshold,
        "limitations": f.limitations,
        "confidence_json": _j(f.confidence.to_dict()),
        "evidence_refs_json": _j(f.evidence_refs),
    })
    assert set(d.keys()) == set(f.to_dict().keys())


def test_live_finding_digest_is_deterministic():
    """Same row → same digest, every time."""
    f = Finding(
        id="f1", observation_id="o1", rule_or_category="r", state="signal",
        rationale="x", scoped_subjects=["a"], statistic=1.0, effect=0.5,
        threshold=1.0,
        confidence=ConfidenceVector(analytical_support=0.5, evidence_completeness=0.5, peer_confidence=None),
        evidence_refs=["s1"], limitations="l",
    )
    fake_row = {
        "id": f.id, "observation_id": f.observation_id,
        "rule_or_category": f.rule_or_category, "state": f.state,
        "rationale": f.rationale,
        "scoped_subjects_json": _j(f.scoped_subjects),
        "statistic": f.statistic, "effect": f.effect, "threshold": f.threshold,
        "limitations": f.limitations,
        "confidence_json": _j(f.confidence.to_dict()),
        "evidence_refs_json": _j(f.evidence_refs),
    }
    d1 = live_finding_digest(fake_row)
    d2 = live_finding_digest(fake_row)
    d3 = live_finding_digest(dict(fake_row))  # copy of row
    assert d1 == d2 == d3


def test_canonical_run_dict_keys_match_run_to_dict():
    r = AnalysisRun(
        id="r1", entity_id="e1", assessment_id="a1",
        snapshot_digest="s", code_version="c", analytics_version="a",
        status="completed", started_at=1.0, finished_at=2.0,
    )
    d = canonical_run_dict_from_row({
        "id": r.id, "entity_id": r.entity_id, "assessment_id": r.assessment_id,
        "snapshot_digest": r.snapshot_digest, "code_version": r.code_version,
        "analytics_version": r.analytics_version, "model_version": r.model_version,
        "status": r.status, "started_at": r.started_at, "finished_at": r.finished_at,
        "error": r.error, "observation_ids_json": _j(r.observation_ids or [], "[]"),
    })
    assert set(d.keys()) == set(r.to_dict().keys())


def test_persistence_roundtrip_matches_canonical():
    """Insert a Finding via the real SQLite engine, then read the
    row back and verify the canonical reconstruction produces a
    byte-identical canonical JSON. This is the single most
    important property for trust verification: the row, as stored,
    reconstructs to the exact same canonical dict that was digested
    at insert time."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.domain.evidence import Observation
    from satsa.analysis.repository import FindingStore, ObservationStore, RunStore
    from satsa.analysis.canonical import live_finding_digest

    td = Path(tempfile.mkdtemp(prefix="phase27_roundtrip_"))
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        run = AnalysisRun(id="r1", entity_id="e1", assessment_id="a1",
                          snapshot_digest="s", code_version="c", analytics_version="a",
                          status="completed")
        RunStore(eng).insert(run, created_at=time.time())
        obs = Observation(id="o1", run_id="r1", worker_name="w",
                          detector_version="1", entity_id="e1", assessment_id="a1",
                          scope={}, created_at=time.time())
        ObservationStore(eng).insert(obs, created_at=time.time())
        f = Finding(
            id="f1", observation_id="o1", rule_or_category="r", state="signal",
            rationale="low \u2014 confirm", scoped_subjects=["a", "b"],
            statistic=1.0, effect=0.667, threshold=1.5,
            confidence=ConfidenceVector(analytical_support=0.667, evidence_completeness=0.25, peer_confidence=None),
            evidence_refs=["s1", "s2"], limitations="a limitation",
        )
        FindingStore(eng).insert(f, created_at=time.time())
        r = dict(eng.query_one("SELECT * FROM satsa_findings WHERE id=?", ("f1",)))
        # The stored content_digest should equal the live digest
        # computed from the row.
        live = live_finding_digest(r)
        assert r["content_digest"] == live, (
            f"stored={r['content_digest']} live={live}"
        )
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)

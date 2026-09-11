"""Stress test: insert N findings with various rationales and verify
the round-trip works for all of them. This isolates whether the
1/25 demo mismatch is due to a specific character or a structural
issue."""
from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.domain.evidence import ConfidenceVector, Finding, Observation
from satsa.domain.runs import AnalysisRun
from satsa.analysis.repository import FindingStore, ObservationStore, RunStore, _d
from satsa.analysis.canonical import live_finding_digest


def test_roundtrip_works_for_various_rationales():
    """Insert findings with various Unicode content and verify the
    round-trip digest matches the stored content_digest."""
    td = Path(tempfile.mkdtemp(prefix="phase27_stress_"))
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

        rationales = [
            "plain text",
            "with em-dash \u2014 confirm",
            "with en-dash \u2013 confirm",
            "with apostrophe \u2019s",
            "with quotes \u201chello\u201d",
            "with chinese \u4e2d\u6587",
            "with emoji \U0001f4ca",
            "with control chars \x00\x01",
            "with newline\non second line",
            "with tab\there",
            "with very long text " + "x" * 1000,
            "with mixed \u2014 \u2013 \u2018 \u201c",
            "with null in string\x00after",
            "with backslash \\ and quote \"",
        ]
        for i, rat in enumerate(rationales):
            f = Finding(
                id=f"f{i}", observation_id="o1", rule_or_category="r",
                state="signal", rationale=rat,
                scoped_subjects=["a", "b"], statistic=1.0, effect=0.5,
                threshold=1.0,
                confidence=ConfidenceVector(analytical_support=0.5, evidence_completeness=0.5, peer_confidence=None),
                evidence_refs=["s1", "s2"], limitations="l",
            )
            FindingStore(eng).insert(f, created_at=time.time())
            r = dict(eng.query_one("SELECT * FROM satsa_findings WHERE id=?", (f"f{i}",)))
            live = live_finding_digest(r)
            if r["content_digest"] != live:
                print(f"MISMATCH for rationale {i}: {rat!r}")
                print(f"  stored: {r['content_digest'][:32]}")
                print(f"  live:   {live[:32]}")
                # Debug: what was the insert-time digest?
                # We can't recover it, but we can re-derive
                digest_now = _d(f)
                print(f"  via _d(f) now: {digest_now[:32]}")
                # And what does the canonical do with the row?
                from satsa.analysis.canonical import canonical_finding_dict_from_row
                from qsmlops.crypto.hashing import digest_document
                d = canonical_finding_dict_from_row(r)
                print(f"  via canonical-from-row: {digest_document(d)[:32]}")
                # And with a fake_row built from the row's columns?
                fake = {
                    "id": r["id"], "observation_id": r["observation_id"],
                    "rule_or_category": r["rule_or_category"], "state": r["state"],
                    "rationale": r["rationale"],
                    "scoped_subjects_json": r["scoped_subjects_json"],
                    "statistic": r["statistic"], "effect": r["effect"],
                    "threshold": r["threshold"],
                    "limitations": r["limitations"],
                    "confidence_json": r["confidence_json"],
                    "evidence_refs_json": r["evidence_refs_json"],
                }
                print(f"  via canonical-from-fake: {digest_document(canonical_finding_dict_from_row(fake))[:32]}")
            assert r["content_digest"] == live, (
                f"Round-trip mismatch for rationale {i}: {rat!r}"
            )
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)

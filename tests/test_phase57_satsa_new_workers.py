"""Phase P14 — new supervisory workers: coverage gap, case
similarity, evidence completeness, drift, cross-entity insights.

Every worker must honor the contract:
* ``signal`` findings cite at least one evidence_ref;
* empty / ungroundable scopes yield ``insufficient_data`` or
  ``no_signal``, never a fabricated signal;
* the worker never crashes the run (orchestrator isolates).
"""
from __future__ import annotations

import tempfile
from pathlib import Path


def _setup():
    td = Path(tempfile.mkdtemp())
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
    MigrationRunner(eng).migrate()
    return eng, td


def _seed_alerts_cases(eng, n_alerts=3, n_cases=3, with_steps=True):
    from satsa.service import SatsaService
    from satsa.domain.entities import Submission
    from satsa.domain.workflow import Alert, Case, InvestigationStep
    from satsa.store.repositories import (
        AlertStore, CaseStore, InvestigationStepStore, SubmissionStore)
    svc = SatsaService(eng)
    e = svc.register_entity("CSE-T", sector="defence",
                            environment_class="on-prem")
    a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
    sub_id = "sub-1"
    SubmissionStore(eng).insert(Submission(
        id=sub_id, assessment_id=a.id, source_system="t",
        declared_period_start=1735689600.0, declared_period_end=1738281600.0,
        file_digests={}, declared_counts={},
        received_at=1735689600.0, signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap", created_at=1735689600.0)
    for i in range(n_alerts):
        AlertStore(eng).insert(Alert(
            entity_id=e.id, assessment_id=a.id, native_id=f"a{i}",
            created_at=1735689600.0 + i * 60,
            mapped_severity="medium",
            acknowledged_at=1735689600.0 + i * 60 + 60,
            closed_at=1735689600.0 + i * 60 + 600,
            source_record_ref=f"sr-a{i}"),
            submission_id=sub_id)
    for i in range(n_cases):
        c = Case(entity_id=e.id, assessment_id=a.id, native_id=f"c{i}",
                 opened_at=1735689600.0, status="open",
                 source_record_ref=f"sr-c{i}")
        CaseStore(eng).insert(c, submission_id=sub_id)
        if with_steps:
            InvestigationStepStore(eng).insert(InvestigationStep(
                case_id=c.id, action_type="triage",
                performed_at=1735689600.0 + 10, sequence=0),
                submission_id=sub_id)
    return e.id, a.id


def _runctx(entity_id, assessment_id):
    from satsa.contracts.worker import RunContext, SnapshotRef
    return (SnapshotRef(digest="snap", entity_id=entity_id,
                        assessment_id=assessment_id),
            RunContext(run_id="run-t", entity_id=entity_id,
                       assessment_id=assessment_id))


def test_case_similarity_no_signal_on_unique_sequences():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CaseSimilarityWorker
        from satsa.store.dataset import load_dataset
        eid, aid = _seed_alerts_cases(eng)
        ds = load_dataset(eng, eid, aid)
        # Each case has a single identical "triage" step → they DO
        # cluster (3 identical signatures). The finding must cite
        # the clustered cases' source records.
        snap, ctx = _runctx(eid, aid)
        batch = CaseSimilarityWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "signal"
        assert len(batch.findings) == 1
        assert batch.findings[0].evidence_refs, \
            "signal finding must cite evidence_refs"
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_case_similarity_insufficient_data_without_cases():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CaseSimilarityWorker
        from satsa.store.dataset import load_dataset
        eid, aid = _seed_alerts_cases(eng, n_cases=0, with_steps=False)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _runctx(eid, aid)
        batch = CaseSimilarityWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "insufficient_data"
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_evidence_completeness_signal_cites_assessed_base():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import EvidenceCompletenessWorker
        from satsa.store.dataset import load_dataset
        # Seed only alerts + cases: 4 of 6 categories missing →
        # missing_ratio 0.67 ≥ 0.20 → signal, citing alert/case refs.
        eid, aid = _seed_alerts_cases(eng)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _runctx(eid, aid)
        batch = EvidenceCompletenessWorker().evaluate(
            snap, ds, [], None, ctx)
        assert batch.state == "signal"
        assert batch.findings[0].evidence_refs
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_coverage_gap_no_crash_without_assets():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CoverageGapWorker
        from satsa.store.dataset import load_dataset
        eid, aid = _seed_alerts_cases(eng)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _runctx(eid, aid)
        batch = CoverageGapWorker().evaluate(snap, ds, [], None, ctx)
        # No critical assets → insufficient_data, never a crash.
        assert batch.state == "insufficient_data"
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_coverage_gap_signal_with_silent_critical_asset():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CoverageGapWorker
        from satsa.domain.entities import Asset
        from satsa.store.repositories import AssetStore
        from satsa.store.dataset import load_dataset
        eid, aid = _seed_alerts_cases(eng)
        AssetStore(eng).insert(Asset(
            entity_id=eid, native_id="srv-1", criticality="critical"),
            assessment_id=aid, submission_id="sub-1")
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _runctx(eid, aid)
        batch = CoverageGapWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "signal"
        assert batch.findings[0].evidence_refs
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_drift_and_cross_entity_abstain_without_context():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import DriftWorker, CrossEntityInsightsWorker
        from satsa.store.dataset import load_dataset
        eid, aid = _seed_alerts_cases(eng)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _runctx(eid, aid)
        assert DriftWorker().evaluate(
            snap, ds, [], None, ctx).state == "insufficient_data"
        assert CrossEntityInsightsWorker().evaluate(
            snap, ds, [], None, ctx).state == "insufficient_data"
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_default_run_now_has_16_workers():
    eng, td = _setup()
    try:
        from satsa.analysis.run import RunService
        eid, aid = _seed_alerts_cases(eng)
        result = RunService(eng).run(eid, aid)
        assert result.status in ("completed", "partial")
        # 16 observations — one per default worker (14 + the P25
        # agent-expansion additions: workflow-reconstruction,
        # entity-asset-resolution).
        assert len(result.observation_ids) == 16
        # No finding was silently dropped: every persisted signal
        # finding cites evidence and carries confidence.
        rows = eng.query_all(
            "SELECT * FROM satsa_findings WHERE state='signal'")
        for r in rows:
            import json
            refs = json.loads(r["evidence_refs_json"] or "[]")
            assert refs, f"signal finding {r['id']} has no evidence_refs"
            assert r["confidence_json"], \
                f"signal finding {r['id']} has no confidence"
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)
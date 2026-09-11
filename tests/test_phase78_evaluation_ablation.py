"""Phase P26 addendum (checklist item 2) — ablation study: disable
exactly one default analytical worker at a time on the same ingested
scope and measure which finding families actually disappear.
"""
from __future__ import annotations

import pytest

from evaluation.ablation.runner import run_ablation_study
from satsa.analysis.run import _default_workers, DEFAULT_FAST_CLOSURE_POLICY
from satsa.domain.entities import Submission
from satsa.domain.workflow import Alert
from satsa.store.repositories import AlertStore, SubmissionStore

BASE = 1735689600.0


@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


@pytest.fixture()
def service(engine):
    from satsa.service import SatsaService
    return SatsaService(engine)


def _open_scope(service, name):
    entity = service.register_entity(name, sector="defence",
                                       environment_class="on-prem")
    a = service.open_assessment(entity.id, BASE, BASE + 30 * 86400)
    return entity, a


def _ingest_fast_closure_alert(service, engine, entity, assessment):
    import time
    sub_id = f"sub-{entity.id}"
    SubmissionStore(engine).insert(
        Submission(id=sub_id, assessment_id=assessment.id, source_system="unit",
                   declared_period_start=BASE, declared_period_end=BASE + 30 * 86400,
                   file_digests={"x": "d"}, declared_counts={"alerts": 1},
                   received_at=time.time(), signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest=f"snap-{entity.id}", created_at=time.time())
    a = Alert(entity_id=entity.id, assessment_id=assessment.id,
              native_id="A1", created_at=BASE, mapped_severity="critical",
              acknowledged_at=BASE + 30, closed_at=BASE + 60,
              source_record_ref="sr-1")
    AlertStore(engine).insert(a, submission_id=sub_id)


def test_ablation_study_covers_every_default_worker(service, engine):
    entity, a = _open_scope(service, "CSE-ABL")
    _ingest_fast_closure_alert(service, engine, entity, a)
    report = run_ablation_study(engine, entity.id, a.id)
    expected_names = {w.name for w in _default_workers(DEFAULT_FAST_CLOSURE_POLICY)}
    reported_names = {r["worker_name"] for r in report["workers"]}
    assert reported_names == expected_names


def test_ablation_study_full_families_include_fast_closure(service, engine):
    entity, a = _open_scope(service, "CSE-ABL2")
    _ingest_fast_closure_alert(service, engine, entity, a)
    report = run_ablation_study(engine, entity.id, a.id)
    assert "execution_gap.fast_closure" in report["full_families"]


def test_removing_fast_closure_worker_loses_its_family(service, engine):
    entity, a = _open_scope(service, "CSE-ABL3")
    _ingest_fast_closure_alert(service, engine, entity, a)
    report = run_ablation_study(engine, entity.id, a.id)
    fast_closure_result = next(
        r for r in report["workers"] if r["worker_name"] == "fast-closure")
    assert "execution_gap.fast_closure" in fast_closure_result["lost_families"]
    assert fast_closure_result["unique_contribution"] is True
    assert "execution_gap.fast_closure" not in fast_closure_result["ablated_families"]


def test_removing_an_unrelated_worker_does_not_lose_fast_closure(service, engine):
    """Removing DriftWorker (which has nothing to compare against —
    no previous-period data exists for this scope) must not affect
    the fast-closure family emitted by a different worker."""
    entity, a = _open_scope(service, "CSE-ABL4")
    _ingest_fast_closure_alert(service, engine, entity, a)
    report = run_ablation_study(engine, entity.id, a.id)
    drift_result = next(
        r for r in report["workers"] if r["worker_name"] == "drift")
    assert "execution_gap.fast_closure" not in drift_result["lost_families"]
    assert "execution_gap.fast_closure" in drift_result["ablated_families"]


def test_ablation_result_to_dict_shape(service, engine):
    entity, a = _open_scope(service, "CSE-ABL5")
    _ingest_fast_closure_alert(service, engine, entity, a)
    report = run_ablation_study(engine, entity.id, a.id)
    for r in report["workers"]:
        assert set(r) == {
            "worker_name", "full_families", "ablated_families",
            "lost_families", "unique_contribution",
        }

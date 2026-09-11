"""Phase P25 (agent expansion) — Workflow Reconstruction Agent (N4).

Reconstructs the ordered event timeline per case from timestamps
already present in every submission and flags three independent
temporal-sequence violations no other worker checks for: escalation
after closure, disposition before any investigation, and declared-
sequence-vs-chronology mismatch.
"""
from __future__ import annotations

import pytest

from satsa.analysis.workers.workflow_reconstruction import (
    WorkflowReconstructionWorker,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.workflow import Case, Disposition, Escalation, InvestigationStep
from satsa.store.dataset import CanonicalDataset

BASE = 1735689600.0


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a")


def _case(*, id, opened=BASE, status="open", closed_at=None,
         source_record_ref="sr-c") -> Case:
    return Case(id=id, entity_id="e", assessment_id="a", native_id=f"native-{id}",
               opened_at=opened, status=status, closed_at=closed_at,
               source_record_ref=source_record_ref)


def _step(*, case_id, performed_at, sequence, id=None) -> InvestigationStep:
    return InvestigationStep(
        id=id or f"step-{case_id}-{sequence}", case_id=case_id,
        action_type="triage", performed_at=performed_at, sequence=sequence)


def _eval(worker, ds):
    return worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())


def _ds(*, cases=None, steps=None, escalations=None, dispositions=None) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=[], cases=cases or [], steps=steps or [],
        escalations=escalations or [], dispositions=dispositions or [], assets=[],
        submitted_categories=frozenset(
            ("alerts", "cases", "investigation_steps", "escalations",
             "dispositions", "assets")))


def test_escalation_after_closure_fires():
    c = _case(id="C1", status="closed", closed_at=BASE + 1000)
    e = Escalation(id="E1", entity_id="e", assessment_id="a",
                   occurred_at=BASE + 2000, case_id="C1")
    ds = _ds(cases=[c], escalations=[e])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "workflow_reconstruction.escalation_after_closure")
    assert f.state == "signal"
    assert f.scoped_subjects == ["E1"]


def test_escalation_before_closure_does_not_fire():
    c = _case(id="C1", status="closed", closed_at=BASE + 2000)
    e = Escalation(id="E1", entity_id="e", assessment_id="a",
                   occurred_at=BASE + 1000, case_id="C1")
    ds = _ds(cases=[c], escalations=[e])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(f.rule_or_category == "workflow_reconstruction.escalation_after_closure"
                   for f in batch.findings)


def test_escalation_on_open_case_never_fires():
    """An open case has no closed_at — the check must not fabricate
    a violation from a None comparison."""
    c = _case(id="C1", status="open")
    e = Escalation(id="E1", entity_id="e", assessment_id="a",
                   occurred_at=BASE + 5000, case_id="C1")
    ds = _ds(cases=[c], escalations=[e])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(f.rule_or_category == "workflow_reconstruction.escalation_after_closure"
                   for f in batch.findings)


def test_disposition_before_investigation_fires():
    c = _case(id="C1")
    step = _step(case_id="C1", performed_at=BASE + 2000, sequence=1)
    d = Disposition(id="D1", entity_id="e", assessment_id="a",
                    occurred_at=BASE + 1000, case_id="C1")
    ds = _ds(cases=[c], steps=[step], dispositions=[d])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "workflow_reconstruction.disposition_before_investigation")
    assert f.scoped_subjects == ["D1"]


def test_disposition_after_investigation_does_not_fire():
    c = _case(id="C1")
    step = _step(case_id="C1", performed_at=BASE + 1000, sequence=1)
    d = Disposition(id="D1", entity_id="e", assessment_id="a",
                    occurred_at=BASE + 2000, case_id="C1")
    ds = _ds(cases=[c], steps=[step], dispositions=[d])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(
        f.rule_or_category == "workflow_reconstruction.disposition_before_investigation"
        for f in batch.findings)


def test_disposition_with_no_investigation_steps_is_not_this_workers_concern():
    """Zero investigation steps at all is negative_space's job
    (missing_investigation) — this worker only compares relative
    ordering when steps actually exist."""
    c = _case(id="C1")
    d = Disposition(id="D1", entity_id="e", assessment_id="a",
                    occurred_at=BASE + 1000, case_id="C1")
    ds = _ds(cases=[c], dispositions=[d])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(
        f.rule_or_category == "workflow_reconstruction.disposition_before_investigation"
        for f in batch.findings)


def test_sequence_chronology_mismatch_fires():
    """Step declared sequence=1 happens chronologically AFTER the
    step declared sequence=2 — a real mismatch."""
    c = _case(id="C1")
    s1 = _step(case_id="C1", performed_at=BASE + 5000, sequence=1)
    s2 = _step(case_id="C1", performed_at=BASE + 1000, sequence=2)
    ds = _ds(cases=[c], steps=[s1, s2])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "workflow_reconstruction.sequence_chronology_mismatch")
    assert f.scoped_subjects == ["C1"]


def test_sequence_matches_chronology_does_not_fire():
    c = _case(id="C1")
    s1 = _step(case_id="C1", performed_at=BASE + 1000, sequence=1)
    s2 = _step(case_id="C1", performed_at=BASE + 2000, sequence=2)
    ds = _ds(cases=[c], steps=[s1, s2])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(
        f.rule_or_category == "workflow_reconstruction.sequence_chronology_mismatch"
        for f in batch.findings)


def test_single_step_case_cannot_mismatch():
    c = _case(id="C1")
    s1 = _step(case_id="C1", performed_at=BASE + 1000, sequence=1)
    ds = _ds(cases=[c], steps=[s1])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert not any(
        f.rule_or_category == "workflow_reconstruction.sequence_chronology_mismatch"
        for f in batch.findings)


def test_clean_case_produces_no_findings():
    c = _case(id="C1", status="closed", closed_at=BASE + 5000)
    s1 = _step(case_id="C1", performed_at=BASE + 1000, sequence=1)
    s2 = _step(case_id="C1", performed_at=BASE + 2000, sequence=2)
    e = Escalation(id="E1", entity_id="e", assessment_id="a",
                   occurred_at=BASE + 1500, case_id="C1")
    d = Disposition(id="D1", entity_id="e", assessment_id="a",
                    occurred_at=BASE + 3000, case_id="C1")
    ds = _ds(cases=[c], steps=[s1, s2], escalations=[e], dispositions=[d])
    batch = _eval(WorkflowReconstructionWorker(), ds)
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_worker_is_registered_in_the_26_agent_roster():
    from satsa.supervisor import list_agents
    ids = {a.agent_id for a in list_agents()}
    assert "satsa.workflow_reconstruction" in ids


def test_worker_runs_in_the_default_run_pipeline(tmp_path):
    """End-to-end: the worker is actually wired into RunService's
    default set, not just registered as a spec."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.domain.entities import Submission
    from satsa.domain.workflow import Alert
    from satsa.store.repositories import AlertStore, SubmissionStore

    eng = SQLiteDatabaseEngine(tmp_path / "x.db"); eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    e = svc.register_entity("CSE-WF", sector="defence")
    a = svc.open_assessment(e.id, BASE, BASE + 2592000)
    SubmissionStore(eng).insert(Submission(
        id="sub-1", assessment_id=a.id, source_system="t",
        declared_period_start=BASE, declared_period_end=BASE + 2592000,
        file_digests={}, declared_counts={}, received_at=BASE,
        signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap", created_at=BASE)
    AlertStore(eng).insert(Alert(
        entity_id=e.id, assessment_id=a.id, native_id="a1",
        created_at=BASE, mapped_severity="medium",
        acknowledged_at=BASE + 60, closed_at=BASE + 600,
        source_record_ref="sr-1"), submission_id="sub-1")
    result = svc.run_analysis(e.id, a.id)
    rows = eng.query_all(
        "SELECT DISTINCT worker_name FROM satsa_observations WHERE run_id=?",
        (result.run_id,))
    worker_names = {r["worker_name"] for r in rows}
    assert "workflow-reconstruction" in worker_names

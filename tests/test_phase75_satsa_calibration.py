"""Phase P26 — N17 calibration workflow: propose -> test against
labeled data -> supervisor approval -> versioned deployment.

Extends the Validation Agent (satsa.analysis.validate) with a real
governed process for changing a worker's detection thresholds. Every
step is tested against a concrete, realistic scenario: an alert closed
in 200s. Under the default FastClosureThresholds (critical_max_seconds
= 600), that alert qualifies as a fast-closure finding; an expert has
labeled that specific family a false positive for this entity (the
200s closure was a legitimate benign auto-closure, not an execution
gap). A tightened candidate threshold (critical_max_seconds=100) no
longer flags it — the calibration proposal is a genuine, measurable
improvement (fewer false positives against real labels), not a
fabricated one.
"""
from __future__ import annotations

import pytest

from satsa.analysis.calibration import (
    APPROVED,
    DEPLOYED,
    PROPOSED,
    REJECTED,
    TESTED,
    CalibrationLedger,
    CalibrationProposal,
    decide_calibration_proposal,
    deploy_calibration_proposal,
    propose_calibration,
    run_calibration_test,
)
from satsa.analysis.validate import ExpertLabel
from satsa.analysis.workers.fast_closure import (
    FastClosureThresholds,
    FastClosureWorker,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.workflow import Alert
from satsa.store.dataset import CanonicalDataset

BASE = 1735689600.0
LAYER = "execution_gap.fast_closure"


def _dataset() -> CanonicalDataset:
    alert = Alert(
        entity_id="e", assessment_id="a", native_id="A1", created_at=BASE,
        mapped_severity="critical", acknowledged_at=BASE + 30,
        closed_at=BASE + 200, source_record_ref="sr-1",
    )
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=[alert], cases=[], steps=[], escalations=[], dispositions=[],
        assets=[],
        submitted_categories=frozenset(
            ("alerts", "cases", "investigation_steps", "escalations",
             "dispositions", "assets")))


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a")


def _labels_calling_it_a_false_positive():
    return [ExpertLabel(
        layer=LAYER, is_signal=False, finding_category=LAYER,
        reviewer="expert1",
        rationale="200s closure was a legitimate benign auto-closure",
    )]


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------

def test_propose_requires_rationale():
    with pytest.raises(ValueError):
        propose_calibration(
            proposal_id="p1", worker_name="fast-closure", layer=LAYER,
            proposed_thresholds={"critical_max_seconds": 100.0},
            rationale="   ", proposer="alice")


def test_propose_requires_at_least_one_threshold():
    with pytest.raises(ValueError):
        propose_calibration(
            proposal_id="p1", worker_name="fast-closure", layer=LAYER,
            proposed_thresholds={}, rationale="tighten it", proposer="alice")


def test_propose_starts_in_proposed_state():
    p = propose_calibration(
        proposal_id="p1", worker_name="fast-closure", layer=LAYER,
        proposed_thresholds={"critical_max_seconds": 100.0},
        rationale="tighten it", proposer="alice")
    assert p.status == PROPOSED
    assert p.baseline_metric is None
    assert p.proposed_metric is None


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

def _proposed():
    return propose_calibration(
        proposal_id="p1", worker_name="fast-closure", layer=LAYER,
        proposed_thresholds={"critical_max_seconds": 100.0},
        rationale="200s closures are being flagged as false positives",
        proposer="alice")


def test_run_calibration_test_scores_against_real_labels():
    p = _proposed()
    ds = _dataset()
    tested = run_calibration_test(
        p,
        baseline_worker=FastClosureWorker(),
        candidate_worker=FastClosureWorker(FastClosureThresholds(critical_max_seconds=100.0)),
        snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
        run_context=_ctx(), expert_labels=_labels_calling_it_a_false_positive())
    assert tested.status == TESTED
    # Baseline (loose threshold) still flags the alert -> the expert's
    # negative label makes that a false positive.
    assert tested.baseline_metric["false_positives"] == 1
    assert tested.baseline_metric["true_negatives"] == 0
    # Candidate (tightened threshold) no longer flags it -> true negative.
    assert tested.proposed_metric["false_positives"] == 0
    assert tested.proposed_metric["true_negatives"] == 1


def test_run_calibration_test_does_not_mutate_input():
    p = _proposed()
    ds = _dataset()
    run_calibration_test(
        p, baseline_worker=FastClosureWorker(),
        candidate_worker=FastClosureWorker(FastClosureThresholds(critical_max_seconds=100.0)),
        snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
        run_context=_ctx(), expert_labels=_labels_calling_it_a_false_positive())
    assert p.status == PROPOSED  # original untouched


def test_run_calibration_test_rejects_non_proposed_input():
    p = _proposed()
    ds = _dataset()
    tested = run_calibration_test(
        p, baseline_worker=FastClosureWorker(),
        candidate_worker=FastClosureWorker(FastClosureThresholds(critical_max_seconds=100.0)),
        snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
        run_context=_ctx(), expert_labels=_labels_calling_it_a_false_positive())
    with pytest.raises(ValueError):
        run_calibration_test(
            tested, baseline_worker=FastClosureWorker(),
            candidate_worker=FastClosureWorker(),
            snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
            run_context=_ctx(), expert_labels=[])


def _tested():
    p = _proposed()
    ds = _dataset()
    return run_calibration_test(
        p, baseline_worker=FastClosureWorker(),
        candidate_worker=FastClosureWorker(FastClosureThresholds(critical_max_seconds=100.0)),
        snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
        run_context=_ctx(), expert_labels=_labels_calling_it_a_false_positive())


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------

def test_decide_requires_tested_state():
    p = _proposed()  # still 'proposed', not 'tested'
    with pytest.raises(ValueError):
        decide_calibration_proposal(
            p, decided_by="supervisor-bob", approve=True, rationale="ok")


def test_decide_requires_rationale():
    tested = _tested()
    with pytest.raises(ValueError):
        decide_calibration_proposal(
            tested, decided_by="supervisor-bob", approve=True, rationale=" ")


def test_decide_approve_records_decision():
    tested = _tested()
    decided = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True,
        rationale="candidate removes the false positive without losing recall")
    assert decided.status == APPROVED
    assert decided.decided_by == "supervisor-bob"
    assert decided.decided_at is not None
    assert "false positive" in decided.decision_rationale


def test_decide_reject_records_decision():
    tested = _tested()
    decided = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=False,
        rationale="too aggressive, would miss real fast closures")
    assert decided.status == REJECTED


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------

def test_deploy_requires_approved_state():
    tested = _tested()
    with pytest.raises(ValueError):
        deploy_calibration_proposal(tested, version="v2")


def test_deploy_rejects_rejected_proposal():
    tested = _tested()
    rejected = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=False, rationale="no")
    with pytest.raises(ValueError):
        deploy_calibration_proposal(rejected, version="v2")


def test_deploy_requires_version_label():
    tested = _tested()
    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True, rationale="ok")
    with pytest.raises(ValueError):
        deploy_calibration_proposal(approved, version="  ")


def test_deploy_marks_proposal_deployed():
    tested = _tested()
    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True, rationale="ok")
    deployed = deploy_calibration_proposal(approved, version="fast-closure-v2")
    assert deployed.status == DEPLOYED
    assert deployed.deployed_version == "fast-closure-v2"


# ---------------------------------------------------------------------------
# CalibrationLedger
# ---------------------------------------------------------------------------

def test_ledger_records_full_history(tmp_path):
    ledger = CalibrationLedger(tmp_path / "calibration.jsonl")
    p = _proposed()
    ledger.append(p)
    tested = _tested()
    ledger.append(tested)
    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True, rationale="ok")
    ledger.append(approved)
    deployed = deploy_calibration_proposal(approved, version="fast-closure-v2")
    ledger.append(deployed)

    history = ledger.history("p1")
    assert [r["status"] for r in history] == [PROPOSED, TESTED, APPROVED, DEPLOYED]


def test_ledger_latest_deployed_returns_none_when_nothing_deployed(tmp_path):
    ledger = CalibrationLedger(tmp_path / "calibration.jsonl")
    ledger.append(_proposed())
    assert ledger.latest_deployed("fast-closure") is None


def test_ledger_latest_deployed_returns_proposed_thresholds(tmp_path):
    ledger = CalibrationLedger(tmp_path / "calibration.jsonl")
    tested = _tested()
    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True, rationale="ok")
    deployed = deploy_calibration_proposal(approved, version="fast-closure-v2")
    ledger.append(deployed)

    latest = ledger.latest_deployed("fast-closure")
    assert latest is not None
    assert latest["deployed_version"] == "fast-closure-v2"
    assert latest["proposed_thresholds"] == {"critical_max_seconds": 100.0}


def test_ledger_latest_deployed_scoped_by_worker_name(tmp_path):
    ledger = CalibrationLedger(tmp_path / "calibration.jsonl")
    tested = _tested()
    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True, rationale="ok")
    deployed = deploy_calibration_proposal(approved, version="v2")
    ledger.append(deployed)
    assert ledger.latest_deployed("some-other-worker") is None


def test_ledger_is_append_only_not_rewritten(tmp_path):
    """Appending never edits a previously-written line."""
    path = tmp_path / "calibration.jsonl"
    ledger = CalibrationLedger(path)
    ledger.append(_proposed())
    first_write = path.read_text(encoding="utf-8")
    ledger.append(_tested())
    second_write = path.read_text(encoding="utf-8")
    assert second_write.startswith(first_write)


# ---------------------------------------------------------------------------
# CalibrationProposal serialization
# ---------------------------------------------------------------------------

def test_proposal_to_dict_from_dict_round_trip():
    p = _proposed()
    d = p.to_dict()
    restored = CalibrationProposal.from_dict(d)
    assert restored == p


# ---------------------------------------------------------------------------
# full happy-path workflow
# ---------------------------------------------------------------------------

def test_full_workflow_propose_test_approve_deploy():
    p = propose_calibration(
        proposal_id="wf1", worker_name="fast-closure", layer=LAYER,
        proposed_thresholds={"critical_max_seconds": 100.0},
        rationale="false positives on legitimate fast closures",
        proposer="alice")
    assert p.status == PROPOSED

    ds = _dataset()
    tested = run_calibration_test(
        p, baseline_worker=FastClosureWorker(),
        candidate_worker=FastClosureWorker(FastClosureThresholds(critical_max_seconds=100.0)),
        snapshot=SnapshotRef("d", "e", "a"), dataset=ds, baselines=[],
        run_context=_ctx(), expert_labels=_labels_calling_it_a_false_positive())
    assert tested.status == TESTED
    assert tested.proposed_metric["false_positives"] < tested.baseline_metric["false_positives"]

    approved = decide_calibration_proposal(
        tested, decided_by="supervisor-bob", approve=True,
        rationale="measurable reduction in false positives")
    assert approved.status == APPROVED

    deployed = deploy_calibration_proposal(approved, version="fast-closure-v2")
    assert deployed.status == DEPLOYED
    assert deployed.deployed_version == "fast-closure-v2"

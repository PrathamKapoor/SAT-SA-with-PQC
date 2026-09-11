"""Phase 2 — SAT-SA domain foundation tests (Part H/I).

Each domain record's validate() is tested against both a valid instance and
the specific edge cases docs/phase1/data-architecture.md called out by name
(e.g. "optional acknowledgment/closure is null, not zero duration") — this
phase does not implement ingestion or persistence for these records, but
their validation rules are real and tested, not placeholders.
"""
from __future__ import annotations

from satsa.domain.entities import Assessment, Asset, Entity, Submission
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
    Observation,
    ProvenanceRecord,
    ReviewDecision,
    SourceRecord,
)
from satsa.domain.runs import AnalysisRun
from satsa.domain.workflow import Alert, Case, Disposition, Escalation, InvestigationStep


# -------------------- Entity / Assessment / Submission / Asset --------------------

def test_entity_requires_display_name():
    assert Entity(display_name="Acme SOC").validate() == []
    assert Entity(display_name="").validate() != []


def test_entity_round_trips():
    e = Entity(display_name="Acme SOC", sector="finance", cohort_attributes={"scale": "large"})
    assert Entity.from_dict(e.to_dict()).to_dict() == e.to_dict()


def test_assessment_period_must_be_forward_and_half_open():
    entity = Entity(display_name="e")
    ok = Assessment(entity_id=entity.id, period_start=100, period_end=200)
    assert ok.validate() == []
    assert ok.contains(100) is True   # inclusive start
    assert ok.contains(200) is False  # exclusive end

    backwards = Assessment(entity_id=entity.id, period_start=200, period_end=100)
    assert backwards.validate() != []


def test_assessment_status_enum_enforced():
    a = Assessment(entity_id="e1", period_start=0, period_end=1, status="not-a-real-status")
    errors = a.validate()
    assert any("status" in e for e in errors)


def test_submission_requires_forward_declared_period_and_valid_signature_status():
    ok = Submission(
        assessment_id="a1", source_system="soc-tool", declared_period_start=0,
        declared_period_end=100,
    )
    assert ok.validate() == []

    bad = Submission(
        assessment_id="a1", source_system="soc-tool", declared_period_start=100,
        declared_period_end=0, signature_status="not-a-real-status",
    )
    errors = bad.validate()
    assert len(errors) == 2


def test_asset_requires_entity_and_native_id():
    assert Asset(entity_id="e1", native_id="srv-01").validate() == []
    assert Asset(entity_id="", native_id="").validate() != []


# -------------------- Alert / Case / InvestigationStep / Escalation / Disposition --------------------

def test_alert_acknowledged_none_is_not_zero_duration():
    """data-architecture.md: 'optional acknowledgment/closure is null, not
    zero duration' — an alert with no acknowledged_at must report
    time_to_acknowledge as None, never 0."""
    alert = Alert(entity_id="e1", assessment_id="a1", native_id="A-1", created_at=1000.0)
    assert alert.acknowledged_at is None
    assert alert.time_to_acknowledge is None
    assert alert.validate() == []


def test_alert_rejects_acknowledged_before_created():
    alert = Alert(
        entity_id="e1", assessment_id="a1", native_id="A-1", created_at=1000.0,
        acknowledged_at=999.0,
    )
    assert alert.validate() != []


def test_alert_rejects_closed_before_acknowledged():
    alert = Alert(
        entity_id="e1", assessment_id="a1", native_id="A-1", created_at=1000.0,
        acknowledged_at=1100.0, closed_at=1050.0,
    )
    assert alert.validate() != []


def test_case_closed_at_requires_status_closed():
    case = Case(
        entity_id="e1", assessment_id="a1", native_id="C-1", opened_at=1000.0,
        closed_at=1100.0, status="open",  # inconsistent on purpose
    )
    errors = case.validate()
    assert any("status" in e for e in errors)


def test_investigation_step_requires_action_and_non_negative_sequence():
    ok = InvestigationStep(case_id="c1", action_type="triage", performed_at=1.0, sequence=0)
    assert ok.validate() == []
    bad = InvestigationStep(case_id="c1", action_type="", performed_at=1.0, sequence=-1)
    assert len(bad.validate()) == 2


def test_escalation_requires_alert_or_case_reference():
    orphan = Escalation(entity_id="e1", assessment_id="a1", occurred_at=1.0)
    assert orphan.validate() != []
    linked = Escalation(entity_id="e1", assessment_id="a1", occurred_at=1.0, alert_id="A-1")
    assert linked.validate() == []


def test_disposition_requires_alert_or_case_reference():
    orphan = Disposition(entity_id="e1", assessment_id="a1", occurred_at=1.0)
    assert orphan.validate() != []
    linked = Disposition(entity_id="e1", assessment_id="a1", occurred_at=1.0, case_id="C-1")
    assert linked.validate() == []


# -------------------- SourceRecord / Observation / Finding / ReviewDecision / ProvenanceRecord --------------------

def test_source_record_requires_digests():
    ok = SourceRecord(
        submission_id="s1", file_digest="deadbeef", format="csv", locator="row:3",
        original_record_digest="cafebabe",
    )
    assert ok.validate() == []
    bad = SourceRecord(submission_id="", file_digest="", format="csv", locator="", original_record_digest="")
    assert len(bad.validate()) == 3


def test_finding_signal_state_requires_evidence_and_confidence():
    """SIH-EX-02: 'a score without explanation is insufficient' — enforced
    as a validation rule, not just documentation."""
    unsupported = Finding(observation_id="o1", rule_or_category="fast_closure", state="signal")
    errors = unsupported.validate()
    assert any("evidence_ref" in e for e in errors)
    assert any("confidence" in e for e in errors)

    supported = Finding(
        observation_id="o1", rule_or_category="fast_closure", state="signal",
        evidence_refs=["src1"],
        confidence=ConfidenceVector(analytical_support=0.9, evidence_completeness=0.8),
    )
    assert supported.validate() == []


def test_finding_no_signal_state_does_not_require_evidence():
    """An abstaining/clean finding is not held to the same evidentiary bar
    as a positive signal — only 'signal' findings must cite evidence."""
    clean = Finding(observation_id="o1", rule_or_category="fast_closure", state="no_signal")
    assert clean.validate() == []


def test_finding_rejects_unknown_state():
    bad = Finding(observation_id="o1", rule_or_category="x", state="totally_fine")
    assert bad.validate() != []


def test_confidence_vector_overall_is_weakest_component():
    cv = ConfidenceVector(analytical_support=0.9, evidence_completeness=0.4, peer_confidence=0.95)
    assert cv.overall == 0.4  # the weakest leg, not an average
    cv_no_peer = ConfidenceVector(analytical_support=0.9, evidence_completeness=0.4)
    assert cv_no_peer.overall == 0.4
    assert cv_no_peer.to_dict()["peer_confidence"] is None  # not_applicable, not zero


def test_review_decision_requires_known_action():
    bad = ReviewDecision(finding_id="f1", principal_identity_id="id1", action="auto_apply_forever")
    assert bad.validate() != []
    ok = ReviewDecision(finding_id="f1", principal_identity_id="id1", action="confirm")
    assert ok.validate() == []


def test_provenance_record_requires_all_five_fields():
    ok = ProvenanceRecord(
        subject_type="finding", subject_id="f1", predicate="derived_from",
        object_type="observation", object_id="o1",
    )
    assert ok.validate() == []
    bad = ProvenanceRecord(subject_type="", subject_id="", predicate="", object_type="", object_id="")
    assert len(bad.validate()) == 5


# -------------------- AnalysisRun --------------------

def test_analysis_run_terminal_status_requires_finished_at():
    incomplete = AnalysisRun(
        entity_id="e1", assessment_id="a1", snapshot_digest="deadbeef", status="completed",
    )
    assert incomplete.validate() != []

    complete = AnalysisRun(
        entity_id="e1", assessment_id="a1", snapshot_digest="deadbeef", status="completed",
        finished_at=1234.0,
    )
    assert complete.validate() == []


def test_analysis_run_failed_status_requires_error_message():
    bad = AnalysisRun(
        entity_id="e1", assessment_id="a1", snapshot_digest="deadbeef", status="failed",
        finished_at=1234.0,
    )
    assert any("error" in e for e in bad.validate())

    ok = AnalysisRun(
        entity_id="e1", assessment_id="a1", snapshot_digest="deadbeef", status="failed",
        finished_at=1234.0, error="worker crashed",
    )
    assert ok.validate() == []


def test_analysis_run_round_trips():
    run = AnalysisRun(
        entity_id="e1", assessment_id="a1", snapshot_digest="deadbeef",
        baseline_digests={"peer_cohort": "cafebabe"}, observation_ids=["o1", "o2"],
    )
    assert AnalysisRun.from_dict(run.to_dict()).to_dict() == run.to_dict()

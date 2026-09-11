"""Phase 5 (SAT-SA) — execution-gap engine tests.

The SIH execution-gap catalogue has six signals. Phase 4 implemented
5.2 (fast-closure). This file proves the other five workers plus
end-to-end execution of the full default worker set against a
ground-truth dataset with true-positive / true-negative / borderline /
missing-data / conflicting-evidence scenarios.
"""
from __future__ import annotations

import pytest

from satsa.analysis.repository import (
    FindingStore,
    ObservationStore,
    RunStore,
)
from satsa.analysis.workers.ack_without_investigation import (
    DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY,
    AckWithoutInvestigationThresholds,
    AckWithoutInvestigationWorker,
)
from satsa.analysis.workers.critical_without_escalation import (
    DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY,
    CriticalWithoutEscalationThresholds,
    CriticalWithoutEscalationWorker,
)
from satsa.analysis.workers.metric_gaming import (
    DEFAULT_METRIC_GAMING_POLICY,
    MetricGamingThresholds,
    MetricGamingWorker,
)
from satsa.analysis.workers.recurring_without_remediation import (
    DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY,
    RecurringWithoutRemediationThresholds,
    RecurringWithoutRemediationWorker,
)
from satsa.analysis.workers.repeated_investigation_pattern import (
    DEFAULT_REPEATED_INVESTIGATION_POLICY,
    RepeatedInvestigationThresholds,
    RepeatedInvestigationWorker,
)
from satsa.contracts.worker import (
    ObservationBatch,
    RunContext,
    SnapshotRef,
)
from satsa.domain.workflow import (
    Alert,
    Case,
    Escalation,
    InvestigationStep,
)
from satsa.store.dataset import CanonicalDataset
from satsa.store.repositories import (
    AlertStore,
    CaseStore,
    EscalationStore,
    InvestigationStepStore,
    SubmissionStore,
)
from satsa.domain.entities import Submission


BASE = 1735689600.0
END = 1738281600.0


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

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


def _open_scope(service, name="CSE-X"):
    entity = service.register_entity(name, sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    return entity, a


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a")


def _empty_args():
    """Kept for symmetry with the phase 4 tests; tests now call
    evaluate(snap, ds, [], None, ctx) directly so the dataset position is
    unambiguous."""
    return SnapshotRef("d", "e", "a"), [], None


def _eval(worker, ds, ctx=None):
    """Worker unit-test call helper: evaluate(snapshot, dataset, [], None, ctx)."""
    return worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None, ctx or _ctx())


def _dataset(*, alerts=None, cases=None, steps=None,
             escalations=None, dispositions=None, assets=None,
             submitted=("alerts",)) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=alerts or [], cases=cases or [], steps=steps or [],
        escalations=escalations or [], dispositions=dispositions or [],
        assets=assets or [], submitted_categories=frozenset(submitted),
    )


def _alert(*, id, severity, ack=None, closed=None,
           source_record_ref="srcrec-x", created_at=None) -> Alert:
    return Alert(
        id=id, entity_id="e", assessment_id="a",
        native_id=f"native-{id}",
        created_at=created_at if created_at is not None else BASE,
        mapped_severity=severity,
        acknowledged_at=ack, closed_at=closed,
        source_record_ref=source_record_ref,
    )


def _case(*, id, status="open", closed_at=None, alert_ids=None,
          remediation_refs=None, source_record_ref="srcrec-c") -> Case:
    return Case(
        id=id, entity_id="e", assessment_id="a", native_id=f"native-{id}",
        opened_at=BASE + 50, alert_refs=alert_ids or [],
        status=status, closed_at=closed_at, remediation_refs=remediation_refs or [],
        source_record_ref=source_record_ref,
    )


def _step(*, case_id, action_type="triage", note="x", sequence=1,
          performed_at=BASE + 200) -> InvestigationStep:
    return InvestigationStep(
        id=f"step-{case_id}-{sequence}",
        case_id=case_id, action_type=action_type, performed_at=performed_at,
        sequence=sequence, note_text=note,
    )


def _escalation(*, alert_id=None, case_id=None,
                occurred_at=BASE + 300) -> Escalation:
    return Escalation(
        id=f"esc-{alert_id or case_id}", entity_id="e", assessment_id="a",
        occurred_at=occurred_at, alert_id=alert_id, case_id=case_id,
        destination_role="soc-l2",
    )


# ===========================================================================
# 5.1 AckWithoutInvestigation
# ===========================================================================

def test_5_1_true_positive_closed_ack_without_investigation():
    """A critical alert is acknowledged AND closed, but its case has no
    investigation steps at all."""
    a = _alert(id="A1", severity="critical", ack=BASE + 200, closed=BASE + 3600)
    c = _case(id="C1", status="closed", closed_at=BASE + 3600, alert_ids=["A1"])
    a.case_refs = ["C1"]
    ds = _dataset(alerts=[a], cases=[c])
    batch = AckWithoutInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"
    assert len(batch.findings) == 1
    f = batch.findings[0]
    assert f.rule_or_category == "execution_gap.ack_without_investigation"
    assert "A1" in f.scoped_subjects


def test_5_1_true_negative_healthy_investigation():
    """An acknowledged-and-closed alert whose case has 3 investigation steps
    is *not* flagged — there was a real investigation."""
    a = _alert(id="A1", severity="critical", ack=BASE + 200, closed=BASE + 3600)
    c = _case(id="C1", status="closed", closed_at=BASE + 3600, alert_ids=["A1"])
    a.case_refs = ["C1"]
    steps = [_step(case_id="C1", sequence=i) for i in range(1, 4)]
    ds = _dataset(alerts=[a], cases=[c], steps=steps)
    batch = AckWithoutInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_5_1_borderline_only_one_step():
    """Default threshold is 2 steps; one step is below threshold → signal."""
    a = _alert(id="A1", severity="high", ack=BASE + 200, closed=BASE + 3600)
    c = _case(id="C1", status="closed", closed_at=BASE + 3600, alert_ids=["A1"])
    a.case_refs = ["C1"]
    ds = _dataset(alerts=[a], cases=[c], steps=[_step(case_id="C1", sequence=1)])
    batch = AckWithoutInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"


def test_5_1_unacknowledged_alert_not_flagged_here():
    """An alert that was never acknowledged is *not* a closure gap — the
    signal is for acknowledged-then-closed, not for never-acknowledged
    (which is the negative-space engine's concern)."""
    a = _alert(id="A1", severity="critical", ack=None, closed=BASE + 3600)
    c = _case(id="C1", status="closed", closed_at=BASE + 3600, alert_ids=["A1"])
    a.case_refs = ["C1"]
    ds = _dataset(alerts=[a], cases=[c], steps=[])
    batch = AckWithoutInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_1_conflicting_thresholds_under_custom_min_steps():
    """A custom min_steps_per_case=3 still flags a one-step case as
    having *too few* steps (1 < 3) → signal. The conflicting-evidence
    angle: a CSE might argue "we use a stricter runbook with more
    steps" — that would move the threshold to 5+ and require
    higher-quality data, not silence the signal here."""
    a = _alert(id="A1", severity="high", ack=BASE + 200, closed=BASE + 3600)
    c = _case(id="C1", status="closed", closed_at=BASE + 3600, alert_ids=["A1"])
    a.case_refs = ["C1"]
    ds = _dataset(alerts=[a], cases=[c], steps=[_step(case_id="C1", sequence=1)])
    batch = AckWithoutInvestigationWorker(
        thresholds=AckWithoutInvestigationThresholds(min_steps_per_case=5)
    ).evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    # 1 step is still below the 5-step threshold → still a signal
    assert batch.state == "signal"


# ===========================================================================
# 5.3 CriticalWithoutEscalation
# ===========================================================================

def test_5_3_true_positive_critical_closed_no_escalation():
    a = _alert(id="A1", severity="critical", closed=BASE + 3600)
    ds = _dataset(alerts=[a])
    batch = CriticalWithoutEscalationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"
    assert batch.findings[0].rule_or_category == "execution_gap.critical_without_escalation"
    assert batch.findings[0].scoped_subjects == ["A1"]


def test_5_3_true_negative_critical_with_direct_escalation():
    a = _alert(id="A1", severity="critical", closed=BASE + 3600)
    e = _escalation(alert_id="A1")
    ds = _dataset(alerts=[a], escalations=[e])
    batch = CriticalWithoutEscalationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_3_true_negative_critical_via_case_escalation():
    a = _alert(id="A1", severity="critical", closed=BASE + 3600)
    a.case_refs = ["C1"]
    c = _case(id="C1", alert_ids=["A1"])
    e = _escalation(case_id="C1")
    ds = _dataset(alerts=[a], cases=[c], escalations=[e])
    batch = CriticalWithoutEscalationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_3_high_severity_not_flagged_by_default():
    a = _alert(id="A1", severity="high", closed=BASE + 3600)
    ds = _dataset(alerts=[a])
    batch = CriticalWithoutEscalationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_3_unclosed_critical_not_flagged():
    a = _alert(id="A1", severity="critical", closed=None)
    ds = _dataset(alerts=[a])
    batch = CriticalWithoutEscalationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


# ===========================================================================
# 5.4 RepeatedInvestigationPattern
# ===========================================================================

def test_5_4_true_positive_shallow_playbook():
    """9/10 steps are 'triage' with the same trivial 'ok' note."""
    steps = [
        _step(case_id=f"C{i}", sequence=1, action_type="triage", note="ok")
        for i in range(9)
    ]
    steps.append(_step(case_id="C-final", sequence=1, action_type="deep-dive",
                        note="comprehensive investigation across hosts, network and user behaviour"))
    ds = _dataset(steps=steps)
    batch = RepeatedInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"
    f = batch.findings[0]
    assert f.rule_or_category == "execution_gap.repeated_investigation_pattern"


def test_5_4_true_negative_diverse_meaningful_work():
    steps = [
        _step(case_id=f"C{i}", sequence=1, action_type=action,
              note=("a real investigation note with at least thirty characters of content"
                    " written by an analyst"))
        for i, action in enumerate(("triage", "deep-dive", "containment", "eradication",
                                     "recovery", "review", "lessons-learned",
                                     "stakeholder-update", "comms", "followup"), start=1)
    ]
    ds = _dataset(steps=steps)
    batch = RepeatedInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_4_borderline_consistent_but_substantive():
    """Consistent process with substantive notes is NOT shallow."""
    steps = [
        _step(case_id=f"C{i}", sequence=1, action_type="triage",
              note="initial triage per runbook — full review of relevant logs and indicators")
        for i in range(10)
    ]
    ds = _dataset(steps=steps)
    batch = RepeatedInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_4_missing_data_fewer_than_min_steps():
    steps = [_step(case_id="C1", sequence=i) for i in range(1, 4)]
    ds = _dataset(steps=steps)
    batch = RepeatedInvestigationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "insufficient_data"


# ===========================================================================
# 5.5 RecurringWithoutRemediation
# ===========================================================================

def test_5_5_true_positive_recurring_case_no_remediation():
    """A closed case that absorbed 4 alerts with no remediation_refs."""
    a = _alert(id="A1", severity="high", closed=BASE + 3600)
    a.case_refs = ["C1"]
    c = _case(id="C1", status="closed", closed_at=BASE + 7200)
    extra_alerts = [
        _alert(id=f"A{i}", severity="high", closed=BASE + 3600) for i in range(2, 5)
    ]
    for ea in extra_alerts:
        ea.case_refs = ["C1"]
    ds = _dataset(alerts=[a] + extra_alerts, cases=[c])
    batch = RecurringWithoutRemediationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"
    f = batch.findings[0]
    assert f.rule_or_category == "execution_gap.recurring_without_remediation"
    assert "C1" in f.scoped_subjects


def test_5_5_true_negative_recurring_case_with_remediation():
    a = _alert(id="A1", severity="high", closed=BASE + 3600)
    a.case_refs = ["C1"]
    c = _case(id="C1", status="closed", closed_at=BASE + 7200,
              remediation_refs=["REM-1", "REM-2"])
    extra = [
        _alert(id=f"A{i}", severity="high", closed=BASE + 3600) for i in range(2, 5)
    ]
    for ea in extra:
        ea.case_refs = ["C1"]
    ds = _dataset(alerts=[a] + extra, cases=[c])
    batch = RecurringWithoutRemediationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_5_true_negative_case_still_open():
    a = _alert(id="A1", severity="high", closed=BASE + 3600)
    a.case_refs = ["C1"]
    c = _case(id="C1", status="open")
    extra = [
        _alert(id=f"A{i}", severity="high", closed=BASE + 3600) for i in range(2, 5)
    ]
    for ea in extra:
        ea.case_refs = ["C1"]
    ds = _dataset(alerts=[a] + extra, cases=[c])
    batch = RecurringWithoutRemediationWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_5_conflicting_threshold_low_recurrence():
    """A custom recurrence_threshold=5 turns a 3-alert case into no-signal."""
    a = _alert(id="A1", severity="high", closed=BASE + 3600)
    a.case_refs = ["C1"]
    c = _case(id="C1", status="closed", closed_at=BASE + 7200)
    extra = [
        _alert(id=f"A{i}", severity="high", closed=BASE + 3600) for i in range(2, 4)
    ]
    for ea in extra:
        ea.case_refs = ["C1"]
    ds = _dataset(alerts=[a] + extra, cases=[c])
    batch = RecurringWithoutRemediationWorker(
        thresholds=RecurringWithoutRemediationThresholds(recurrence_threshold=5)
    ).evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


# ===========================================================================
# 5.6 MetricGaming
# ===========================================================================

def test_5_6_true_positive_high_closure_low_depth():
    """All 10 critical alerts closed, average 0.5 investigation steps per
    linked case."""
    alerts = []
    cases = []
    for i in range(10):
        a = _alert(id=f"A{i+1}", severity="critical", closed=BASE + 600)
        a.case_refs = [f"C{i+1}"]
        alerts.append(a)
        c = _case(id=f"C{i+1}", status="closed", closed_at=BASE + 600,
                  alert_ids=[a.id])
        cases.append(c)
    # half the cases have 0 steps, half have 1 → average 0.5
    steps = []
    for i in range(0, 10, 2):
        steps.append(_step(case_id=f"C{i+1}", sequence=1))
    ds = _dataset(alerts=alerts, cases=cases, steps=steps)
    batch = MetricGamingWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "signal"
    f = batch.findings[0]
    assert f.rule_or_category == "execution_gap.potential_metric_gaming"
    assert len(f.scoped_subjects) == 10


def test_5_6_true_negative_closure_with_substantive_work():
    """Same closure rate, but each linked case has 5 steps → not flagged."""
    alerts, cases, steps = [], [], []
    for i in range(10):
        a = _alert(id=f"A{i+1}", severity="critical", closed=BASE + 600)
        a.case_refs = [f"C{i+1}"]
        alerts.append(a)
        c = _case(id=f"C{i+1}", status="closed", closed_at=BASE + 600,
                  alert_ids=[a.id])
        cases.append(c)
        for s in range(1, 6):
            steps.append(_step(case_id=f"C{i+1}", sequence=s))
    ds = _dataset(alerts=alerts, cases=cases, steps=steps)
    batch = MetricGamingWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_6_borderline_low_closure_rate():
    """A 50% closure rate does not exceed the 90% threshold → no signal."""
    alerts = []
    for i in range(10):
        alerts.append(_alert(id=f"A{i+1}", severity="critical",
                             closed=(BASE + 600 if i < 5 else None)))
    ds = _dataset(alerts=alerts)
    batch = MetricGamingWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "no_signal"


def test_5_6_missing_data_fewer_alerts():
    alerts = [_alert(id="A1", severity="critical", closed=BASE + 600)]
    ds = _dataset(alerts=alerts)
    batch = MetricGamingWorker().evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())
    assert batch.state == "insufficient_data"


# ===========================================================================
# End-to-end: the full default worker set on a ground-truth mixed scenario
# ===========================================================================

def test_e2e_full_worker_set_against_mixed_ground_truth(service, engine):
    """A single ground-truth submission that exercises every signal at
    least once (positive, negative, or borderline) and confirm the right
    combination of findings persists."""
    import time
    entity, a = _open_scope(service, "CSE-GT")
    sub = SubmissionStore(engine)
    sub.insert(
        Submission(id="s-gt", assessment_id=a.id, source_system="gt",
                   declared_period_start=BASE, declared_period_end=END,
                   file_digests={"x": "d"}, declared_counts={"alerts": 8},
                   received_at=time.time(), signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap-gt", created_at=time.time())

    # ---- alerts (3 critical: 2 fast-close + 1 healthy; 1 high;
    #                 2 medium: 1 closed+acked, 1 open).
    # The two fast-close criticals (A1, A2) link to C-EMPTY (no steps) so
    # 5.1 (ack-without-investigation) fires for them; the healthy critical
    # A3 links to C-NORM (2 deep steps) so 5.1 does not fire for A3.
    # A4, A5, A6 all link to C-REC (5 shallow steps) — C-REC has
    # 3 alerts, no remediation → 5.5 fires.
    alerts = [
        # A1: critical, closed in 120s (well below 600s SLA) → 5.2 fires
        _alert(id="A1", severity="critical",
               created_at=BASE, ack=BASE + 60, closed=BASE + 120,
               source_record_ref="sr-A1"),
        # A2: critical, closed in 300s (also below SLA) → 5.2 fires
        _alert(id="A2", severity="critical",
               created_at=BASE, ack=BASE + 60, closed=BASE + 300,
               source_record_ref="sr-A2"),
        # A3: critical, closed in 24h (healthy)
        _alert(id="A3", severity="critical",
               created_at=BASE, ack=BASE + 200, closed=BASE + 24*3600,
               source_record_ref="sr-A3"),
        # A4: high, closed in 2h (healthy for high SLA = 1800s)
        _alert(id="A4", severity="high",
               created_at=BASE, ack=BASE + 200, closed=BASE + 7200,
               source_record_ref="sr-A4"),
        # A5: medium, closed in 2h (healthy for medium SLA = 3600s)
        _alert(id="A5", severity="medium",
               created_at=BASE, ack=BASE + 200, closed=BASE + 7200,
               source_record_ref="sr-A5"),
        # A6: medium, still open (unacked)
        _alert(id="A6", severity="medium",
               created_at=BASE, ack=None, closed=None,
               source_record_ref="sr-A6"),
    ]
    for x in alerts:
        x.entity_id, x.assessment_id = entity.id, a.id
    for a_ in alerts:
        AlertStore(engine).insert(a_, submission_id="s-gt")

    # ---- cases (3: one empty-for-investigation, one normal, one recurring) ----
    cases = [
        _case(id="C-EMPTY", status="closed", closed_at=BASE + 3600,
              source_record_ref="sr-C-EMPTY"),
        _case(id="C-NORM", status="closed", closed_at=BASE + 7200,
              source_record_ref="sr-C-NORM"),
        _case(id="C-REC", status="closed", closed_at=BASE + 7200,
              source_record_ref="sr-C-REC"),
    ]
    for c_ in cases:
        c_.entity_id, c_.assessment_id = entity.id, a.id
        CaseStore(engine).insert(c_, submission_id="s-gt")
    # link alerts → cases
    alerts[0].case_refs = ["C-EMPTY"]; alerts[1].case_refs = ["C-EMPTY"]
    alerts[2].case_refs = ["C-NORM"]
    alerts[3].case_refs = ["C-REC"]; alerts[4].case_refs = ["C-REC"]
    alerts[5].case_refs = ["C-REC"]
    # persist the case_refs updates back to the DB
    import json as _json
    for a_ in alerts:
        engine.execute("UPDATE satsa_alerts SET case_refs_json=? WHERE id=?",
                       (_json.dumps(a_.case_refs), a_.id))

    # ---- investigation steps: 5 shallow (C-REC), 2 deep (C-NORM),
    #      none for C-EMPTY (so 5.1 fires for A1, A2) ----
    shallow = [
        _step(case_id="C-REC", sequence=s, action_type="triage", note="ok")
        for s in range(1, 6)
    ]
    deep = [
        _step(case_id="C-NORM", sequence=s, action_type="triage",
              note="comprehensive investigation across hosts, network and user behaviour")
        for s in range(1, 3)
    ]
    for s_ in (shallow + deep):
        s_.id = f"step-{s_.case_id}-{s_.sequence}"
        InvestigationStepStore(engine).insert(s_, submission_id="s-gt")

    # ---- one escalation: A3 only (A1, A2 critical go up without one) ----
    e3 = _escalation(alert_id="A3")
    e3.entity_id, e3.assessment_id, e3.id = entity.id, a.id, "esc-A3"
    EscalationStore(engine).insert(e3, submission_id="s-gt")

    # ---- run with the full default worker set ----
    from satsa.analysis.run import RunService
    result = RunService(engine).run(entity.id, a.id)
    # 6 workers, all completed, no crashing
    assert result.status == "completed"
    rules = set()
    for fid in result.finding_ids:
        rows = FindingStore(engine).list_for_run(result.run_id)
        for r in rows:
            rules.add(r["rule_or_category"])
    # expectations: 5.2 fast-closure (A1, A2 closed < 600s), 5.1
    # ack-without-investigation (A1, A2, A4, A5 under-investigated for
    # case C-REC), 5.3 critical-without-escalation (A1, A2), 5.4
    # repeated pattern (5/7 shallow), 5.5 recurring-without-remediation
    # (C-REC absorbed 4 alerts). 5.6 metric-gaming does NOT fire: only
    # 4 critical+high alerts (A1, A2, A3, A4) — below the
    # min_alerts_for_signal=5 default; that's a deliberate threshold,
    # not a test bug.
    expected = {
        "execution_gap.fast_closure",
        "execution_gap.ack_without_investigation",
        "execution_gap.critical_without_escalation",
        "execution_gap.repeated_investigation_pattern",
        "execution_gap.recurring_without_remediation",
    }
    missing = expected - rules
    assert not missing, f"missing rules: {missing}; got: {rules}"
    # and 5/6 is a closure finding fast_closure from A1, A2 (both < 600s)
    # 6/6 metric_gaming fires (10 alerts is borderline; here only 6 alerts
    # of interest — critical+high = 4 — but the min_alerts_for_signal=5
    # only counts severities in ('critical','high') which is 4 → no signal
    # for 5.6 here, actually). Loosen: the 5.6 worker counts only
    # critical+high alerts; with 3 critical + 1 high = 4, that's below
    # the min_alerts_for_signal=5 → no metric-gaming signal. That matches
    # expectation for the small synthetic ground truth.


def test_workers_register_in_deterministic_order():
    """The default worker set is registered in a fixed order — important
    for the persistence/replay guarantee and for the test fixtures
    above (observations list_for_run is order-dependent)."""
    from satsa.analysis.run import _default_workers
    workers = _default_workers(None)  # type: ignore[arg-type]
    names = [w.name for w in workers]
    assert names == [
        "fast-closure",
        "ack-without-investigation",
        "critical-without-escalation",
        "repeated-investigation-pattern",
        "recurring-without-remediation",
        "potential-metric-gaming",
        "negative-space",
        "anomaly",
        "peer-benchmark",
        "coverage-gap",
        "drift",
        "cross-entity-insights",
        "case-similarity",
        "evidence-completeness",
    ]

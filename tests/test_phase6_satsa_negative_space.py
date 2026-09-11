"""Phase 6 (SAT-SA) — negative-space engine tests.

The spec requires the negative-space engine to distinguish *absence
in reality* from *absence from submission*, and to never let zero
activity alone be an automatic finding. These tests prove the six
negative-space rules: missing_file (×6), missing_investigation,
missing_escalation, missing_disposition, missing_monitoring,
unexpectedly_low_activity — across true-positive, true-negative,
borderline, and missing-data scenarios.
"""
from __future__ import annotations

import pytest

from satsa.analysis.workers.negative_space import (
    DEFAULT_NEGATIVE_SPACE_POLICY,
    NegativeSpaceThresholds,
    NegativeSpaceWorker,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.entities import Asset
from satsa.domain.workflow import (
    Alert,
    Case,
    Disposition,
    Escalation,
    InvestigationStep,
)
from satsa.store.dataset import CanonicalDataset


BASE = 1735689600.0


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a")


def _alert(*, id, severity, ack=None, closed=None, case_refs=None,
           asset_refs=None, source_record_ref="sr-x") -> Alert:
    return Alert(
        id=id, entity_id="e", assessment_id="a",
        native_id=f"native-{id}", created_at=BASE,
        mapped_severity=severity, acknowledged_at=ack, closed_at=closed,
        case_refs=case_refs or [], asset_refs=asset_refs or [],
        source_record_ref=source_record_ref,
    )


def _case(*, id, status="open", closed_at=None, source_record_ref="sr-c") -> Case:
    return Case(
        id=id, entity_id="e", assessment_id="a", native_id=f"native-{id}",
        opened_at=BASE, status=status, closed_at=closed_at,
        source_record_ref=source_record_ref,
    )


def _step(*, case_id, action_type="triage", note="x", sequence=1) -> InvestigationStep:
    return InvestigationStep(
        id=f"step-{case_id}-{sequence}",
        case_id=case_id, action_type=action_type, performed_at=BASE,
        sequence=sequence, note_text=note,
    )


def _asset(*, id, criticality="high") -> Asset:
    return Asset(
        id=id, entity_id="e", native_id=f"native-{id}",
        criticality=criticality,
    )


def _eval(worker, ds):
    return worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx())


def _ds(*, alerts=None, cases=None, steps=None, escalations=None,
        dispositions=None, assets=None,
        submitted=("alerts", "cases", "investigation_steps",
                   "escalations", "dispositions", "assets")) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=alerts or [], cases=cases or [], steps=steps or [],
        escalations=escalations or [], dispositions=dispositions or [],
        assets=assets or [], submitted_categories=frozenset(submitted),
    )


# ---------------------------------------------------------------------------
# 1. Missing file: a category that was never submitted
# ---------------------------------------------------------------------------

def test_missing_file_finding_per_missing_category():
    """No assets.csv and no escalations.csv submitted → two missing-file
    findings, with evidence_completeness = 0.0 (the data simply isn't
    there)."""
    ds = _ds(submitted=("alerts", "cases", "investigation_steps",
                         "dispositions"))
    batch = _eval(NegativeSpaceWorker(), ds)
    rules = {f.rule_or_category for f in batch.findings}
    assert "negative_space.missing_file.assets" in rules
    assert "negative_space.missing_file.escalations" in rules
    # both have state=insufficient_data
    for f in batch.findings:
        if f.rule_or_category.startswith("negative_space.missing_file."):
            assert f.state == "insufficient_data"
            assert f.confidence.evidence_completeness == 0.0
            assert f.confidence.analytical_support == 1.0


def test_all_categories_submitted_emits_no_missing_file_findings():
    ds = _ds(submitted=("alerts", "cases", "investigation_steps",
                         "escalations", "dispositions", "assets"))
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category.startswith("negative_space.missing_file.")
                   for f in batch.findings)


# ---------------------------------------------------------------------------
# 2. Missing investigation
# ---------------------------------------------------------------------------

def test_missing_investigation_true_positive():
    a = _alert(id="A1", severity="critical", closed=BASE + 100,
               case_refs=["C1"])
    c = _case(id="C1", status="closed", closed_at=BASE + 100)
    ds = _ds(alerts=[a], cases=[c], steps=[])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "negative_space.missing_investigation")
    assert f.state == "signal"
    assert "C1" in f.scoped_subjects


def test_missing_investigation_true_negative():
    a = _alert(id="A1", severity="high", closed=BASE + 100, case_refs=["C1"])
    c = _case(id="C1", status="closed", closed_at=BASE + 100)
    ds = _ds(alerts=[a], cases=[c], steps=[_step(case_id="C1", sequence=1)])
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_investigation"
                   for f in batch.findings)


def test_missing_investigation_not_raised_when_steps_not_submitted():
    """The engine refuses to claim 'cases have no investigation' when
    the investigation_steps file itself was not submitted — that is
    a missing-file signal, not a missing-investigation signal."""
    a = _alert(id="A1", severity="critical", closed=BASE + 100, case_refs=["C1"])
    c = _case(id="C1", status="closed", closed_at=BASE + 100)
    ds = _ds(alerts=[a], cases=[c],
              submitted=("alerts", "cases"))  # no investigation_steps
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_investigation"
                   for f in batch.findings)
    # the missing_file finding is the right thing instead
    assert any(f.rule_or_category == "negative_space.missing_file.investigation_steps"
               for f in batch.findings)


# ---------------------------------------------------------------------------
# 3. Missing escalation
# ---------------------------------------------------------------------------

def test_missing_escalation_true_positive():
    a = _alert(id="A1", severity="critical", closed=BASE + 100)
    ds = _ds(alerts=[a])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "negative_space.missing_escalation")
    assert f.state == "signal"
    assert f.scoped_subjects == ["A1"]


def test_missing_escalation_via_linked_case():
    a = _alert(id="A1", severity="critical", closed=BASE + 100,
               case_refs=["C1"])
    c = _case(id="C1", status="closed", closed_at=BASE + 100)
    e = Escalation(id="esc-1", entity_id="e", assessment_id="a",
                    occurred_at=BASE + 50, case_id="C1")
    ds = _ds(alerts=[a], cases=[c], escalations=[e])
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_escalation"
                   for f in batch.findings)


def test_missing_escalation_does_not_fire_when_escalations_file_missing():
    """The engine refuses to claim 'critical alerts lack escalations'
    when the escalations file was not submitted — the absence is a
    data-completeness problem, not a conduct problem. The
    negative_space.missing_file.escalations finding is the right
    thing in this case."""
    a = _alert(id="A1", severity="critical", closed=BASE + 100)
    ds = _ds(alerts=[a],
              submitted=("alerts", "cases", "investigation_steps",
                          "dispositions", "assets"))  # no escalations
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_escalation"
                   for f in batch.findings)
    assert any(f.rule_or_category == "negative_space.missing_file.escalations"
               for f in batch.findings)


def test_high_severity_not_escalation_negative_space_signal():
    """Only critical alerts count for the missing-escalation signal."""
    a = _alert(id="A1", severity="high", closed=BASE + 100)
    ds = _ds(alerts=[a])
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_escalation"
                   for f in batch.findings)


# ---------------------------------------------------------------------------
# 4. Missing disposition
# ---------------------------------------------------------------------------

def test_missing_disposition_true_positive():
    a = _alert(id="A1", severity="high", closed=BASE + 100)
    ds = _ds(alerts=[a])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "negative_space.missing_disposition")
    assert f.state == "signal"


def test_missing_disposition_with_record_present():
    a = _alert(id="A1", severity="high", closed=BASE + 100)
    d = Disposition(id="disp-1", entity_id="e", assessment_id="a",
                     occurred_at=BASE + 200, alert_id="A1",
                     mapped_category="true_positive")
    ds = _ds(alerts=[a], dispositions=[d])
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_disposition"
                   for f in batch.findings)


def test_missing_disposition_skipped_when_dispositions_not_submitted():
    a = _alert(id="A1", severity="high", closed=BASE + 100)
    ds = _ds(alerts=[a],
              submitted=("alerts", "cases", "investigation_steps",
                          "escalations", "assets"))  # no dispositions
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_disposition"
                   for f in batch.findings)
    assert any(f.rule_or_category == "negative_space.missing_file.dispositions"
               for f in batch.findings)


# ---------------------------------------------------------------------------
# 5. Missing monitoring
# ---------------------------------------------------------------------------

def test_missing_monitoring_true_positive():
    a1 = _asset(id="asset-1", criticality="critical")
    a2 = _asset(id="asset-2", criticality="critical")
    a3 = _asset(id="asset-3", criticality="high")
    ds = _ds(assets=[a1, a2, a3])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "negative_space.missing_monitoring")
    assert f.state == "signal"
    assert set(f.scoped_subjects) == {"asset-1", "asset-2", "asset-3"}


def test_missing_monitoring_with_alerts_present():
    a1 = _asset(id="asset-1", criticality="critical")
    a2 = _asset(id="asset-2", criticality="critical")
    alert = _alert(id="A1", severity="critical", asset_refs=["asset-1"])
    ds = _ds(assets=[a1, a2], alerts=[alert])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next((f for f in batch.findings
              if f.rule_or_category == "negative_space.missing_monitoring"), None)
    if f is not None:
        # may or may not fire depending on threshold; if it does,
        # asset-1 must NOT be flagged (it has alerts)
        assert "asset-1" not in f.scoped_subjects


def test_missing_monitoring_skipped_when_inventory_not_submitted():
    a1 = _alert(id="A1", severity="critical")
    ds = _ds(alerts=[a1],
              submitted=("alerts", "cases", "investigation_steps",
                          "escalations", "dispositions"))  # no assets
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.missing_monitoring"
                   for f in batch.findings)
    assert any(f.rule_or_category == "negative_space.missing_file.assets"
               for f in batch.findings)


# ---------------------------------------------------------------------------
# 6. Unexpectedly low activity
# ---------------------------------------------------------------------------

def test_unexpectedly_low_activity_true_positive():
    """3 critical assets, only 1 alert in scope."""
    assets = [_asset(id=f"a-{i}", criticality="critical") for i in range(1, 4)]
    alert = _alert(id="A1", severity="high")
    ds = _ds(assets=assets, alerts=[alert])
    batch = _eval(NegativeSpaceWorker(), ds)
    f = next(f for f in batch.findings
             if f.rule_or_category == "negative_space.unexpectedly_low_activity")
    assert f.state == "signal"
    assert f.statistic == 1.0


def test_unexpectedly_low_activity_true_negative():
    assets = [_asset(id=f"a-{i}", criticality="critical") for i in range(1, 4)]
    alerts = [_alert(id=f"A{i}", severity="low") for i in range(1, 6)]
    ds = _ds(assets=assets, alerts=alerts)
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.unexpectedly_low_activity"
                   for f in batch.findings)


def test_unexpectedly_low_activity_below_min_critical_assets():
    """Only 1 critical asset is not enough to raise a 'low activity'
    finding — small inventories produce noise."""
    assets = [_asset(id="a-1", criticality="critical")]
    alert = _alert(id="A1", severity="low")
    ds = _ds(assets=assets, alerts=[alert])
    batch = _eval(NegativeSpaceWorker(), ds)
    assert not any(f.rule_or_category == "negative_space.unexpectedly_low_activity"
                   for f in batch.findings)


# ---------------------------------------------------------------------------
# Spec rule: zero activity alone must NOT be a finding
# ---------------------------------------------------------------------------

def test_zero_activity_alone_is_not_a_finding():
    """A scope with one alert, no cases, no assets, no dispositions is
    'small' — not 'negative'. No signal findings should fire (the
    missing-file findings will fire, but those are data-completeness,
    not CSE-conduct)."""
    a = _alert(id="A1", severity="low")
    ds = _ds(alerts=[a],
              submitted=("alerts",))  # only alerts submitted
    batch = _eval(NegativeSpaceWorker(), ds)
    # all findings should be data-completeness (state=insufficient_data),
    # not conduct signals
    for f in batch.findings:
        assert f.state == "insufficient_data", \
            f"unexpected conduct signal {f.rule_or_category} for a 1-alert scope"


# ---------------------------------------------------------------------------
# Confidence / data-completeness plumbing
# ---------------------------------------------------------------------------

def test_scope_records_data_completeness_per_category():
    """The ObservationBatch scope block must report a per-category
    data-completeness map, regardless of whether findings fired."""
    ds = _ds(submitted=("alerts", "cases"))
    batch = _eval(NegativeSpaceWorker(), ds)
    completeness = batch.scope["data_completeness"]
    assert completeness == {
        "alerts": True, "cases": True, "investigation_steps": False,
        "escalations": False, "dispositions": False, "assets": False,
    }


def test_custom_thresholds_lower_min_alert_volume():
    """A custom low threshold makes the 'low activity' finding fire on
    a smaller absolute alert count."""
    assets = [_asset(id="a-1", criticality="critical")]
    alerts = [_alert(id="A1", severity="low")]
    ds = _ds(assets=assets, alerts=alerts)
    batch = _eval(NegativeSpaceWorker(
        thresholds=NegativeSpaceThresholds(
            min_alert_volume_for_low_activity=2,
            min_critical_assets=1,
        )), ds)
    assert any(f.rule_or_category == "negative_space.unexpectedly_low_activity"
               for f in batch.findings)

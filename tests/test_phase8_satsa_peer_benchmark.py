"""Phase 8 (SAT-SA) — peer-benchmarking tests.

The peer-benchmark engine compares an entity's in-scope metrics
against a cohort baseline built from other entities in the same
``sector`` + ``environment_class``. Tests cover:

* the cohort selection (matching sector + environment_class, no
  blind cross-entity comparison),
* the per-metric peer aggregation (median / MAD / p25 / p75 / count),
* the per-metric deviation rule and the per-metric output shape,
* the "insufficient_data" behaviour when the peer cohort is too
  small (< min_peers),
* the end-to-end run with the default worker set (16 workers now),
* a sanity check that the spec-style output (entity observed value,
  peer median, deviation, signal) is present and computed from
  real numbers.
"""
from __future__ import annotations

import pytest

from satsa.analysis.repository import FindingStore
from satsa.analysis.workers.peer_benchmark import (
    DEFAULT_PEER_BENCHMARK_POLICY,
    METRIC_KEYS,
    PeerBaseline,
    PeerBenchmarkThresholds,
    PeerBenchmarkWorker,
    _aggregate_peer_metric,
    _assessment_metrics,
    _cohort_key,
    _percentile_local,
    attach_baseline,
    compute_peer_baseline,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.entities import Asset, Submission
from satsa.domain.workflow import (
    Alert,
    Case,
    Escalation,
    InvestigationStep,
)
from satsa.store.dataset import CanonicalDataset
from satsa.store.repositories import (
    AlertStore, AssetStore, CaseStore, EscalationStore,
    InvestigationStepStore, SubmissionStore,
)


BASE = 1735689600.0


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


def _open_scope(service, name, sector="defence", env="on-prem"):
    entity = service.register_entity(name, sector=sector,
                                       environment_class=env)
    a = service.open_assessment(entity.id, BASE, BASE + 30 * 86400)
    return entity, a


def _alert(*, id, severity, ack=None, closed=None, asset_refs=None,
           case_refs=None, source_record_ref="sr-x", created_at=BASE) -> Alert:
    return Alert(
        id=id, entity_id="e", assessment_id="a",
        native_id=f"native-{id}", created_at=created_at,
        mapped_severity=severity, acknowledged_at=ack, closed_at=closed,
        asset_refs=asset_refs or [], case_refs=case_refs or [],
        source_record_ref=source_record_ref,
    )


def _case(*, id, status="closed", opened_at=BASE, closed_at=None,
          source_record_ref="sr-c") -> Case:
    return Case(
        id=id, entity_id="e", assessment_id="a", native_id=f"native-{id}",
        opened_at=opened_at, status=status, closed_at=closed_at,
        source_record_ref=source_record_ref,
    )


def _step(*, case_id, sequence=1, action_type="triage", note="x") -> InvestigationStep:
    return InvestigationStep(
        id=f"step-{case_id}-{sequence}", case_id=case_id,
        action_type=action_type, performed_at=BASE, sequence=sequence,
        note_text=note,
    )


def _asset(*, id, criticality="high") -> Asset:
    return Asset(id=id, entity_id="e", native_id=f"native-{id}", criticality=criticality)


def _ingest_simple_scope(service, engine, *, entity, assessment, alerts, cases=None,
                          steps=None, escalations=None, assets=None, dispositions=None,
                          sub_id=None):
    """Helper: persist a small canonical dataset directly into the
    stores so the dataset loader can find it later."""
    import time
    sub_id = sub_id or f"sub-{entity.id}"
    sub = SubmissionStore(engine)
    sub.insert(
        Submission(id=sub_id, assessment_id=assessment.id, source_system="unit",
                   declared_period_start=BASE, declared_period_end=BASE + 30 * 86400,
                   file_digests={"x": "d"}, declared_counts={"alerts": len(alerts)},
                   received_at=time.time(), signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest=f"snap-{entity.id}", created_at=time.time())
    for a in alerts:
        a.entity_id, a.assessment_id = entity.id, assessment.id
        AlertStore(engine).insert(a, submission_id=sub_id)
    for c in (cases or []):
        c.entity_id, c.assessment_id = entity.id, assessment.id
        CaseStore(engine).insert(c, submission_id=sub_id)
    for s in (steps or []):
        InvestigationStepStore(engine).insert(s, submission_id=sub_id)
    for e in (escalations or []):
        e.entity_id, e.assessment_id = entity.id, assessment.id
        EscalationStore(engine).insert(e, submission_id=sub_id)
    for a in (assets or []):
        a.entity_id = entity.id
        AssetStore(engine).insert(a, assessment_id=assessment.id, submission_id=sub_id)


# ---------------------------------------------------------------------------
# 1. cohort selection
# ---------------------------------------------------------------------------

def test_cohort_key_from_entity():
    e = {"sector": "defence", "environment_class": "on-prem"}
    assert _cohort_key(e) == ("defence", "on-prem")


def test_peer_baseline_empty_when_no_peers(service, engine):
    e1, a1 = _open_scope(service, "Loner", sector="defence", env="on-prem")
    _ingest_simple_scope(service, engine, entity=e1, assessment=a1,
                          alerts=[_alert(id="A1", severity="low", closed=BASE + 60)])
    baseline = compute_peer_baseline(engine, e1.id)
    assert baseline.peer_count == 0
    assert baseline.metrics["critical_closure_median_seconds"]["count"] == 0


def test_peer_baseline_uses_cohort_match_not_blind(service, engine):
    """Two entities, different sector → no peer baseline; matching
    sector → peer baseline."""
    e1, a1 = _open_scope(service, "CSE-A", sector="defence", env="on-prem")
    e2, a2 = _open_scope(service, "CSE-B", sector="finance", env="on-prem")
    _ingest_simple_scope(service, engine, entity=e1, assessment=a1,
                          alerts=[_alert(id="A1", severity="low", closed=BASE + 60)])
    _ingest_simple_scope(service, engine, entity=e2, assessment=a2,
                          alerts=[_alert(id="B1", severity="low", closed=BASE + 60)])
    baseline = compute_peer_baseline(engine, e1.id, min_peers=1)
    assert baseline.peer_count == 0   # e2 is in a different sector

    e3, a3 = _open_scope(service, "CSE-C", sector="defence", env="on-prem")
    _ingest_simple_scope(service, engine, entity=e3, assessment=a3,
                          alerts=[_alert(id="C1", severity="low", closed=BASE + 60)])
    baseline = compute_peer_baseline(engine, e1.id, min_peers=1)
    assert baseline.peer_count == 1
    assert baseline.cohort_key == ("defence", "on-prem")


# ---------------------------------------------------------------------------
# 2. per-metric aggregation
# ---------------------------------------------------------------------------

def test_aggregate_peer_metric_handles_empty():
    r = _aggregate_peer_metric([])
    assert r == {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}


def test_aggregate_peer_metric_handles_single_value():
    r = _aggregate_peer_metric([42.0])
    assert r["count"] == 1
    assert r["median"] == 42.0
    assert r["mad"] == 0.0


def test_aggregate_peer_metric_basic():
    r = _aggregate_peer_metric([1, 2, 3, 4, 5])
    assert r["count"] == 5
    assert r["median"] == 3.0
    assert r["mad"] == 1.0
    assert r["p25"] == 2.0
    assert r["p75"] == 4.0


# ---------------------------------------------------------------------------
# 3. peer baseline assembled from real peer entities
# ---------------------------------------------------------------------------

def test_peer_baseline_aggregates_real_peer_metrics(service, engine):
    """Five entities in the same cohort. The baseline median closure
    time should equal the median across the four peer entities."""
    names = ["P1", "P2", "P3", "P4", "SUBJECT"]
    closures = [120, 240, 360, 480, 600]  # each entity's median closure
    for i, (name, t) in enumerate(zip(names, closures)):
        e, a = _open_scope(service, name, sector="defence", env="on-prem")
        _ingest_simple_scope(service, engine, entity=e, assessment=a,
                              alerts=[
                                  _alert(id=f"A{i}-1", severity="critical",
                                          closed=BASE + t),
                                  _alert(id=f"A{i}-2", severity="critical",
                                          closed=BASE + t),
                              ])
    subject_entity = service.get_entity(
        [n for n in service.list_entities() if n["display_name"] == "SUBJECT"][0]["id"])
    baseline = compute_peer_baseline(engine, subject_entity["id"], min_peers=2)
    assert baseline.peer_count == 4
    # peer median closure = median of [120, 240, 360, 480] = 300
    assert baseline.metrics["critical_closure_median_seconds"]["median"] == pytest.approx(300.0)
    assert baseline.metrics["critical_closure_median_seconds"]["count"] == 4


# ---------------------------------------------------------------------------
# 4. PeerBenchmarkWorker with a real attached baseline
# ---------------------------------------------------------------------------

def _build_dataset_for_subject(subject_closure_seconds):
    alerts = [
        _alert(id="A1", severity="critical", closed=BASE + subject_closure_seconds,
               source_record_ref="sr-A1"),
        _alert(id="A2", severity="critical", closed=BASE + subject_closure_seconds,
               source_record_ref="sr-A2"),
    ]
    return CanonicalDataset(
        entity_id="subject", assessment_id="a", snapshot_digest="d",
        alerts=alerts, cases=[], steps=[], escalations=[], dispositions=[],
        assets=[], submitted_categories=frozenset(("alerts",)),
    )


def test_peer_benchmark_signal_when_subject_far_below_peer():
    """Subject median closure = 30s; peer median = 300s; deviation
    well over 2 MADs → signal."""
    peer = PeerBaseline(
        entity_id="subject", cohort_key=("defence", "on-prem"),
        digest="x", peer_count=4,
        metrics={
            "critical_closure_median_seconds":
                {"median": 300.0, "mad": 50.0, "p25": 250.0, "p75": 350.0, "count": 4},
            **{k: {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}
               for k in METRIC_KEYS if k != "critical_closure_median_seconds"},
        },
    )
    worker = attach_baseline(PeerBenchmarkWorker(), peer)
    ds = _build_dataset_for_subject(30)
    batch = worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None,
                             RunContext(run_id="r", entity_id="e", assessment_id="a"))
    f = next(f for f in batch.findings
             if f.rule_or_category == "peer_benchmark.critical_closure_median_seconds.deviation")
    # observed 30, peer 300 → deviation -270 / mad 50 = -5.4 mads
    assert f.statistic == 30.0
    assert f.threshold == 300.0
    assert f.effect < 0
    assert f.effect < -2.0
    # the rationale should carry both numbers + the cohort label
    assert "30" in f.rationale and "300" in f.rationale
    assert "defence" in f.rationale


def test_peer_benchmark_no_signal_within_mad_k():
    """Subject median closure = 310s, peer median = 300s, peer MAD = 50s
    → deviation is 10s, well inside 2 MADs → no signal."""
    peer = PeerBaseline(
        entity_id="subject", cohort_key=("defence", "on-prem"),
        digest="x", peer_count=4,
        metrics={
            "critical_closure_median_seconds":
                {"median": 300.0, "mad": 50.0, "p25": 0.0, "p75": 0.0, "count": 4},
            **{k: {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}
               for k in METRIC_KEYS if k != "critical_closure_median_seconds"},
        },
    )
    worker = attach_baseline(PeerBenchmarkWorker(), peer)
    ds = _build_dataset_for_subject(310)
    batch = worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None,
                             RunContext(run_id="r", entity_id="e", assessment_id="a"))
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_peer_benchmark_insufficient_when_too_few_peers():
    peer = PeerBaseline(
        entity_id="subject", cohort_key=("d", "e"), digest="x",
        peer_count=2, metrics={k: {"median": 0.0, "mad": 0.0, "p25": 0.0,
                                    "p75": 0.0, "count": 0} for k in METRIC_KEYS},
    )
    worker = attach_baseline(
        PeerBenchmarkWorker(thresholds=PeerBenchmarkThresholds(min_peers=3)),
        peer)
    ds = _build_dataset_for_subject(30)
    batch = worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None,
                             RunContext(run_id="r", entity_id="e", assessment_id="a"))
    assert batch.state == "insufficient_data"


def test_peer_benchmark_emits_spec_style_finding():
    """The spec example is a CSE-017 4.2 min median closure vs 38.7
    min peer. This test produces a structurally identical finding."""
    peer = PeerBaseline(
        entity_id="x", cohort_key=("d", "e"), digest="x", peer_count=5,
        metrics={
            "critical_closure_median_seconds":
                {"median": 38.7 * 60, "mad": 5 * 60, "p25": 0.0, "p75": 0.0, "count": 5},
            **{k: {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}
               for k in METRIC_KEYS if k != "critical_closure_median_seconds"},
        },
    )
    worker = attach_baseline(PeerBenchmarkWorker(), peer)
    ds = _build_dataset_for_subject(4.2 * 60)
    batch = worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None,
                             RunContext(run_id="r", entity_id="e", assessment_id="a"))
    f = batch.findings[0]
    assert f.rule_or_category == "peer_benchmark.critical_closure_median_seconds.deviation"
    # observed 4.2 min, peer 38.7 min → deviation -89%
    assert f.statistic == pytest.approx(4.2 * 60)
    assert f.threshold == pytest.approx(38.7 * 60)
    # confidence.peer_confidence is now populated (Phase 8's contribution)
    assert f.confidence.peer_confidence is not None
    assert 0.0 < f.confidence.peer_confidence <= 1.0


# ---------------------------------------------------------------------------
# 5. end-to-end: full default worker set + peer baseline (real data)
# ---------------------------------------------------------------------------

def test_end_to_end_peer_benchmark_with_real_peers(service, engine):
    """Build 4 peers and 1 subject. Subject's closure time is far
    below the peer median → the default RunService worker set emits
    a peer_benchmark finding."""
    # peers: 300, 600, 900, 1200 second closures
    for i, t in enumerate([300, 600, 900, 1200]):
        e, a = _open_scope(service, f"PEER-{i+1}", sector="defence", env="on-prem")
        _ingest_simple_scope(service, engine, entity=e, assessment=a,
                              alerts=[
                                  _alert(id=f"P{i}-1", severity="critical", closed=BASE + t),
                                  _alert(id=f"P{i}-2", severity="critical", closed=BASE + t),
                              ])
    e_sub, a_sub = _open_scope(service, "SUBJECT", sector="defence", env="on-prem")
    # subject: very fast closure (30s) — strong peer-deviation signal
    _ingest_simple_scope(service, engine, entity=e_sub, assessment=a_sub,
                          alerts=[
                              _alert(id="S1", severity="critical", closed=BASE + 30,
                                      source_record_ref="sr-S1"),
                              _alert(id="S2", severity="critical", closed=BASE + 30,
                                      source_record_ref="sr-S2"),
                          ])
    result = service.run_analysis(e_sub.id, a_sub.id)
    assert result.status == "completed"
    # a peer_benchmark finding should be present
    findings = FindingStore(engine).list_for_run(result.run_id)
    rules = {f["rule_or_category"] for f in findings}
    assert any(r.startswith("peer_benchmark.") for r in rules), \
        f"no peer_benchmark finding in {rules}"
    # the spec-style output is present (numbers are real, not hard-coded)
    f = next(r for r in findings
             if r["rule_or_category"] == "peer_benchmark.critical_closure_median_seconds.deviation")
    assert f["statistic"] == 30.0
    assert f["threshold"] in (300.0, 600.0, 900.0, 1200.0,
                                450.0, 600.0, 750.0, 900.0)
    # the rationale contains both observed and peer numbers
    assert "30" in f["rationale"]

"""Phase 4 (SAT-SA) — analysis-run engine + first worker tests.

The first worker (``fast-closure``) is exercised in isolation against
hand-built ``CanonicalDataset``-s so every signal/no-signal/edge case
is a deterministic unit test, then the full ``RunService`` is
exercised end-to-end through ``SatsaService.run_analysis`` to prove
the persistence path and the run-status state machine.
"""
from __future__ import annotations

import pytest

from satsa.analysis.repository import (
    FindingStore,
    JobStore,
    ObservationStore,
    RunStore,
)
from satsa.analysis.run import RunService
from satsa.analysis.workers.fast_closure import (
    DEFAULT_FAST_CLOSURE_POLICY,
    FastClosureThresholds,
    FastClosureWorker,
)
from satsa.contracts.worker import (
    BaselineRef,
    EchoWorker,
    ObservationBatch,
    PolicyRef,
    RunContext,
    SnapshotRef,
)
from satsa.domain.workflow import Alert
from satsa.store.dataset import CanonicalDataset
from satsa.store.repositories import (
    AlertStore,
    SubmissionStore,
)


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


def _open_scope(service, name="CSE-001"):
    entity = service.register_entity(name, sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    return entity, a


def _alert(*, severity, close_seconds, source_record_ref="srcrec-x",
           id=None) -> Alert:
    created = 1000.0
    closed = created + close_seconds
    mapped = {"critical": "critical", "high": "high", "medium": "medium"}.get(severity, severity)
    return Alert(
        id=id or f"alert-{created}-{severity}-{close_seconds}",
        entity_id="entity-x", assessment_id="assessment-x",
        native_id=f"native-{created}-{severity}-{close_seconds}",
        created_at=created, mapped_severity=mapped,
        acknowledged_at=created + 10, closed_at=closed,
        source_record_ref=source_record_ref,
    )


def _dataset(alerts=None, asset_id="asset-1", scope_categories=None) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="entity-x", assessment_id="assessment-x",
        snapshot_digest="snap-x", alerts=alerts or [],
        cases=[], steps=[], escalations=[], dispositions=[],
        assets=[], submitted_categories=frozenset(scope_categories or ("alerts",)),
    )


def _ctx() -> RunContext:
    return RunContext(run_id="run-x", entity_id="entity-x", assessment_id="assessment-x")


def _empty_args():
    snap = SnapshotRef("snap-x", "entity-x", "assessment-x")
    return snap, [], None


# ---------------------------------------------------------------------------
# FastClosureWorker — unit tests
# ---------------------------------------------------------------------------

def test_normal_case_emits_no_signal():
    """Healthy CSE: critical alerts closed in well over the SLA → no signal."""
    worker = FastClosureWorker()
    alerts = [
        _alert(severity="critical", close_seconds=24 * 3600),  # 24h
        _alert(severity="high", close_seconds=12 * 3600),
        _alert(severity="medium", close_seconds=8 * 3600),
    ]
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_suspicious_case_emits_signal():
    """A critical alert closed in 60s is far below the 600s default SLA."""
    worker = FastClosureWorker()
    alerts = [
        _alert(severity="critical", close_seconds=60),
        _alert(severity="critical", close_seconds=24 * 3600),  # contrast
    ]
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert batch.state == "signal"
    assert len(batch.findings) == 1
    f = batch.findings[0]
    assert f.rule_or_category == "execution_gap.fast_closure"
    assert f.threshold == DEFAULT_FAST_CLOSURE_POLICY.critical_max_seconds
    assert f.statistic is not None and f.statistic < 600
    assert 0.0 < f.effect <= 1.0
    assert f.confidence is not None
    assert 0.0 < f.confidence.analytical_support <= 1.0
    assert 0.0 < f.confidence.evidence_completeness <= 1.0
    assert f.confidence.peer_confidence is None  # peer is a later phase
    # every finding cites at least one SourceRecord (SIH-EX-02)
    assert f.evidence_refs


def test_threshold_boundary_below_threshold_signals_at_threshold_does_not():
    """At exactly the threshold, the worker does not fire (strictly less than)."""
    worker = FastClosureWorker(thresholds=FastClosureThresholds(
        critical_max_seconds=600.0, high_max_seconds=1800.0,
        medium_max_seconds=3600.0, absolute_floor_seconds=30.0,
        min_count_per_severity=1))
    # 29 = below the absolute floor → excluded; 599 = below the threshold
    # → signal; 600 = at the threshold → not signalled
    alerts = [
        _alert(severity="critical", close_seconds=29, id="a-floor"),
        _alert(severity="critical", close_seconds=599, id="a-below"),
        _alert(severity="critical", close_seconds=600, id="a-at"),
    ]
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert batch.state == "signal"
    assert len(batch.findings) == 1
    f = batch.findings[0]
    assert f.scoped_subjects == ["a-below"]


def test_absolute_floor_excludes_obviously_auto_closed_alerts():
    """Closure in 5 seconds is a common auto-closure; not the worker's
    place to flag it (the workflow is, possibly, a 'noise' issue, not a
    supervisory finding)."""
    worker = FastClosureWorker()
    alerts = [_alert(severity="critical", close_seconds=5)]
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert batch.state == "no_signal"


def test_missing_data_emits_insufficient_data():
    """No alerts at all in scope → insufficient_data (not no_signal — a
    detector that was not actually run is structurally different from one
    that ran and found nothing)."""
    worker = FastClosureWorker()
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=[]), baselines, policy, _ctx())
    assert batch.state == "insufficient_data"
    assert batch.findings == []


def test_multiple_severities_produce_multiple_findings():
    """One critical + one high + one medium all fast-closed → 3 findings,
    one per severity, in the canonical order."""
    worker = FastClosureWorker()
    alerts = [
        _alert(severity="critical", close_seconds=120, id="a-c"),
        _alert(severity="high", close_seconds=600, id="a-h"),
        _alert(severity="medium", close_seconds=1200, id="a-m"),
    ]
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert batch.state == "signal"
    rules = [f.rule_or_category for f in batch.findings]
    # one finding per severity, all share the same rule
    assert rules == ["execution_gap.fast_closure"] * 3
    stats = {round(f.statistic): f for f in batch.findings}
    assert round(stats[120].statistic) == 120
    assert round(stats[600].statistic) == 600
    assert round(stats[1200].statistic) == 1200


def test_unknown_severity_excluded_by_design():
    """Alerts with mapped_severity='unknown' are intentionally not flagged
    by this worker — the system did not classify them, so the worker
    should not raise findings on data it does not understand."""
    worker = FastClosureWorker()
    a = Alert(id="a-u", entity_id="e", assessment_id="a", native_id="U1",
              created_at=1000.0, mapped_severity="unknown", closed_at=1010.0)
    snap, baselines, policy = _empty_args()
    batch = worker.evaluate(snap, _dataset(alerts=[a]), baselines, policy, _ctx())
    assert batch.state == "no_signal"


def test_worker_is_deterministic():
    """Two runs over the same dataset produce the same findings
    (modulo the run-scope identifiers, which the worker does not
    generate — they are filled in by the RunService)."""
    worker = FastClosureWorker()
    alerts = [
        _alert(severity="critical", close_seconds=120, id="a1"),
        _alert(severity="high", close_seconds=600, id="a2"),
    ]
    snap, baselines, policy = _empty_args()
    b1 = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    b2 = worker.evaluate(snap, _dataset(alerts=alerts), baselines, policy, _ctx())
    assert b1.state == b2.state == "signal"
    assert len(b1.findings) == len(b2.findings) == 2
    # statistic + threshold + effect are pure functions of input
    for f1, f2 in zip(b1.findings, b2.findings):
        assert f1.statistic == f2.statistic
        assert f1.threshold == f2.threshold
        assert f1.effect == f2.effect
        assert f1.scoped_subjects == f2.scoped_subjects


def test_baseline_and_policy_do_not_change_first_phase_results():
    """The Phase 4 worker ignores baselines and policy — they exist on
    the contract so a peer-benchmarking layer (Phase 8) can slot in
    without changing the worker signature."""
    worker = FastClosureWorker()
    alerts = [_alert(severity="critical", close_seconds=120, id="a1")]
    snap, _, _ = _empty_args()
    ctx = _ctx()
    no_bl = worker.evaluate(snap, _dataset(alerts=alerts), [], None, ctx)
    with_bl = worker.evaluate(
        snap, _dataset(alerts=alerts),
        [BaselineRef("peer", "d")], PolicyRef("v1", "dp"), ctx)
    assert no_bl.state == with_bl.state
    assert no_bl.findings[0].statistic == with_bl.findings[0].statistic


# ---------------------------------------------------------------------------
# RunService — integration (persistence, state machine, crash isolation)
# ---------------------------------------------------------------------------

def _ingest_healthy_alerts(service, alerts_csv_text, name="CSE-001"):
    """Helper: open a scope and ingest one CSV of alerts."""
    import csv
    from io import StringIO
    entity, a = _open_scope(service, name)
    rows = list(csv.DictReader(StringIO(alerts_csv_text)))
    # use the engine directly to skip the directory / file scanner
    sub = SubmissionStore(service._db)  # type: ignore[attr-defined]
    from satsa.domain.entities import Submission
    import time as _t
    sub.insert(
        Submission(id="sub-1", assessment_id=a.id, source_system="test",
                   declared_period_start=BASE, declared_period_end=END,
                   file_digests={"alerts.csv": "fd-x"},
                   declared_counts={"alerts": len(rows)}, received_at=_t.time(),
                   signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap-x", created_at=_t.time())
    for r in rows:
        rec = Alert(
            entity_id=entity.id, assessment_id=a.id,
            native_id=r["native_id"], created_at=float(r["created_at"]),
            mapped_severity=r["severity"],
            acknowledged_at=float(r["acknowledged_at"]) if r.get("acknowledged_at") else None,
            closed_at=float(r["closed_at"]) if r.get("closed_at") else None,
            source_record_ref="srcrec-" + r["native_id"],
        )
        AlertStore(service._db).insert(rec, submission_id="sub-1")  # type: ignore[attr-defined]
    return entity, a


def test_run_service_persists_run_observation_finding_and_job(service, engine):
    csv = (
        "native_id,created_at,severity,closed_at\n"
        f"A1,{BASE},critical,{BASE + 120}\n"            # fast close
        f"A2,{BASE},high,{BASE + 24 * 3600}\n"          # healthy
    )
    entity, a = _ingest_healthy_alerts(service, csv, "CSE-FAST")

    result = service.run_analysis(entity.id, a.id)
    assert result.status == "completed"
    # The default worker set has 14 workers (Phase 5 + Phase 6 +
    # Phase 7 + Phase 8 + the five Phase P14 supervisory workers:
    # coverage-gap, drift, cross-entity-insights, case-similarity,
    # evidence-completeness). A1 is a critical alert that closed in
    # 120s with no escalation, no cases, no steps → fast-closure
    # (5.2) and critical-without-escalation (5.3) fire; the
    # negative-space worker adds missing-investigation,
    # missing-escalation, and missing-disposition findings for the
    # same scope; the anomaly worker may flag the slow closure
    # as well; the peer-benchmark worker is silent (no peers).
    assert len(result.observation_ids) == 14
    assert len(result.finding_ids) >= 4
    assert result.error == ""
    assert len(result.jobs) == 14
    assert all(j.status == "completed" for j in result.jobs)

    run = RunStore(engine).get(result.run_id)
    assert run is not None
    assert run["status"] == "completed"
    obs = ObservationStore(engine).list_for_run(run["id"])
    assert len(obs) == 14
    fc_obs = next(o for o in obs if o["worker_name"] == "fast-closure")
    assert fc_obs["state"] == "signal"
    findings = FindingStore(engine).list_for_run(run["id"])
    assert len(findings) >= 4
    rules = {f["rule_or_category"] for f in findings}
    assert "execution_gap.fast_closure" in rules
    assert "execution_gap.critical_without_escalation" in rules
    # the negative-space engine correctly reports missing-file rather
    # than missing-investigation for the cases category
    assert "negative_space.missing_file.cases" in rules
    jobs = JobStore(engine).list_for_run(run["id"])
    assert len(jobs) == 14
    assert all(j["status"] == "completed" for j in jobs)


def test_run_service_rerun_creates_new_run_not_overwrite(service, engine):
    csv = f"native_id,created_at,severity,closed_at\nA1,{BASE},critical,{BASE + 120}\n"
    entity, a = _ingest_healthy_alerts(service, csv, "CSE-RERUN")
    r1 = service.run_analysis(entity.id, a.id)
    r2 = service.run_analysis(entity.id, a.id)
    assert r1.run_id != r2.run_id
    assert len(RunStore(engine).list_for_scope(entity.id, a.id)) == 2


def test_run_service_handles_failing_worker_without_crashing_run(
    service, engine
):
    csv = f"native_id,created_at,severity,closed_at\nA1,{BASE},critical,{BASE + 120}\n"
    entity, a = _ingest_healthy_alerts(service, csv, "CSE-CRASH")
    # replace default workers: one OK, one that crashes
    from satsa.contracts.worker import CrashingWorker

    class CrashingV2(CrashingWorker):
        name = "crashing-worker-2"
        version = "0.1.0"

    result = service.run_analysis(
        entity.id, a.id,
        workers=[FastClosureWorker(), CrashingV2()],
    )
    # the successful worker still produced its finding; the crashing
    # worker is recorded as a failed job
    assert result.status == "partial"
    assert len(result.finding_ids) == 1
    assert "crashing-worker-2" in result.error


def test_run_service_with_no_workers_rejected(service):
    entity, a = _open_scope(service, "CSE-NONE")
    with pytest.raises(ValueError):
        service.run_analysis(entity.id, a.id, workers=[])


def test_observation_id_backfilled_into_findings(service, engine):
    csv = (
        f"native_id,created_at,severity,closed_at\n"
        f"A1,{BASE},critical,{BASE + 120}\n"
        f"A2,{BASE},high,{BASE + 600}\n"
    )
    entity, a = _ingest_healthy_alerts(service, csv, "CSE-BACKFILL")
    result = service.run_analysis(entity.id, a.id)
    obs = ObservationStore(engine).list_for_run(result.run_id)
    assert obs
    findings = FindingStore(engine).list_for_run(result.run_id)
    obs_ids = {o["id"] for o in obs}
    assert all(f["observation_id"] in obs_ids for f in findings)


def test_run_service_uses_custom_thresholds(service, engine):
    csv = (
        f"native_id,created_at,severity,closed_at\n"
        f"A1,{BASE},high,{BASE + 500}\n"   # 500s — fast under aggressive
    )
    entity, a = _ingest_healthy_alerts(service, csv, "CSE-CUSTOM")
    # aggressive thresholds: 300s for high → 500s does not trigger
    # fast-closure; the other Phase 5/6 workers will still fire on
    # this minimal scope (no cases, no steps, no escalation, no
    # disposition) — we only assert here that the *fast-closure*
    # finding is absent.
    result = service.run_analysis(
        entity.id, a.id,
        thresholds=FastClosureThresholds(
            high_max_seconds=300.0, critical_max_seconds=120.0,
            absolute_floor_seconds=10.0, min_count_per_severity=1),
    )
    assert result.status == "completed"
    # no fast-closure signal under aggressive threshold
    eng = service._db  # type: ignore[attr-defined]
    fc = eng.query_all(
        "SELECT 1 FROM satsa_findings WHERE rule_or_category='execution_gap.fast_closure'"
        " AND observation_id IN (SELECT id FROM satsa_observations WHERE run_id=?)",
        (result.run_id,))
    assert fc == []

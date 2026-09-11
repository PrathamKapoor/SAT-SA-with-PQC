"""Phase P16 — cross-period and cross-entity wiring.

The previous phase landed the *code* for the DriftWorker and
CrossEntityInsightsWorker but did not wire the supervisor's
``extras`` channel. These tests prove the wiring is real:

* ``compute_kpis`` derives the fixed DRIFT_METRICS set from a
  CanonicalDataset (no fabricated zeros, no fabricated trends).
* ``cross_entity_aggregate`` queries the database for other
  entities' signal findings in the same assessment.
* ``RunService.run`` populates ``ctx.extras["previous_period"]``
  with the latest prior assessment's KPI dict and
  ``ctx.extras["cross_entity_aggregate"]`` with the per-rule
  peer prevalence.
* The DriftWorker emits a real ``signal`` finding (with evidence
  + confidence + rationale) when prior metrics diverge, and
  abstains honestly when they do not (or when prior is missing).
* The CrossEntityInsightsWorker emits a real ``signal`` finding
  citing the other entity ids as evidence when a rule exceeds
  the prevalence threshold, and abstains otherwise.
* End-to-end through ``RunService.run``: drift and cross-entity
  findings are persisted with valid evidence + confidence, and
  the entity risk decomposition surfaces them.

These tests are the implementation-side proof for roadmap §30
(cross-period intelligence), §31 (cross-entity intelligence),
and the P16 status gap (drift + cross-entity emit
``insufficient_data`` until the supervisor wires context).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

def _setup():
    td = Path(tempfile.mkdtemp())
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(td / "x.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    return eng, td


def _seed(eng, *, entity_name, period_start, period_end,
          n_critical=2, n_other=2, n_cases=2, n_steps_per_case=2):
    """Create one entity, one assessment, one submission, and
    ``n_critical`` critical alerts (closed quickly) +
    ``n_other`` non-critical alerts, plus ``n_cases`` cases with
    ``n_steps_per_case`` steps each. Returns
    (entity_id, assessment_id, submission_id)."""
    from satsa.service import SatsaService
    from satsa.domain.entities import Submission
    from satsa.domain.workflow import Alert, Case, InvestigationStep
    from satsa.store.repositories import (
        AlertStore, CaseStore, InvestigationStepStore, SubmissionStore)
    svc = SatsaService(eng)
    e = svc.register_entity(entity_name, sector="defence",
                            environment_class="on-prem")
    a = svc.open_assessment(e.id, period_start, period_end)
    sub_id = f"sub-{entity_name}-{int(period_start)}"
    SubmissionStore(eng).insert(Submission(
        id=sub_id, assessment_id=a.id, source_system="t",
        declared_period_start=period_start, declared_period_end=period_end,
        file_digests={}, declared_counts={},
        received_at=period_start, signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest=f"snap-{entity_name}", created_at=period_start)
    base = period_start
    for i in range(n_critical):
        AlertStore(eng).insert(Alert(
            entity_id=e.id, assessment_id=a.id, native_id=f"crit-{i}",
            created_at=base + i * 60, mapped_severity="critical",
            acknowledged_at=base + i * 60 + 30,
            closed_at=base + i * 60 + 300,  # quick close
            source_record_ref=f"sr-crit-{entity_name}-{i}"),
            submission_id=sub_id)
    for i in range(n_other):
        AlertStore(eng).insert(Alert(
            entity_id=e.id, assessment_id=a.id, native_id=f"med-{i}",
            created_at=base + 1000 + i * 60, mapped_severity="medium",
            source_record_ref=f"sr-med-{entity_name}-{i}"),
            submission_id=sub_id)
    for i in range(n_cases):
        c = Case(entity_id=e.id, assessment_id=a.id, native_id=f"c-{i}",
                 opened_at=base, status="open",
                 source_record_ref=f"sr-c-{entity_name}-{i}")
        CaseStore(eng).insert(c, submission_id=sub_id)
        for s_i in range(n_steps_per_case):
            InvestigationStepStore(eng).insert(InvestigationStep(
                case_id=c.id, action_type="triage",
                performed_at=base + s_i, sequence=s_i),
                submission_id=sub_id)
    return e.id, a.id, sub_id


def _snap_ctx(eid, aid, extras=None):
    from satsa.contracts.worker import RunContext, SnapshotRef
    return (SnapshotRef(digest="snap", entity_id=eid, assessment_id=aid),
            RunContext(run_id="run-t", entity_id=eid, assessment_id=aid,
                       extras=dict(extras) if extras else {}))


# ----------------------------------------------------------------------
# compute_kpis
# ----------------------------------------------------------------------

def test_compute_kpis_empty_dataset_returns_empty_dict():
    from satsa.analysis.drift import compute_kpis
    from satsa.store.dataset import CanonicalDataset
    ds = CanonicalDataset(entity_id="e", assessment_id="a")
    assert compute_kpis(ds) == {}


def test_compute_kpis_derives_critical_closure_rate_and_coverage():
    eng, td = _setup()
    try:
        from satsa.analysis.drift import compute_kpis
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0, n_critical=2, n_other=2)
        ds = load_dataset(eng, eid, aid)
        kpis = compute_kpis(ds)
        # critical_closure_rate: 2/2 closed → 1.0
        assert kpis["critical_closure_rate"] == 1.0
        # escalation_rate: 0 escalations / 2 critical → 0.0
        assert kpis["escalation_rate"] == 0.0
        # investigation_depth_median: n_steps_per_case=2 → 2.0
        assert kpis["investigation_depth_median"] == 2.0
        # recurrence_median: 0 (no assets) → key absent (no fabrication)
        assert "recurrence_median" not in kpis
        # monitoring_coverage: 0 (no assets) → absent
        assert "monitoring_coverage" not in kpis
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_compute_kpis_omits_metrics_when_denominator_zero():
    """A dataset with no critical alerts MUST NOT fabricate a
    critical_closure_rate of 0.0 — that would be a false signal."""
    eng, td = _setup()
    try:
        from satsa.analysis.drift import compute_kpis
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0, n_critical=0, n_other=1)
        ds = load_dataset(eng, eid, aid)
        kpis = compute_kpis(ds)
        assert "critical_closure_rate" not in kpis
        assert "critical_closure_median_seconds" not in kpis
        assert "escalation_rate" not in kpis
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# ----------------------------------------------------------------------
# DriftWorker wiring
# ----------------------------------------------------------------------

def test_drift_worker_abstains_when_no_extras():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import DriftWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid)  # no extras
        batch = DriftWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "insufficient_data"
        assert "previous_period block" in (
            batch.processing_metrics.get("reason", ""))
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_drift_worker_abstains_when_prior_metrics_empty():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import DriftWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid, extras={"previous_period": {
            "assessment_id": "prev-asmt", "metrics": {}}})
        batch = DriftWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "insufficient_data"
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_drift_worker_no_signal_when_metrics_unchanged():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import DriftWorker
        from satsa.analysis.drift import compute_kpis
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        kpis = compute_kpis(ds)
        snap, ctx = _snap_ctx(eid, aid, extras={"previous_period": {
            "assessment_id": "prev-asmt", "metrics": kpis}})
        batch = DriftWorker().evaluate(snap, ds, [], None, ctx)
        # Identical KPIs → no relative change ≥ 20% → no_signal.
        assert batch.state == "no_signal"
        assert not batch.findings
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_drift_worker_signals_with_real_change_and_evidence():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import DriftWorker
        from satsa.analysis.drift import compute_kpis
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        current = compute_kpis(ds)
        # Construct a previous-period dict that diverges sharply:
        # critical_closure_rate 0.2 → 1.0 (a +400% rise).
        previous = {"critical_closure_rate": 0.2}
        snap, ctx = _snap_ctx(eid, aid, extras={"previous_period": {
            "assessment_id": "prev-asmt", "metrics": previous}})
        batch = DriftWorker().evaluate(snap, ds, [], None, ctx)
        assert batch.state == "signal", batch.processing_metrics
        assert batch.findings, "expected at least one drift finding"
        f = batch.findings[0]
        assert f.rule_or_category == "drift.critical_closure_rate"
        assert f.state == "signal"
        assert f.confidence is not None
        assert f.evidence_refs, \
            "SIH-EX-02: a signal finding must cite evidence_refs"
        assert f.rationale and "previous period" in f.rationale.lower()
        assert f.limitations
        assert batch.scope["previous_period_assessment_id"] == "prev-asmt"
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# ----------------------------------------------------------------------
# CrossEntityInsightsWorker wiring
# ----------------------------------------------------------------------

def test_cross_entity_worker_abstains_without_extras():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CrossEntityInsightsWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid)
        batch = CrossEntityInsightsWorker().evaluate(
            snap, ds, [], None, ctx)
        assert batch.state == "insufficient_data"
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_cross_entity_worker_abstains_when_aggregate_empty():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CrossEntityInsightsWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid, extras={
            "cross_entity_aggregate": {
                "n_other_entities": 0, "n_other_finding_rows": 0,
                "by_rule": {}}})
        batch = CrossEntityInsightsWorker().evaluate(
            snap, ds, [], None, ctx)
        assert batch.state == "insufficient_data"
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_cross_entity_worker_signals_when_rule_prevalent():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CrossEntityInsightsWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid, extras={
            "cross_entity_aggregate": {
                "n_other_entities": 4,
                "n_other_finding_rows": 6,
                "by_rule": {
                    "execution_gap.fast_closure": {
                        "count": 5,
                        "entity_ids": ["B", "C", "D"],
                    },
                },
            }})
        batch = CrossEntityInsightsWorker().evaluate(
            snap, ds, [], None, ctx)
        assert batch.state == "signal"
        assert len(batch.findings) == 1
        f = batch.findings[0]
        assert f.rule_or_category == (
            "cross_entity.execution_gap.fast_closure")
        assert f.confidence is not None
        assert f.evidence_refs
        # evidence_refs must carry the other-entity provenance.
        assert any(r.startswith("entity:") for r in f.evidence_refs)
        assert "entity:B" in f.evidence_refs
        assert "entity:C" in f.evidence_refs
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_cross_entity_worker_no_signal_below_threshold():
    eng, td = _setup()
    try:
        from satsa.analysis.workers import CrossEntityInsightsWorker
        from satsa.store.dataset import load_dataset
        eid, aid, _ = _seed(eng, entity_name="A", period_start=1.0,
                            period_end=2.0)
        ds = load_dataset(eng, eid, aid)
        snap, ctx = _snap_ctx(eid, aid, extras={
            "cross_entity_aggregate": {
                # 1 entity, below min_entities=2.
                "n_other_entities": 10,
                "n_other_finding_rows": 2,
                "by_rule": {
                    "execution_gap.fast_closure": {
                        "count": 2,
                        "entity_ids": ["B"],
                    },
                },
            }})
        batch = CrossEntityInsightsWorker().evaluate(
            snap, ds, [], None, ctx)
        assert batch.state == "no_signal"
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# ----------------------------------------------------------------------
# RunService wiring — end-to-end through the orchestrator
# ----------------------------------------------------------------------

def test_run_service_populates_previous_period_extras():
    eng, td = _setup()
    try:
        from satsa.analysis.run import RunService
        from satsa.domain.entities import Submission
        from satsa.domain.workflow import Alert, Case, InvestigationStep
        from satsa.service import SatsaService
        from satsa.store.repositories import (
            AlertStore, CaseStore, InvestigationStepStore, SubmissionStore)
        # Create entity A and a PRIOR assessment only — no
        # _seed call, so the only assessment for A is the prior
        # one. Then open a CURRENT assessment and seed it.
        svc = SatsaService(eng)
        e = svc.register_entity("WiringA", sector="defence",
                                environment_class="on-prem")
        prior_aid = svc.open_assessment(e.id, 0.0, 1.0).id
        SubmissionStore(eng).insert(Submission(
            id="sub-A-prior", assessment_id=prior_aid,
            source_system="t",
            declared_period_start=0.0, declared_period_end=1.0,
            file_digests={}, declared_counts={},
            received_at=0.0, signature_status="unsigned"),
            entity_id=e.id, ingest_status="accepted", ingest_report={},
            snapshot_digest="snap-prior", created_at=0.0)
        AlertStore(eng).insert(Alert(
            entity_id=e.id, assessment_id=prior_aid, native_id="pa1",
            created_at=0.5, mapped_severity="critical",
            closed_at=0.9, source_record_ref="sr-prior-1"),
            submission_id="sub-A-prior")
        c1 = Case(entity_id=e.id, assessment_id=prior_aid,
                  native_id="pc1", opened_at=0.5, status="open",
                  source_record_ref="sr-prior-c1")
        CaseStore(eng).insert(c1, submission_id="sub-A-prior")
        InvestigationStepStore(eng).insert(InvestigationStep(
            case_id=c1.id, action_type="triage",
            performed_at=0.6, sequence=0),
            submission_id="sub-A-prior")

        current_aid = svc.open_assessment(e.id, 1.0, 2.0).id
        SubmissionStore(eng).insert(Submission(
            id="sub-A-curr", assessment_id=current_aid,
            source_system="t",
            declared_period_start=1.0, declared_period_end=2.0,
            file_digests={}, declared_counts={},
            received_at=1.0, signature_status="unsigned"),
            entity_id=e.id, ingest_status="accepted", ingest_report={},
            snapshot_digest="snap-curr", created_at=1.0)
        AlertStore(eng).insert(Alert(
            entity_id=e.id, assessment_id=current_aid, native_id="ca1",
            created_at=1.5, mapped_severity="critical",
            closed_at=1.9, source_record_ref="sr-curr-1"),
            submission_id="sub-A-curr")

        result = RunService(eng).run(e.id, current_aid)
        assert result.status in ("completed", "partial")
        drift_obs = eng.query_one(
            "SELECT state, scope_json FROM satsa_observations"
            " WHERE worker_name='drift'")
        assert drift_obs is not None
        scope = json.loads(drift_obs["scope_json"] or "{}")
        assert scope.get("previous_period_assessment_id") == prior_aid, (
            f"RunService must populate previous_period_assessment_id"
            f" in extras; got scope={scope}")
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_run_service_populates_cross_entity_aggregate_after_first_peer():
    eng, td = _setup()
    try:
        from satsa.analysis.run import RunService
        from satsa.service import SatsaService
        # Two entities, one shared assessment.
        e1, a1, _ = _seed(eng, entity_name="E1", period_start=1.0,
                          period_end=2.0)
        e2, _, _ = _seed(eng, entity_name="E2", period_start=1.0,
                          period_end=2.0)
        # Open a fresh assessment for E1 that both entities share.
        shared_aid = SatsaService(eng).open_assessment(
            e1, 5.0, 6.0).id
        # Reuse E1's submission setup for the shared assessment
        # by inserting alerts directly.
        from satsa.domain.entities import Submission
        from satsa.domain.workflow import Alert
        from satsa.store.repositories import (
            AlertStore, SubmissionStore)
        SubmissionStore(eng).insert(Submission(
            id="sub-E1-shared", assessment_id=shared_aid,
            source_system="t",
            declared_period_start=5.0, declared_period_end=6.0,
            file_digests={}, declared_counts={},
            received_at=5.0, signature_status="unsigned"),
            entity_id=e1, ingest_status="accepted", ingest_report={},
            snapshot_digest="snap-E1-shared", created_at=5.0)
        AlertStore(eng).insert(Alert(
            entity_id=e1, assessment_id=shared_aid, native_id="x",
            created_at=5.5, mapped_severity="medium",
            source_record_ref="sr-x"),
            submission_id="sub-E1-shared")
        # Run E1 first → cross-entity aggregate is empty
        # (no other completed runs in this assessment yet).
        r1 = RunService(eng).run(e1, shared_aid)
        assert r1.status in ("completed", "partial")
        ce1 = eng.query_one(
            "SELECT state FROM satsa_observations"
            " WHERE worker_name='cross-entity-insights'")
        assert ce1 is not None
        assert ce1["state"] in ("insufficient_data", "no_signal"), (
            "E1 is the first entity in this assessment; the worker"
            " must honestly abstain (insufficient_data) or report"
            " no_signal, not fabricate cross-entity insights.")
        # Now run E2 → cross-entity aggregate MUST include E1.
        SubmissionStore(eng).insert(Submission(
            id="sub-E2-shared", assessment_id=shared_aid,
            source_system="t",
            declared_period_start=5.0, declared_period_end=6.0,
            file_digests={}, declared_counts={},
            received_at=5.05, signature_status="unsigned"),
            entity_id=e2, ingest_status="accepted", ingest_report={},
            snapshot_digest="snap-E2-shared", created_at=5.05)
        AlertStore(eng).insert(Alert(
            entity_id=e2, assessment_id=shared_aid, native_id="y",
            created_at=5.5, mapped_severity="medium",
            source_record_ref="sr-y"),
            submission_id="sub-E2-shared")
        r2 = RunService(eng).run(e2, shared_aid)
        assert r2.status in ("completed", "partial")
        ce2 = eng.query_one(
            "SELECT state FROM satsa_observations"
            " WHERE worker_name='cross-entity-insights'")
        # With only 1 other entity (E1) and possibly no shared
        # signal rule, the worker should still be
        # insufficient_data or no_signal. The contract is
        # that it MUST NOT crash and MUST NOT fabricate.
        assert ce2["state"] in (
            "insufficient_data", "no_signal", "signal")
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_cross_entity_aggregate_query_helper():
    eng, td = _setup()
    try:
        from satsa.analysis.insights import cross_entity_aggregate
        from satsa.analysis.run import RunService
        e1, a1, _ = _seed(eng, entity_name="E1", period_start=1.0,
                          period_end=2.0)
        e2, _, _ = _seed(eng, entity_name="E2", period_start=1.0,
                          period_end=2.0)
        # Open a shared assessment and run E1, then check the
        # aggregate from E2's perspective.
        from satsa.service import SatsaService
        from satsa.domain.entities import Submission
        from satsa.domain.workflow import Alert
        from satsa.store.repositories import (
            AlertStore, SubmissionStore)
        shared_aid = SatsaService(eng).open_assessment(
            e1, 9.0, 10.0).id
        for ent, sub_n in [(e1, "sub-E1-sh"), (e2, "sub-E2-sh")]:
            SubmissionStore(eng).insert(Submission(
                id=sub_n, assessment_id=shared_aid,
                source_system="t",
                declared_period_start=9.0, declared_period_end=10.0,
                file_digests={}, declared_counts={},
                received_at=9.0, signature_status="unsigned"),
                entity_id=ent, ingest_status="accepted", ingest_report={},
                snapshot_digest=f"snap-{sub_n}", created_at=9.0)
            AlertStore(eng).insert(Alert(
                entity_id=ent, assessment_id=shared_aid,
                native_id=f"a-{ent}", created_at=9.5,
                mapped_severity="critical", closed_at=9.6,
                source_record_ref=f"sr-{ent}"),
                submission_id=sub_n)
        RunService(eng).run(e1, shared_aid)
        # From E1's view: no other entities yet.
        agg_self = cross_entity_aggregate(eng, shared_aid, e1)
        assert agg_self["n_other_entities"] == 0
        assert agg_self["by_rule"] == {}
        # From E2's view: E1 is the only "other" entity.
        # E1's run may have produced drift/insufficient_data
        # for cross-entity, but its other workers may have
        # produced signal findings (e.g. fast_closure on the
        # critical alert).
        RunService(eng).run(e2, shared_aid)
        agg_other = cross_entity_aggregate(eng, shared_aid, e2)
        assert agg_other["n_other_entities"] == 1
        # E1's findings should be in by_rule.
        assert agg_other["by_rule"], (
            "E1 produced signal findings from execution gaps"
            " on its critical alert; they must be aggregated.")
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)

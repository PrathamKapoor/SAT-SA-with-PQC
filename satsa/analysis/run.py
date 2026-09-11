"""RunService — turn one (entity, assessment) into a persisted analysis
run: create the AnalysisRun, load the frozen CanonicalDataset, run
every registered worker through the existing Orchestrator contract,
and persist the resulting observations/findings/jobs in a single
transaction.

The orchestrator is unchanged from Phase 2's contract; this service
is the thin glue that supplies the dataset, persists the run, and
translates a list of ``Job``s into the run's overall status.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from satsa import __version__ as _SATSA_VERSION
from satsa.analysis import ANALYTICS_VERSION
from satsa.analysis.repository import (
    FindingStore,
    JobStore,
    ObservationStore,
    RunStore,
)
from satsa.analysis.workers import (
    DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY,
    DEFAULT_ANOMALY_POLICY,
    DEFAULT_CASE_SIMILARITY_POLICY,
    DEFAULT_COVERAGE_GAP_POLICY,
    DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY,
    DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY,
    DEFAULT_DRIFT_POLICY,
    DEFAULT_EVIDENCE_COMPLETENESS_POLICY,
    DEFAULT_FAST_CLOSURE_POLICY,
    DEFAULT_METRIC_GAMING_POLICY,
    DEFAULT_NEGATIVE_SPACE_POLICY,
    DEFAULT_PEER_BENCHMARK_POLICY,
    DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY,
    DEFAULT_REPEATED_INVESTIGATION_POLICY,
    AckWithoutInvestigationThresholds,
    AckWithoutInvestigationWorker,
    AnomalyThresholds,
    AnomalyWorker,
    CaseSimilarityThresholds,
    CaseSimilarityWorker,
    CoverageGapThresholds,
    CoverageGapWorker,
    CriticalWithoutEscalationThresholds,
    CriticalWithoutEscalationWorker,
    CrossEntityInsightsThresholds,
    CrossEntityInsightsWorker,
    DriftThresholds,
    DriftWorker,
    EvidenceCompletenessThresholds,
    EvidenceCompletenessWorker,
    FastClosureThresholds,
    FastClosureWorker,
    MetricGamingThresholds,
    MetricGamingWorker,
    NegativeSpaceThresholds,
    NegativeSpaceWorker,
    PeerBenchmarkThresholds,
    PeerBenchmarkWorker,
    RecurringWithoutRemediationThresholds,
    RecurringWithoutRemediationWorker,
    RepeatedInvestigationThresholds,
    RepeatedInvestigationWorker,
    DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY,
    WorkflowReconstructionThresholds,
    WorkflowReconstructionWorker,
    DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY,
    EntityAssetResolutionThresholds,
    EntityAssetResolutionWorker,
    attach_baseline,
    compute_peer_baseline,
)
from satsa.contracts.orchestration import Job, Orchestrator
from satsa.contracts.worker import (
    AnalyticalWorker,
    BaselineRef,
    PolicyRef,
    RunContext,
    SnapshotRef,
)
from satsa.domain.base import new_id
from satsa.domain.evidence import Finding, Observation
from satsa.domain.runs import AnalysisRun
from satsa.store.dataset import load_dataset

log = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    run_id: str
    status: str
    observation_ids: list
    finding_ids: list
    jobs: list
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "status": self.status,
            "observation_ids": list(self.observation_ids),
            "finding_ids": list(self.finding_ids),
            "jobs": [j.to_dict() for j in self.jobs],
            "error": self.error,
        }


def _default_workers(fast_closure_thresholds: FastClosureThresholds,
                    ack_thresholds: AckWithoutInvestigationThresholds | None = None,
                    crit_thresholds: CriticalWithoutEscalationThresholds | None = None,
                    repeated_thresholds: RepeatedInvestigationThresholds | None = None,
                    recurring_thresholds: RecurringWithoutRemediationThresholds | None = None,
                    gaming_thresholds: MetricGamingThresholds | None = None,
                    negative_space_thresholds: NegativeSpaceThresholds | None = None,
                    anomaly_thresholds: AnomalyThresholds | None = None,
                    peer_thresholds: PeerBenchmarkThresholds | None = None,
                    coverage_gap_thresholds: CoverageGapThresholds | None = None,
                    drift_thresholds: DriftThresholds | None = None,
                    cross_entity_thresholds: CrossEntityInsightsThresholds | None = None,
                    similarity_thresholds: CaseSimilarityThresholds | None = None,
                    completeness_thresholds: EvidenceCompletenessThresholds | None = None,
                    workflow_reconstruction_thresholds: WorkflowReconstructionThresholds | None = None,
                    entity_asset_resolution_thresholds: EntityAssetResolutionThresholds | None = None,
                    ) -> list[AnalyticalWorker]:
    """The default worker set — execution gaps + negative space +
    anomaly + peer benchmark + coverage gap + drift +
    cross-entity insights + case similarity + evidence
    completeness + workflow reconstruction + entity/asset
    resolution. Each subsequent phase appends to this list, never
    overwrites it — registry ordering stays deterministic."""
    return [
        FastClosureWorker(thresholds=fast_closure_thresholds),
        AckWithoutInvestigationWorker(
            thresholds=ack_thresholds or DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY),
        CriticalWithoutEscalationWorker(
            thresholds=crit_thresholds or DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY),
        RepeatedInvestigationWorker(
            thresholds=repeated_thresholds or DEFAULT_REPEATED_INVESTIGATION_POLICY),
        RecurringWithoutRemediationWorker(
            thresholds=recurring_thresholds or DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY),
        MetricGamingWorker(
            thresholds=gaming_thresholds or DEFAULT_METRIC_GAMING_POLICY),
        NegativeSpaceWorker(
            thresholds=negative_space_thresholds or DEFAULT_NEGATIVE_SPACE_POLICY),
        AnomalyWorker(
            thresholds=anomaly_thresholds or DEFAULT_ANOMALY_POLICY),
        PeerBenchmarkWorker(
            thresholds=peer_thresholds or DEFAULT_PEER_BENCHMARK_POLICY),
        CoverageGapWorker(
            thresholds=coverage_gap_thresholds or DEFAULT_COVERAGE_GAP_POLICY),
        DriftWorker(
            thresholds=drift_thresholds or DEFAULT_DRIFT_POLICY),
        CrossEntityInsightsWorker(
            thresholds=cross_entity_thresholds or DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY),
        CaseSimilarityWorker(
            thresholds=similarity_thresholds or DEFAULT_CASE_SIMILARITY_POLICY),
        EvidenceCompletenessWorker(
            thresholds=completeness_thresholds or DEFAULT_EVIDENCE_COMPLETENESS_POLICY),
        WorkflowReconstructionWorker(
            thresholds=workflow_reconstruction_thresholds
            or DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY),
        EntityAssetResolutionWorker(
            thresholds=entity_asset_resolution_thresholds
            or DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY),
    ]


class RunService:
    def __init__(self, database) -> None:
        if hasattr(database, "ensure_ready"):
            database.ensure_ready()
            self._db = database.engine
        else:
            self._db = database
        self.runs = RunStore(self._db)
        self.observations = ObservationStore(self._db)
        self.findings = FindingStore(self._db)
        self.jobs = JobStore(self._db)

    def run(self, entity_id: str, assessment_id: str, *,
            workers: Optional[Iterable[AnalyticalWorker]] = None,
            thresholds: Optional[FastClosureThresholds] = None,
            ack_thresholds: Optional[AckWithoutInvestigationThresholds] = None,
            crit_thresholds: Optional[CriticalWithoutEscalationThresholds] = None,
            repeated_thresholds: Optional[RepeatedInvestigationThresholds] = None,
            recurring_thresholds: Optional[RecurringWithoutRemediationThresholds] = None,
            gaming_thresholds: Optional[MetricGamingThresholds] = None,
            negative_space_thresholds: Optional[NegativeSpaceThresholds] = None,
            anomaly_thresholds: Optional[AnomalyThresholds] = None,
            peer_thresholds: Optional[PeerBenchmarkThresholds] = None,
            coverage_gap_thresholds: Optional[CoverageGapThresholds] = None,
            drift_thresholds: Optional[DriftThresholds] = None,
            cross_entity_thresholds: Optional[CrossEntityInsightsThresholds] = None,
            similarity_thresholds: Optional[CaseSimilarityThresholds] = None,
            completeness_thresholds: Optional[EvidenceCompletenessThresholds] = None,
            workflow_reconstruction_thresholds: Optional[WorkflowReconstructionThresholds] = None,
            entity_asset_resolution_thresholds: Optional[EntityAssetResolutionThresholds] = None,
            baselines: Optional[list[BaselineRef]] = None,
            policy: Optional[PolicyRef] = None,
            trust_key_dir: Optional[Path] = None,
            analytics_version: str = ANALYTICS_VERSION) -> AnalysisResult:
        """Execute one analysis run for the given scope. Returns the
        persisted AnalysisResult; the run is queryable via the stores.

        If ``trust_key_dir`` is provided, the run + every persisted
        finding is signed with a PQC keypair at the given directory
        (see ``satsa.analysis.trust.TrustService``); signatures are
        persisted in ``satsa_trust_receipts``. The run's
        ``summary_json`` records the algorithm + the number of
        signed findings."""
        if thresholds is None:
            thresholds = DEFAULT_FAST_CLOSURE_POLICY
        if workers is None:
            workers = _default_workers(
                thresholds, ack_thresholds, crit_thresholds,
                repeated_thresholds, recurring_thresholds, gaming_thresholds,
                negative_space_thresholds, anomaly_thresholds, peer_thresholds,
                coverage_gap_thresholds, drift_thresholds,
                cross_entity_thresholds, similarity_thresholds,
                completeness_thresholds, workflow_reconstruction_thresholds,
                entity_asset_resolution_thresholds)
        workers = list(workers)
        if not workers:
            raise ValueError("RunService.run requires at least one worker")

        # If the worker set contains a PeerBenchmarkWorker, compute
        # the baseline once and attach it to the worker (the worker
        # contract does not currently carry a baseline *data*
        # channel; this is the minimal way to feed it without
        # widening the contract).
        for w in workers:
            if isinstance(w, PeerBenchmarkWorker):
                baseline = compute_peer_baseline(self._db, entity_id,
                                                 min_peers=w.thresholds.min_peers)
                attach_baseline(w, baseline)

        dataset = load_dataset(self._db, entity_id, assessment_id)
        run = AnalysisRun(
            id=new_id("run"), entity_id=entity_id,
            assessment_id=assessment_id, snapshot_digest=dataset.snapshot_digest or "",
            code_version=_SATSA_VERSION, analytics_version=analytics_version,
            model_version=None, status="pending", started_at=time.time(),
        )

        # Build the per-run extras block the DriftWorker and
        # CrossEntityInsightsWorker consume: the previous period's
        # KPI dict (same entity, earlier assessment) and the
        # cross-entity aggregate for the same assessment. Both
        # are computed from the database at run start; neither
        # requires a schema change or a contract widening —
        # workers opt in via the documented ``extras`` channel.
        extras = self._build_run_extras(entity_id, assessment_id)

        orch = Orchestrator()
        for w in workers:
            orch.register(w)
        snapshot = SnapshotRef(digest=run.snapshot_digest, entity_id=entity_id,
                               assessment_id=assessment_id)
        ctx = RunContext(run_id=run.id, entity_id=entity_id,
                         assessment_id=assessment_id,
                         code_version=run.code_version, created_at=run.started_at,
                         extras=extras)

        # persist run + execute orchestrator + persist observations/findings/jobs
        # in a single transaction so a partial write never escapes.
        observation_ids: list[str] = []
        finding_ids: list[str] = []
        now = time.time()
        any_failed = False
        error_msg = ""
        with self._db.transaction():
            self.runs.insert(run, created_at=now)
            jobs = orch.run(ctx, snapshot, dataset, baselines or [], policy)
            for j in jobs:
                self.jobs.insert(j, created_at=time.time())
                if j.status == "failed":
                    any_failed = True
                    error_msg = error_msg + ("; " if error_msg else "") + \
                        f"{j.worker_name}: {j.error}"
                    continue
                batch = j.result
                if batch is None:
                    continue
                obs = Observation(
                    id=new_id("observation"), run_id=run.id,
                    worker_name=batch.worker_name,
                    detector_version=batch.detector_version,
                    entity_id=entity_id, assessment_id=assessment_id,
                    scope=dict(batch.scope), created_at=time.time(),
                )
                self.observations.insert(obs, created_at=time.time())
                self.observations.set_state(obs.id, batch.state)
                observation_ids.append(obs.id)
                for f in batch.findings:
                    if not isinstance(f, Finding):  # type: ignore[name-defined]
                        continue
                    f.observation_id = obs.id
                    f_errors = f.validate()
                    if f_errors:
                        log.warning("dropping invalid finding from %s (%s): %s",
                                    batch.worker_name, f.rule_or_category,
                                    "; ".join(f_errors))
                        continue
                    self.findings.insert(f, created_at=time.time())
                    finding_ids.append(f.id)
            status = "completed"
            if any_failed and observation_ids:
                status = "partial"
            elif any_failed and not observation_ids:
                status = "failed"
            finished = time.time()
            summary = {
                "workers": [w.name for w in workers],
                "observations": len(observation_ids),
                "findings": len(finding_ids),
                "failed_jobs": [j.worker_name for j in jobs if j.status == "failed"],
            }
            self.runs.set_status(
                run.id, status, finished_at=finished,
                observation_ids=observation_ids, finding_ids=finding_ids,
                error=error_msg, summary=summary,
            )
            run.status = status
            run.finished_at = finished
            run.observation_ids = observation_ids
            # Recompute the persisted content_digest so it reflects
            # the *post-completion* row state (finished_at,
            # observation_ids, summary_json, etc.). The seed the
            # trust layer signs is derived from this same canonical
            # reconstruction at verification time, so the stored
            # column, the receipt's content_digest, and the live
            # seed must agree.
            from satsa.analysis.canonical import canonical_run_dict_from_row
            from qsmlops.crypto.hashing import digest_document
            row = self.runs.get(run.id)
            if row is not None:
                new_seed = digest_document(canonical_run_dict_from_row(row))
                self._db.execute(
                    "UPDATE satsa_runs SET content_digest=? WHERE id=?",
                    (new_seed, run.id))

        # Sign the run + every persisted finding with a PQC keypair
        # (Phase 11). This is best-effort: if the key directory is
        # not provided, or signing fails, the run is still valid —
        # the supervisor just won't have a trust receipt to verify.
        if trust_key_dir is not None:
            try:
                from satsa.analysis.trust import attest_run_outputs
                run_row = self.runs.get(run.id)
                finding_rows = []
                for fid in finding_ids:
                    r = self._db.query_one(
                        "SELECT * FROM satsa_findings WHERE id=?", (fid,))
                    if r is not None:
                        finding_rows.append(dict(r))
                trust_summary = attest_run_outputs(
                    self._db, Path(trust_key_dir), run_row, finding_rows)
                # merge into the run's summary
                existing = json.loads(run_row.get("summary_json") or "{}")
                existing["trust"] = trust_summary
                self._db.execute(
                    "UPDATE satsa_runs SET summary_json=? WHERE id=?",
                    (json.dumps(existing), run.id))
            except Exception as exc:  # noqa: BLE001
                log.warning("trust attestation failed for run %s: %s",
                            run.id, exc)

        return AnalysisResult(
            run_id=run.id, status=status,
            observation_ids=observation_ids, finding_ids=finding_ids,
            jobs=jobs, error=error_msg,
        )

    def _build_run_extras(self, entity_id: str,
                          assessment_id: str) -> dict:
        """Build the ``extras`` block the DriftWorker and
        CrossEntityInsightsWorker consume via the documented
        ``run_context.extras`` channel.

        Two keys, both optional (absent == honest abstention):

        * ``previous_period``: {"assessment_id", "metrics"} for
          the same entity's most recent *prior* assessment
          (earlier ``period_start``), with the fixed DRIFT_METRICS
          KPI dict computed from that period's dataset. The
          block is present (with empty ``metrics``) when the
          prior assessment exists but produced no computable
          KPIs, and absent when there is no prior assessment at
          all.

        * ``cross_entity_aggregate``: per-rule prevalence of
          *other* entities' signal findings in the same
          assessment, shape::

              {"n_other_entities": int,
               "n_other_finding_rows": int,
               "by_rule": { rule: {"count": int, "entity_ids": [..]} }}

          Absent when there are no other entities with
          completed/partial runs yet in the same assessment
          (the first entity processed honestly abstains).

        * ``previous_period_assets``: the sorted list of asset
          ``native_id`` values submitted in the same prior
          assessment ``previous_period`` refers to (empty list if
          the prior assessment submitted no assets; absent
          entirely under the same conditions ``previous_period``
          is absent). Feeds
          ``EntityAssetResolutionWorker``'s vanished-asset check
          without a second dataset load — reuses the same
          ``prior_dataset`` already loaded for KPI computation
          above.
        """
        from satsa.analysis.drift import compute_kpis
        from satsa.analysis.insights import cross_entity_aggregate
        from satsa.store.dataset import load_dataset
        from satsa.store.repositories import AssessmentStore

        extras: dict = {}

        # ---- previous period (same entity, earlier period) ----
        current = AssessmentStore(self._db).get(assessment_id)
        if current is not None:
            current_start = float(current.get("period_start") or 0.0)
            prior = None
            for a in AssessmentStore(self._db).list_for_entity(entity_id):
                if a["id"] == assessment_id:
                    continue
                a_start = float(a.get("period_start") or 0.0)
                if a_start >= current_start:
                    continue
                # track the latest prior (greatest start < current_start)
                if prior is None or a_start > float(
                        prior.get("period_start") or 0.0):
                    prior = a
            if prior is not None:
                prior_dataset = None
                try:
                    prior_dataset = load_dataset(
                        self._db, entity_id, prior["id"])
                    prior_metrics = compute_kpis(prior_dataset)
                except Exception as exc:  # noqa: BLE001
                    # Dataset load is best-effort: a corrupt or
                    # missing prior period must not block the
                    # current run. The worker will see no
                    # previous_period and abstain honestly.
                    log.warning("could not load prior dataset %s: %s",
                                prior["id"], exc)
                    prior_metrics = None
                extras["previous_period"] = {
                    "assessment_id": prior["id"],
                    "period_start": float(prior.get("period_start") or 0.0),
                    "period_end": float(prior.get("period_end") or 0.0),
                    "metrics": prior_metrics or {},
                }
                if prior_dataset is not None:
                    extras["previous_period_assets"] = sorted(
                        {a.native_id for a in prior_dataset.assets})

        # ---- cross-entity aggregate (same assessment, other entities) ----
        try:
            extras["cross_entity_aggregate"] = cross_entity_aggregate(
                self._db, assessment_id, entity_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("cross_entity_aggregate failed: %s", exc)

        return extras

    def attest_run(self, run_id: str, trust_key_dir: Path) -> dict:
        """Sign a previously-completed run + its findings with the
        PQC keypair stored under ``trust_key_dir`` and return the
        trust summary (algorithm id, public key, counts).

        Useful when the run was completed before this phase shipped,
        or when an operator wants to re-sign after a key rotation."""
        from satsa.analysis.trust import attest_run_outputs
        run_row = self.runs.get(run_id)
        if run_row is None:
            raise ValueError(f"unknown run {run_id!r}")
        # Fetch the run + its findings, then sign.
        with self._db.transaction():
            findings = self.findings.list_for_run(run_id)
        return attest_run_outputs(self._db, trust_key_dir, run_row, findings)

    def verify_run(self, run_id: str, trust_key_dir: Path) -> dict:
        """Verify the run + every persisted finding against its
        trust receipt. Returns a per-subject status dict.

        Verification re-computes each record's current content
        digest from the live row and compares it to the digest the
        receipt was signed over — a row whose columns have been
        altered (e.g. a tampered rationale) is detected by digest
        mismatch even though the stored content_digest column is
        unchanged from insert time.
        """
        from satsa.analysis.trust import TrustService
        from satsa.analysis.canonical import (
            live_finding_digest, live_run_seed,
        )
        svc = TrustService(self._db, trust_key_dir)
        run_row = self.runs.get(run_id)
        result: dict = {"run": None, "findings": []}
        if run_row is None:
            return result
        current_run = live_run_seed(run_row)
        ok, reason = svc.verify_subject("run", run_id, current_run)
        result["run"] = {"ok": ok, "reason": reason}
        finding_rows = self.findings.list_for_run(run_id)
        result["reviews"] = []
        for f in finding_rows:
            current = live_finding_digest(f)
            ok, reason = svc.verify_subject("finding", f["id"], current)
            result["findings"].append({
                "finding_id": f["id"],
                "rule": f.get("rule_or_category", ""),
                "ok": ok, "reason": reason,
            })
            # Human-decision binding (P20): if this finding has any
            # recorded review decisions, check each decision's captured
            # finding_content_digest against the finding's *current*
            # live digest — this is a separate integrity claim from the
            # PQC signature check above (it detects a finding that
            # changed, or a review row that was tampered with, after a
            # human already acted on it).
            from satsa.analysis.review import ReviewService
            bindings = ReviewService(self._db).verify_binding(f["id"], dict(f))
            if bindings:
                result["reviews"].append({
                    "finding_id": f["id"], "decisions": bindings,
                })
        return result

    @staticmethod
    def _live_digest_for_run(run_row: dict) -> str:
        """Backwards-compatible alias for ``live_run_seed`` (the
        content-digest column is excluded from the seed)."""
        from satsa.analysis.canonical import live_run_seed
        return live_run_seed(run_row)

    @staticmethod
    def _live_digest_for_finding(finding_row: dict) -> str:
        """Backwards-compatible alias for ``live_finding_digest``."""
        from satsa.analysis.canonical import live_finding_digest
        return live_finding_digest(finding_row)

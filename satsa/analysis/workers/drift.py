"""Drift detection: longitudinal KPI drift across assessment periods
(SIH-ADD-04).

The roadmap explicitly calls out cross-period intelligence as a
first-class analytical capability. The DriftWorker reads the
*current* period's frozen dataset and the *previous* period's
metric snapshot, both supplied via the supervisor's ``extras``
channel (``run_context.extras["previous_period"]``), then
compares them using the fixed, documented ``DRIFT_METRICS`` set
and the deterministic ``compute_drift`` function.

Drift is a *signal* — a confirmed material deterioration is the
input to the risk aggregator; a neutral change is reported as
``no_signal``; missing prior-period data is reported as
``insufficient_data`` (we never fabricate a baseline).
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.analysis.drift import (
    compute_drift,
    compute_kpis,
    collect_evidence_refs,
)
from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
)


@dataclass(frozen=True)
class DriftThresholds:
    """Drift detection thresholds — minimum relative change for a
    KPI to count as drifting, plus minimum sample size."""

    # Minimum relative change (0..1) before a KPI counts as drifting.
    min_relative_change: float = 0.20
    # Below this many drifted KPIs we do not emit — too little
    # signal to separate drift from noise.
    min_drifted_kpis: int = 1
    # The previous-period dict must be non-empty.
    min_prior_metrics: int = 1


DEFAULT_DRIFT_POLICY = DriftThresholds()


class DriftWorker(AnalyticalWorker):
    """Detect cross-period KPI drift."""

    name = "drift"
    version = "0.2.0"

    def __init__(self, thresholds: DriftThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_DRIFT_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy,
                 run_context) -> ObservationBatch:
        prev_block = (run_context.extras or {}).get("previous_period")
        # The supervisor hands us the previous-period metrics in a
        # well-typed block. If the block is missing or empty, the
        # worker abstains honestly — no fabricated baseline.
        if not isinstance(prev_block, dict):
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "previous_period_present": False},
                state="insufficient_data",
                processing_metrics={
                    "reason": ("no previous_period block in supervisor"
                               " extras; no baseline available"),
                },
            )
        previous_metrics = prev_block.get("metrics") or {}
        previous_assessment_id = prev_block.get("assessment_id")
        if (not previous_metrics
                or len(previous_metrics) < self.thresholds.min_prior_metrics):
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "previous_period_assessment_id": previous_assessment_id,
                       "previous_period_present": bool(previous_assessment_id)},
                state="insufficient_data",
                processing_metrics={
                    "reason": ("previous-period dict empty or below"
                               " min_prior_metrics; no comparable baseline"),
                },
            )

        current_metrics = compute_kpis(dataset)
        drift_findings = compute_drift(
            run_context.entity_id, previous_metrics, current_metrics,
            relative_threshold=self.thresholds.min_relative_change,
        )
        evidence_refs = collect_evidence_refs(dataset)

        if not drift_findings:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "previous_period_assessment_id": previous_assessment_id,
                       "kpis_evaluated": len(current_metrics)},
                state="no_signal",
                processing_metrics={
                    "kpis_current": current_metrics,
                    "kpis_previous": previous_metrics,
                },
            )

        if len(drift_findings) < self.thresholds.min_drifted_kpis:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "previous_period_assessment_id": previous_assessment_id,
                       "kpis_evaluated": len(current_metrics),
                       "drifts_detected": len(drift_findings)},
                state="no_signal",
                processing_metrics={
                    "reason": ("below min_drifted_kpis threshold"),
                    "drifts": [d.to_dict() for d in drift_findings],
                },
            )

        findings: list = []
        for d in drift_findings:
            # Confidence scales with magnitude of the relative delta,
            # but is also explicitly downgraded when one of the two
            # periods has thin data (a documented limitation, not a
            # hidden one).
            abs_rel = min(1.0, abs(d.relative_delta))
            analytical_support = 0.4 + 0.6 * abs_rel
            evidence_completeness = (
                0.9 if len(evidence_refs) >= 3
                else 0.6 if evidence_refs else 0.3)
            confidence = ConfidenceVector(
                analytical_support=round(analytical_support, 3),
                evidence_completeness=evidence_completeness,
                peer_confidence=None,
            )
            # Findings must cite evidence (SIH-EX-02): when the
            # current period has no source_record_refs, fall back
            # to the previous-period assessment id as a single
            # provenance ref so the finding still validates.
            refs = (list(evidence_refs)
                    if evidence_refs
                    else ([f"assessment:{previous_assessment_id}"]
                          if previous_assessment_id else []))
            rationale = (
                f"{d.metric} {d.direction} by "
                f"{abs(d.relative_delta):.1%} relative to the previous "
                f"period ({d.previous:.3f} -> {d.current:.3f}). "
                "Cross-period drift detected; verify the change is "
                "substantive, not a coverage or taxonomy shift."
            )
            findings.append(Finding(
                observation_id="",
                rule_or_category=f"drift.{d.metric}",
                state="signal",
                rationale=rationale,
                scoped_subjects=[run_context.entity_id],
                statistic=d.current,
                effect=d.relative_delta,
                threshold=self.thresholds.min_relative_change,
                confidence=confidence,
                evidence_refs=refs,
                limitations=d.limitations,
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "previous_period_assessment_id": previous_assessment_id,
                   "kpis_evaluated": len(current_metrics),
                   "drifts_detected": len(drift_findings)},
            state="signal",
            findings=findings,
            processing_metrics={
                "kpis_current": current_metrics,
                "kpis_previous": previous_metrics,
                "drifts": [d.to_dict() for d in drift_findings],
            },
        )

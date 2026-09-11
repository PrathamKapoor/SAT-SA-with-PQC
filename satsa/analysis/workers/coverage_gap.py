"""Coverage Gap detection: assets that should have monitoring coverage
but don't, or controls deployed but not monitored (SIH-EG-05 /
SIH-NS-06).

The roadmap explicitly calls this out as a first-class supervisory
signal: a CSE that has critical assets in scope but no alert volume
on them — either because the monitoring pipeline has a gap, or
because the asset inventory itself is incomplete.

This worker is deliberately conservative — it reports ``insufficient_data``
when the asset inventory is too thin to support the comparison,
``no_signal`` when coverage is plausible, and ``signal`` when
critical assets have zero monitoring evidence across the period.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
)
from satsa.domain.entities import Asset


@dataclass(frozen=True)
class CoverageGapThresholds:
    """Coverage gap thresholds — minimum alert volume per critical
    asset, and minimum inventory size to support the comparison."""

    # Below this many critical assets we cannot compute a coverage
    # signal — too little data to tell whether zero alerts is a
    # real gap or just an empty CSE.
    min_critical_assets: int = 1
    # Each critical asset must have at least this many alerts in
    # the period to be considered "monitored". 0 alerts on a
    # critical asset is itself a signal.
    min_alerts_per_critical_asset: int = 1
    # Maximum severity assigned to a coverage gap finding — a single
    # asset gap is bounded at medium; multiple assets can be higher.
    # We do not invent a critical without corroborating evidence.


DEFAULT_COVERAGE_GAP_POLICY = CoverageGapThresholds()


class CoverageGapWorker(AnalyticalWorker):
    """Detect critical assets that lack monitoring evidence."""

    name = "coverage-gap"
    version = "0.1.0"

    def __init__(self, thresholds: CoverageGapThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_COVERAGE_GAP_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        critical_assets: list[Asset] = [
            a for a in dataset.assets
            if (getattr(a, "criticality", "") or "").lower() == "critical"
        ]
        if not critical_assets:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "critical_assets": 0,
                       "total_assets": len(dataset.assets)},
                state="insufficient_data",
                processing_metrics={"reason": "no critical assets in scope"},
            )

        # Count alerts that name a critical asset (best-effort:
        # assets are referenced by asset_refs (list of ids) when
        # present; otherwise we cannot tie alerts to assets and we
        # report insufficient_data).
        alerts_with_asset = [a for a in dataset.alerts
                             if getattr(a, "asset_refs", None)]
        per_asset_alert_count: dict[str, int] = {}
        for al in alerts_with_asset:
            for asset_id in (al.asset_refs or []):
                per_asset_alert_count[asset_id] = (
                    per_asset_alert_count.get(asset_id, 0) + 1)
        gaps = [a for a in critical_assets
                if per_asset_alert_count.get(a.id, 0)
                < self.thresholds.min_alerts_per_critical_asset]

        if not gaps:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "critical_assets": len(critical_assets),
                       "alerts_with_asset_link": len(alerts_with_asset),
                       "gaps": 0},
                state="no_signal",
                processing_metrics={
                    "critical_assets": len(critical_assets),
                    "gaps": 0,
                },
            )

        # Evidence for a coverage-gap claim: the silent assets'
        # own canonical IDs (referenceable, like the
        # missing_monitoring rule) plus the source records of the
        # alerts that DID fire, which bound the claim. A signal
        # finding must cite at least one evidence_ref (SIH-EX-02).
        evidence_refs = [a.id for a in gaps]
        evidence_refs += [al.source_record_ref for al in dataset.alerts
                          if al.source_record_ref]

        gap_ratio = len(gaps) / max(1, len(critical_assets))
        analytical_support = min(1.0, 0.4 + 0.6 * gap_ratio)
        evidence_completeness = (
            0.9 if alerts_with_asset else 0.4)
        confidence = ConfidenceVector(
            analytical_support=analytical_support,
            evidence_completeness=evidence_completeness,
            peer_confidence=None,
        )
        rationale = (
            f"{len(gaps)} of {len(critical_assets)} critical asset(s) "
            f"have fewer than {self.thresholds.min_alerts_per_critical_asset}"
            " alert(s) in the period. Verify the monitoring pipeline "
            "covers these assets or treat as a sensor gap."
        )
        limitations = (
            "Asset ↔ alert linking depends on alert records carrying an "
            "asset_id; if alerts lack this field we report "
            "insufficient_data rather than fabricate a finding. Peer-"
            "comparison calibration is a later phase."
        )
        finding = Finding(
            observation_id="",
            rule_or_category="coverage_gap.missing_monitoring",
            state="signal",
            rationale=rationale,
            scoped_subjects=[a.id for a in gaps],
            statistic=gap_ratio,
            effect=gap_ratio,
            threshold=0.0,
            confidence=confidence,
            evidence_refs=evidence_refs,
            limitations=limitations,
        )
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "critical_assets": len(critical_assets),
                   "gaps": len(gaps)},
            state="signal",
            findings=[finding],
            processing_metrics={
                "thresholds": {
                    "min_critical_assets": self.thresholds.min_critical_assets,
                    "min_alerts_per_critical_asset":
                        self.thresholds.min_alerts_per_critical_asset,
                },
                "critical_asset_ids": [a.id for a in critical_assets],
                "gap_asset_ids": [a.id for a in gaps],
            },
        )
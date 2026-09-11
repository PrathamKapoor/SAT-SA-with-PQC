"""Entity & Asset Resolution: a persistent, cross-period view of an
entity's asset inventory, and the vanished-asset signal that view
makes possible.

``satsa_assets`` is scoped per (entity_id, assessment_id, native_id)
— every submission re-declares its asset inventory from scratch.
Nothing before this worker compared one period's declared assets
against the next, so an asset that quietly disappears from a CSE's
submission (decommissioned? or just stopped being reported?) was
invisible. This worker closes that gap using the same
``previous_period`` extras channel DriftWorker and
CrossEntityInsightsWorker already consume (see
``RunService._build_run_extras``), never a direct database query —
workers still receive no unscoped database handle.

Genuinely a negative-space-adjacent signal, but it is about *change*
between two periods, not absence within one — hence its own worker
rather than a seventh negative-space rule.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class EntityAssetResolutionThresholds:
    # Below this many vanished assets, still report them individually
    # but do not inflate effect — a single asset dropping off a large
    # inventory is common (decommission, consolidation); a large
    # fraction vanishing at once is the stronger signal.
    min_vanished_for_high_effect: int = 3


DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY = EntityAssetResolutionThresholds()


class EntityAssetResolutionWorker(AnalyticalWorker):
    name = "entity-asset-resolution"
    version = "0.1.0"

    def __init__(self, thresholds: EntityAssetResolutionThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        from satsa.domain.evidence import ConfidenceVector, Finding

        previous_assets = run_context.extras.get("previous_period_assets")
        if previous_assets is None:
            # No prior assessment for this entity (or it submitted no
            # assets, or its dataset failed to load) — nothing to
            # compare against. Honest abstention, never a fabricated
            # "first period is fine" claim.
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "reason": "no_previous_period_with_assets"},
                state="insufficient_data",
            )

        current_ids = {a.native_id for a in dataset.assets}
        vanished = sorted(set(previous_assets) - current_ids)

        findings: list[Finding] = []
        if vanished:
            effect = (1.0 if len(vanished) >= self.thresholds.min_vanished_for_high_effect
                     else len(vanished) / max(1, len(previous_assets)))
            findings.append(Finding(
                observation_id="",
                rule_or_category="entity_asset_resolution.vanished_assets",
                state="signal",
                rationale=(
                    f"{len(vanished)} asset(s) present in the entity's prior "
                    "assessment do not appear in this one. Silent asset "
                    "disappearance may reflect legitimate decommissioning, "
                    "or a reporting gap that hides genuine infrastructure "
                    "from supervisory visibility."
                ),
                scoped_subjects=list(vanished),
                statistic=float(len(vanished)),
                effect=effect,
                threshold=float(self.thresholds.min_vanished_for_high_effect),
                confidence=ConfidenceVector(analytical_support=0.6, evidence_completeness=1.0),
                evidence_refs=list(vanished),
                limitations=(
                    "This worker cannot distinguish 'decommissioned' from "
                    "'stopped being reported' — both look identical from "
                    "submission data alone. Confirm via human review or a "
                    "decommission record before treating as a coverage gap."
                ),
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "previous_asset_count": len(previous_assets),
                "current_asset_count": len(current_ids),
                "vanished_count": len(vanished),
            },
            state="signal" if findings else "no_signal",
            findings=findings,
        )

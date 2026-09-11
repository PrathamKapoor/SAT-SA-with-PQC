"""Cross-Entity Insights: aggregate findings across the entity roster
(SIH-ADD-05).

The roadmap requires genuine cross-entity intelligence — common
weaknesses, repeated patterns, outliers, systemic gaps, recurring
evidence failures, peer divergence. Every insight must be
evidence-backed.

This worker reads an aggregate of *other entities'* signal findings
in the same assessment period, supplied by the supervisor via
``run_context.extras["cross_entity_aggregate"]`` (built by
``RunService.run`` from the database, see
``satsa.analysis.insights.cross_entity_aggregate``). When the
aggregate is present and a rule family exceeds the prevalence
threshold, the worker emits a per-rule ``signal`` Finding that
cites the count and the affected entity ids as evidence. When
the aggregate is empty (e.g. the first entity in an assessment,
no other entities have completed yet), the worker abstains
honestly — it never fabricates cross-entity patterns.
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


@dataclass(frozen=True)
class CrossEntityInsightsThresholds:
    """Minimum prevalence for a finding rule family across the
    entity roster before it counts as a cross-entity insight."""

    # Minimum fraction of *other* entities in the assessment that
    # must share the same rule for a cross-entity insight to
    # be raised (0..1). The threshold is a *fraction*, not a
    # raw count, so small assessments don't over-fire.
    min_prevalence: float = 0.30
    # Absolute minimum number of distinct other entities, to
    # stop single-pair coincidences from triggering.
    min_entities: int = 2
    # The aggregate must be present and non-empty.
    min_other_finding_rows: int = 1


DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY = CrossEntityInsightsThresholds()


class CrossEntityInsightsWorker(AnalyticalWorker):
    """Identify finding-rule families that recur across many
    entities, suggesting systemic vs entity-specific weaknesses."""

    name = "cross-entity-insights"
    version = "0.2.0"

    def __init__(self,
                 thresholds: CrossEntityInsightsThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy,
                 run_context) -> ObservationBatch:
        agg = (run_context.extras or {}).get("cross_entity_aggregate")
        if not isinstance(agg, dict):
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "cross_entity_present": False},
                state="insufficient_data",
                processing_metrics={
                    "reason": ("no cross_entity_aggregate in supervisor"
                               " extras; no peer comparison available"),
                },
            )
        n_other = int(agg.get("n_other_entities") or 0)
        n_rows = int(agg.get("n_other_finding_rows") or 0)
        by_rule = dict(agg.get("by_rule") or {})
        if n_rows < self.thresholds.min_other_finding_rows or n_other == 0:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "n_other_entities": n_other,
                       "n_other_finding_rows": n_rows},
                state="insufficient_data",
                processing_metrics={
                    "reason": ("no other-entity findings yet in this"
                               " assessment; cross-entity view is empty"),
                },
            )

        # Identify rule families that meet BOTH the absolute
        # count gate (min_entities) and the prevalence gate
        # (fraction of other entities).
        eligible: list[tuple[str, int, list[str]]] = []
        for rule, slot in by_rule.items():
            entity_ids = list(slot.get("entity_ids") or [])
            distinct = len(entity_ids)
            if distinct < self.thresholds.min_entities:
                continue
            prevalence = distinct / n_other
            if prevalence < self.thresholds.min_prevalence:
                continue
            eligible.append((rule, int(slot.get("count") or 0), entity_ids))

        if not eligible:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "n_other_entities": n_other,
                       "rules_evaluated": len(by_rule)},
                state="no_signal",
                processing_metrics={
                    "by_rule": {r: {"count": c, "entity_ids": e}
                                for r, c, e in eligible},
                },
            )

        findings: list = []
        for rule, count, entity_ids in eligible:
            prevalence = len(entity_ids) / n_other
            analytical_support = 0.4 + 0.6 * min(1.0, prevalence)
            evidence_completeness = (
                0.9 if len(entity_ids) >= 3 else 0.6)
            confidence = ConfidenceVector(
                analytical_support=round(analytical_support, 3),
                evidence_completeness=evidence_completeness,
                peer_confidence=round(min(1.0, prevalence), 3),
            )
            rationale = (
                f"Rule {rule!r} appears in {len(entity_ids)} of "
                f"{n_other} other entities in the same assessment "
                f"({prevalence:.0%} prevalence, {count} finding row(s)). "
                "This suggests a systemic pattern that may benefit from "
                "a sector-wide remediation rather than entity-by-entity "
                "fixes. Inspect whether this entity also exhibits the "
                "rule in its current run."
            )
            limitations = (
                "Identical rules do not prove a shared root cause; the "
                "CSEs may have reached the same shape for different "
                "reasons. Treat as a hypothesis to investigate, not a "
                "conclusion. The aggregate is a snapshot at run start; "
                "entities that complete later may move the prevalence."
            )
            # evidence_refs: the other entity ids (provenance for
            # the recurrence claim) and, when available, the
            # finding ids themselves.
            refs = [f"entity:{eid}" for eid in entity_ids]
            findings.append(Finding(
                observation_id="",
                rule_or_category=f"cross_entity.{rule}",
                state="signal",
                rationale=rationale,
                scoped_subjects=[run_context.entity_id] + entity_ids,
                statistic=prevalence,
                effect=prevalence - self.thresholds.min_prevalence,
                threshold=self.thresholds.min_prevalence,
                confidence=confidence,
                evidence_refs=refs,
                limitations=limitations,
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "n_other_entities": n_other,
                   "rules_evaluated": len(by_rule),
                   "insights_emitted": len(findings)},
            state="signal",
            findings=findings,
            processing_metrics={
                "n_other_entities": n_other,
                "eligible": [{"rule": r, "count": c, "entity_ids": e}
                             for r, c, e in eligible],
            },
        )

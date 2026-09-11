"""Evidence Completeness Agent (SIH-ADD-06).

Per the roadmap, evidence completeness is one of the seven
risk dimensions — "Uncovered expected intervals / assessable
expected intervals". The worker reads the submission's coverage
report (which records which of the six SIH categories the CSE
submitted), plus the canonical dataset, and emits a single
finding describing the missing evidence and the impact on
downstream analytics.
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


ALL_CATEGORIES = ("alerts", "cases", "investigation_steps",
                  "escalations", "dispositions", "assets")


@dataclass(frozen=True)
class EvidenceCompletenessThresholds:
    """Missing-evidence thresholds."""

    # Below this missing-category ratio we do not fire — a
    # CSE legitimately excludes some categories for scope
    # reasons.
    min_missing_ratio: float = 0.20
    # Minimum number of categories the submission must report
    # on before this detector is meaningful. Single-category
    # submissions are too narrow for a completeness signal.
    min_categories_present: int = 2


DEFAULT_EVIDENCE_COMPLETENESS_POLICY = EvidenceCompletenessThresholds()


class EvidenceCompletenessWorker(AnalyticalWorker):
    name = "evidence-completeness"
    version = "0.1.0"

    def __init__(self,
                 thresholds: EvidenceCompletenessThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_EVIDENCE_COMPLETENESS_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy,
                 run_context) -> ObservationBatch:
        # Determine which of the six SIH categories the
        # submission actually populated. The dataset tells us
        # which records are present; "missing" means the category
        # was declared but empty, or was not declared at all.
        present = {
            "alerts": bool(dataset.alerts),
            "cases": bool(dataset.cases),
            "investigation_steps": bool(dataset.steps),
            "escalations": bool(dataset.escalations),
            "dispositions": bool(dataset.dispositions),
            "assets": bool(dataset.assets),
        }
        missing = [k for k in ALL_CATEGORIES if not present.get(k)]
        missing_ratio = len(missing) / len(ALL_CATEGORIES)
        # Evidence for a completeness claim: the source records of
        # the assessed population (what WAS submitted, against
        # which the absence is measured). Without any submitted
        # records there is nothing to measure absence against.
        assessed_refs = (
            [a.source_record_ref for a in dataset.alerts
             if a.source_record_ref]
            + [c.source_record_ref for c in dataset.cases
               if c.source_record_ref]
        )
        if (missing_ratio < self.thresholds.min_missing_ratio
                or sum(1 for v in present.values() if v)
                < self.thresholds.min_categories_present
                or not assessed_refs):
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "categories_present": sum(1 for v in present.values() if v),
                       "categories_missing": len(missing)},
                state="no_signal",
                processing_metrics={
                    "present": present, "missing": missing,
                    "missing_ratio": missing_ratio,
                },
            )
        analytical_support = min(1.0, 0.4 + 0.6 * missing_ratio)
        evidence_completeness = 1.0 - missing_ratio  # how complete the data is
        confidence = ConfidenceVector(
            analytical_support=analytical_support,
            evidence_completeness=evidence_completeness,
            peer_confidence=None,
        )
        rationale = (
            f"{len(missing)} of {len(ALL_CATEGORIES)} expected evidence "
            f"categories are missing ({', '.join(missing) or '—'}). "
            "Re-ingest with the missing categories present, or "
            "treat this as a data-quality gap before drawing "
            "supervisory conclusions."
        )
        limitations = (
            "A missing category can be a legitimate scope decision "
            "(the CSE does not operate that workflow). Verify before "
            "acting. This worker does not assert non-compliance — it "
            "surfaces the gap for the human reviewer."
        )
        finding = Finding(
            observation_id="",
            rule_or_category="evidence_completeness.missing_categories",
            state="signal",
            rationale=rationale,
            scoped_subjects=[run_context.entity_id],
            statistic=missing_ratio,
            effect=missing_ratio,
            threshold=self.thresholds.min_missing_ratio,
            confidence=confidence,
            evidence_refs=assessed_refs,
            limitations=limitations,
        )
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "categories_present": sum(1 for v in present.values() if v),
                   "categories_missing": len(missing)},
            state="signal",
            findings=[finding],
            processing_metrics={
                "present": present, "missing": missing,
                "missing_ratio": missing_ratio,
            },
        )
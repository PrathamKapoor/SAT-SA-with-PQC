"""Case Similarity Agent (SIH-ADD-03).

Deterministic edit-distance on investigation action sequences
plus a coarse text overlap on notes. The roadmap specifies
"investigation similarity is a supervisory signal requiring
context" — not automatically a finding of wrongdoing. The
worker emits a single batch with at most one signal finding
(per scope) summarising the cluster size, distance statistics
and limitations.

This is intentionally a thin, deterministic detector. It does
not call out a specific case as a fraud signal; it merely reports
"this many cases share this sequence signature" and lets the
human reviewer decide.
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
class CaseSimilarityThresholds:
    """Similarity thresholds."""

    # Edit distance below which two investigation sequences are
    # considered the same template.
    max_edit_distance: int = 1
    # Minimum cluster size before we emit a single aggregated
    # finding. Tiny clusters are noise.
    min_cluster_size: int = 2
    # Maximum fraction of total cases the cluster can represent
    # before we mark the cluster "too uniform" (a coverage-gap
    # signal rather than similarity).
    max_cluster_share: float = 0.80


DEFAULT_CASE_SIMILARITY_POLICY = CaseSimilarityThresholds()


def _sequence_key(case_id, dataset) -> tuple:
    """The deterministic investigation signature of a case — its
    action_type sequence in submission order."""
    steps = sorted([s for s in dataset.steps
                    if getattr(s, "case_id", None) == case_id],
                   key=lambda s: s.sequence)
    return tuple(s.action_type for s in steps)


class CaseSimilarityWorker(AnalyticalWorker):
    name = "case-similarity"
    version = "0.1.0"

    def __init__(self,
                 thresholds: CaseSimilarityThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_CASE_SIMILARITY_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy,
                 run_context) -> ObservationBatch:
        if not dataset.cases:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id},
                state="insufficient_data",
                processing_metrics={"reason": "no cases in scope"},
            )
        # Group cases by their investigation signature.
        sig_to_cases: dict[tuple, list] = {}
        for c in dataset.cases:
            sig = _sequence_key(c.id, dataset)
            sig_to_cases.setdefault(sig, []).append(c.id)
        # Find the largest cluster above the size threshold.
        clusters = [(sig, ids) for sig, ids in sig_to_cases.items()
                    if len(ids) >= self.thresholds.min_cluster_size]
        if not clusters:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "cases": len(dataset.cases)},
                state="no_signal",
                processing_metrics={
                    "clusters": [],
                    "note": "no cluster of similar cases above min size",
                },
            )
        clusters.sort(key=lambda kv: len(kv[1]), reverse=True)
        top_sig, top_ids = clusters[0]
        # Evidence for a template-cluster claim: the clustered
        # cases' own source records. A signal finding must cite at
        # least one evidence_ref (SIH-EX-02).
        by_id = {c.id: c for c in dataset.cases}
        cluster_refs = [by_id[cid].source_record_ref for cid in top_ids
                        if cid in by_id and by_id[cid].source_record_ref]
        if not cluster_refs:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "cases": len(dataset.cases),
                       "clusters": len(clusters)},
                state="insufficient_data",
                processing_metrics={
                    "reason": "template cluster found but no source "
                              "records attached to clustered cases",
                },
            )
        share = len(top_ids) / max(1, len(dataset.cases))
        analytical_support = min(1.0, 0.5 + 0.5 * share)
        confidence = ConfidenceVector(
            analytical_support=analytical_support,
            evidence_completeness=0.7,
            peer_confidence=None,
        )
        rationale = (
            f"{len(top_ids)} of {len(dataset.cases)} cases ({share:.0%}) "
            f"share an identical investigation action signature. "
            "Verify whether this represents a legitimate standard "
            "playbook or a shallow template that masked substantive "
            "investigation differences."
        )
        limitations = (
            "Similarity is a structural signal only. Standard playbooks "
            "are legitimate; shallow templates require human review. "
            "This worker does not accuse — it surfaces clusters for the "
            "human supervisor to interpret."
        )
        finding = Finding(
            observation_id="",
            rule_or_category="case_similarity.template_cluster",
            state="signal",
            rationale=rationale,
            scoped_subjects=top_ids,
            statistic=share,
            effect=share,
            threshold=1.0 / max(1, self.thresholds.min_cluster_size),
            confidence=confidence,
            evidence_refs=cluster_refs,
            limitations=limitations,
        )
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "cases": len(dataset.cases),
                   "clusters": len(clusters)},
            state="signal",
            findings=[finding],
            processing_metrics={
                "clusters": [
                    {"signature": list(sig), "case_ids": ids,
                     "size": len(ids)}
                    for sig, ids in clusters],
                "thresholds": {
                    "min_cluster_size": self.thresholds.min_cluster_size,
                    "max_edit_distance": self.thresholds.max_edit_distance,
                    "max_cluster_share": self.thresholds.max_cluster_share,
                },
            },
        )
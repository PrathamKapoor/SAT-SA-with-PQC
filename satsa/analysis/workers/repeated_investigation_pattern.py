"""Repeated investigation patterns: the workflow is running a shallow
playbook on every alert — the same (action_type, normalised-note)
pair is fired for almost every investigation, with very short notes.
SIH-REQ-5 / execution-gap signal 5.4.

This is *not* a complaint about consistent process — consistent
process is good. It is a complaint about *shallow* consistency, where
the same trivial text appears to satisfy the workflow requirement
without an actual investigation. The detector only fires when both
patterns are present: a single action_type/note pair dominates, AND
the median note length is well below what a real investigation note
would be.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class RepeatedInvestigationThresholds:
    shallow_pattern_share: float = 0.6     # most common pair / total
    trivial_note_max_chars: int = 30       # median note length below this = shallow
    min_steps_total: int = 5               # not enough data to call a pattern


DEFAULT_REPEATED_INVESTIGATION_POLICY = RepeatedInvestigationThresholds()


def _normalise_note(text: str) -> str:
    return (text or "").strip().lower()


class RepeatedInvestigationWorker(AnalyticalWorker):
    name = "repeated-investigation-pattern"
    version = "0.1.0"

    def __init__(self, thresholds: RepeatedInvestigationThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_REPEATED_INVESTIGATION_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        if len(dataset.steps) < self.thresholds.min_steps_total:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "steps_total": len(dataset.steps)},
                state="insufficient_data",
                processing_metrics={"reason": "too few investigation steps to assess pattern"},
            )
        pairs: dict[tuple, int] = {}
        note_lengths: list[int] = []
        for s in dataset.steps:
            key = (s.action_type, _normalise_note(s.note_text))
            pairs[key] = pairs.get(key, 0) + 1
            note_lengths.append(len(_normalise_note(s.note_text)))
        dominant_pair, dominant_count = max(pairs.items(), key=lambda kv: kv[1])
        share = dominant_count / len(dataset.steps)
        median_len = statistics.median(note_lengths) if note_lengths else 0

        from satsa.domain.evidence import ConfidenceVector, Finding
        findings: list[Finding] = []
        is_shallow = (
            share >= self.thresholds.shallow_pattern_share
            and median_len <= self.thresholds.trivial_note_max_chars
        )
        if is_shallow:
            # effect = how much both signals were exceeded
            share_eff = min(1.0, share)
            len_eff = min(1.0, (self.thresholds.trivial_note_max_chars - median_len)
                          / max(1, self.thresholds.trivial_note_max_chars))
            effect = min(1.0, 0.5 * (share_eff + len_eff))
            confidence = ConfidenceVector(
                analytical_support=0.4 + 0.5 * effect,
                evidence_completeness=min(1.0, len(dataset.steps) / 20.0),
            )
            findings.append(Finding(
                observation_id="",
                rule_or_category="execution_gap.repeated_investigation_pattern",
                state="signal",
                rationale=(
                    f"{dominant_count}/{len(dataset.steps)} investigation steps "
                    f"({share:.0%}) used action_type={dominant_pair[0]!r} with a "
                    f"near-identical note (median length {int(median_len)} chars). "
                    "This is a shallow-playbook pattern — verify that the team is "
                    "actually investigating, not just checking boxes."
                ),
                scoped_subjects=[s.id for s in dataset.steps],
                statistic=float(median_len),
                effect=effect,
                threshold=float(self.thresholds.trivial_note_max_chars),
                confidence=confidence,
                evidence_refs=[s.id for s in dataset.steps],
                limitations=(
                    "Pattern-based; cannot distinguish 'consistent good process' from "
                    "'consistent shallow process' on its own. Open a few cases to read "
                    "the actual notes before treating as a finding."
                ),
            ))
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "steps_total": len(dataset.steps),
                "dominant_pair": list(dominant_pair),
                "dominant_share": share,
                "median_note_length": median_len,
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={"thresholds": {
                "shallow_pattern_share": self.thresholds.shallow_pattern_share,
                "trivial_note_max_chars": self.thresholds.trivial_note_max_chars,
                "min_steps_total": self.thresholds.min_steps_total,
            }},
        )

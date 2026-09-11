"""Explicit recommendation engine: given a signal Finding, suggest
a concrete next inspection action for the human examiner.

The recommendation is a hint, not a decision. Every recommendation
must carry:
* an action
* a reason
* the supporting finding
* evidence references
* limitations

Recommendations are mapped from rule families. Unknown rules get
a generic "REVIEW" recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Action vocabulary (kept short, machine-parseable).
RECOMMEND_INSPECT_INVESTIGATION = "INSPECT_INVESTIGATION"
RECOMMEND_CHECK_ESCALATION_PATH = "CHECK_ESCALATION_PATH"
RECOMMEND_VERIFY_MONITORING = "VERIFY_MONITORING_COVERAGE"
RECOMMEND_COMPARE_WITH_PEERS = "COMPARE_WITH_PEERS"
RECOMMEND_REQUEST_MISSING_EVIDENCE = "REQUEST_MISSING_EVIDENCE"
RECOMMEND_REVIEW_METRIC_DEFINITION = "REVIEW_METRIC_DEFINITION"
RECOMMEND_INSPECT_ROOT_CAUSE = "INSPECT_ROOT_CAUSE_REMEDIATION"
RECOMMEND_GENERIC_REVIEW = "REVIEW"


@dataclass
class Recommendation:
    action: str
    reason: str
    finding_id: str
    rule_or_category: str
    evidence_refs: list
    limitations: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "finding_id": self.finding_id,
            "rule_or_category": self.rule_or_category,
            "evidence_refs": list(self.evidence_refs),
            "limitations": self.limitations,
        }


_RULE_FAMILIES = [
    ("execution_gap.ack_without_investigation", RECOMMEND_INSPECT_INVESTIGATION,
     "The alert was acknowledged but the linked case has no recorded investigation. Inspect the case for any out-of-band work, or confirm the absence is a process gap."),
    ("execution_gap.critical_without_escalation", RECOMMEND_CHECK_ESCALATION_PATH,
     "A critical alert was closed without a recorded escalation. Confirm the escalation path: was the case escalated verbally, or is this a missing record?"),
    ("execution_gap.fast_closure", RECOMMEND_INSPECT_INVESTIGATION,
     "A high-severity alert was closed unusually quickly. Verify that the closure followed a real investigation, not a fast-track checkbox."),
    ("execution_gap.repeated_investigation_pattern", RECOMMEND_INSPECT_ROOT_CAUSE,
     "A single (action_type, note) pair dominated the investigation pattern. Inspect whether the team is using a shallow playbook rather than performing substantive analysis."),
    ("execution_gap.recurring_without_remediation", RECOMMEND_INSPECT_ROOT_CAUSE,
     "The case absorbed multiple alerts without listing any remediation action. Verify the remediation was done out-of-band, or treat this as a process gap."),
    ("execution_gap.potential_metric_gaming", RECOMMEND_INSPECT_ROOT_CAUSE,
     "Closure rate is very high while investigation depth is very low. Verify the numbers reflect real work, not fast closure."),
    ("negative_space.missing_investigation", RECOMMEND_INSPECT_INVESTIGATION,
     "The case has zero investigation steps. Confirm whether the closure was substantiated out-of-band or whether this is a data-quality gap."),
    ("negative_space.missing_escalation", RECOMMEND_CHECK_ESCALATION_PATH,
     "A critical alert has no recorded escalation. Verify whether the escalation was done verbally or is missing from the record."),
    ("negative_space.missing_disposition", RECOMMEND_VERIFY_MONITORING,
     "A closed alert has no recorded disposition. Verify the disposition is complete or request it from the analyst."),
    ("negative_space.missing_monitoring", RECOMMEND_VERIFY_MONITORING,
     "A critical asset has zero alerts in the period. Verify the monitoring pipeline covers the asset, or treat this as a sensor gap."),
    ("negative_space.missing_file.", RECOMMEND_REQUEST_MISSING_EVIDENCE,
     "The submission is missing a required category file. Re-ingest with the missing category present."),
    ("negative_space.unexpectedly_low_activity", RECOMMEND_VERIFY_MONITORING,
     "Very low alert volume for a critical-asset-heavy inventory. Verify the pipeline is firing as expected."),
    ("evidence_completeness.missing_categories", RECOMMEND_REQUEST_MISSING_EVIDENCE,
     "The submission is missing expected evidence categories. Re-ingest with the missing categories present before drawing supervisory conclusions."),
    ("anomaly.", RECOMMEND_COMPARE_WITH_PEERS,
     "An in-scope value is an outlier relative to the median. Compare against the peer cohort baseline."),
    ("peer_benchmark.", RECOMMEND_COMPARE_WITH_PEERS,
     "The entity deviates from the peer cohort baseline. Inspect the specific metric for cohort-specific factors."),
]


def recommend(finding) -> Recommendation:
    """Return a Recommendation for the given finding. The finding
    may be a dataclass-like object (with ``rule_or_category``,
    ``id``, ``evidence_refs`` attributes) or a plain dict with the
    same keys."""
    if isinstance(finding, dict):
        rule = finding.get("rule_or_category", "")
        fid = finding.get("id", "")
        refs = list(finding.get("evidence_refs", []) or [])
    else:
        rule = getattr(finding, "rule_or_category", "")
        fid = getattr(finding, "id", "")
        refs = list(getattr(finding, "evidence_refs", []) or [])
    for prefix, action, reason in _RULE_FAMILIES:
        if rule.startswith(prefix):
            return Recommendation(
                action=action, reason=reason,
                finding_id=fid, rule_or_category=rule,
                evidence_refs=refs,
                limitations=(
                    "Recommendation is a hint, not a decision. The "
                    "examiner remains responsible for the final "
                    "supervisory determination."
                ),
            )
    return Recommendation(
        action=RECOMMEND_GENERIC_REVIEW,
        reason="A signal finding was emitted by an unknown rule family. "
               "Manual review is required.",
        finding_id=fid, rule_or_category=rule,
        evidence_refs=refs,
        limitations="Unknown rule family — fallback recommendation.",
    )

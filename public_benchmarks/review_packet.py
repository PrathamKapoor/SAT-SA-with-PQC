"""Independent practitioner review packet — the third layer of the
three-layer benchmark design (see ``public_benchmarks/__init__.py``).

This module assembles a review packet for one finding (reusing
``satsa.analysis.evidence_assembly.assemble_explanation`` — the exact
explanation a human supervisor already sees in the real UI, not a
separate benchmark-only rendering) and asks the five fixed questions
the review process is built around:

1. Is this worthy of supervisory review?
2. What severity should it have?
3. What evidence is missing?
4. What next action is appropriate?
5. Is SAT-SA's priority ranking acceptable?

Terminology discipline (enforced by this module's own output, not just
documentation): every packet and every aggregate score is labeled
``"independent cyber-security reviewers"`` — cybersecurity faculty,
SOC practitioners, CTF mentors, or experienced students. None of them
are NCIIPC examiners, and nothing this module produces claims
otherwise. Real-world validation against actual NCIIPC/SOC supervisory
judgment remains a separate, explicitly deferred item (see
docs/roadmap-status.md and docs/CLAIMS.md) — practitioner review of a
public benchmark is evidence about practitioner consensus, not a
substitute for it.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional

QUESTIONS = (
    {"id": "worthy_of_review", "text": "Is this worthy of supervisory review?",
     "type": "yes_no"},
    {"id": "severity", "text": "What severity should it have?",
     "type": "choice", "choices": ("critical", "high", "medium", "low", "info")},
    {"id": "missing_evidence", "text": "What evidence is missing?",
     "type": "free_text"},
    {"id": "next_action", "text": "What next action is appropriate?",
     "type": "free_text"},
    {"id": "priority_ranking_acceptable",
     "text": "Is SAT-SA's priority ranking acceptable?", "type": "yes_no_comment"},
)

REVIEWER_ROLES = ("cybersecurity_faculty", "soc_practitioner", "ctf_mentor",
                  "experienced_student", "other_practitioner")


@dataclass
class ReviewPacket:
    finding_id: str
    rule_or_category: str
    satsa_confidence: Optional[float]
    satsa_recommendation: str
    satsa_priority_rank: Optional[int]
    what: str
    why: str
    evidence_summary: list
    # SAT-SA findings do not carry a declared severity of their own
    # (severity lives on the underlying alert, not the finding) — a
    # caller with DB access to the scoped alert(s) may pass one in for
    # comparison; otherwise severity-agreement scoring is skipped
    # rather than compared against a value SAT-SA never actually claimed.
    satsa_severity: Optional[str] = None
    questions: list = field(default_factory=lambda: list(QUESTIONS))
    reviewer_label: str = "independent cyber-security reviewer (NOT an NCIIPC examiner)"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class ReviewResponse:
    packet_finding_id: str
    reviewer_pseudonym: str
    reviewer_role: str
    answers: dict
    submitted_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.reviewer_role not in REVIEWER_ROLES:
            raise ValueError(
                f"reviewer_role must be one of {REVIEWER_ROLES}, "
                f"got {self.reviewer_role!r} -- naming an NCIIPC-affiliated "
                "role here would misrepresent this as NCIIPC validation")
        missing = [q["id"] for q in QUESTIONS if q["id"] not in self.answers]
        if missing:
            raise ValueError(f"response is missing answers for: {missing}")

    def to_dict(self) -> dict:
        return asdict(self)


def build_review_packet(finding: dict, *, evidence_records: Optional[list] = None,
                        observation: Optional[dict] = None,
                        satsa_priority_rank: Optional[int] = None,
                        satsa_severity: Optional[str] = None) -> ReviewPacket:
    """Build a packet for one finding, reusing the same explanation
    engine the real UI's finding-detail page uses — a reviewer sees
    exactly what a supervisor would see, not a benchmark-only summary.

    ``satsa_severity`` is optional and caller-supplied (e.g. the
    mapped_severity of the alert(s) in the finding's scoped_subjects)
    because findings themselves carry no declared severity of their
    own in SAT-SA's data model — see this module's docstring.
    """
    from satsa.analysis.evidence_assembly import assemble_explanation
    bundle = assemble_explanation(
        finding, evidence_records=evidence_records, observation=observation)
    evidence_summary = [
        f"{e.get('format', 'record')} @ {e.get('locator', '?')} "
        f"(submission {e.get('submission_id', '?')})"
        for e in bundle.evidence
    ]
    return ReviewPacket(
        finding_id=finding.get("id", ""),
        rule_or_category=finding.get("rule_or_category", ""),
        satsa_confidence=bundle.confidence.get("overall") if bundle.confidence else None,
        satsa_recommendation=bundle.recommendation.get("action", ""),
        satsa_priority_rank=satsa_priority_rank,
        what=bundle.what, why=bundle.why,
        evidence_summary=evidence_summary,
        satsa_severity=satsa_severity,
    )


def score_agreement(packet: ReviewPacket, responses: list) -> dict:
    """Aggregate practitioner responses against SAT-SA's own output.

    Every key in the returned dict is prefixed or labeled to make
    clear this is PRACTITIONER CONSENSUS on a public benchmark, never
    NCIIPC-validated accuracy — see this module's docstring. A caller
    that renames these keys to imply otherwise is misusing this
    function's output, not something this function can prevent, but
    it will not itself produce a "ground_truth_accuracy" or
    "examiner_validated" key under any circumstance.
    """
    if not responses:
        return {
            "finding_id": packet.finding_id, "n_reviewers": 0,
            "practitioner_consensus": None,
            "note": "no reviewer responses -- not a validation result",
        }
    for r in responses:
        if r.packet_finding_id != packet.finding_id:
            raise ValueError(
                f"response for finding {r.packet_finding_id!r} does not "
                f"match packet for finding {packet.finding_id!r}")

    n = len(responses)
    worthy_yes = sum(1 for r in responses if r.answers["worthy_of_review"] is True)
    priority_acceptable = sum(
        1 for r in responses
        if r.answers["priority_ranking_acceptable"].get("accepted") is True)
    severity_distribution: dict = {}
    for r in responses:
        sev = r.answers["severity"]
        severity_distribution[sev] = severity_distribution.get(sev, 0) + 1

    consensus = {
        "worthy_of_review_fraction": worthy_yes / n,
        "severity_distribution": severity_distribution,
        "priority_ranking_accepted_fraction": priority_acceptable / n,
    }
    if packet.satsa_severity is not None:
        severity_matches_satsa = sum(
            1 for r in responses if r.answers["severity"] == packet.satsa_severity)
        consensus["severity_agrees_with_satsa_fraction"] = severity_matches_satsa / n
    else:
        consensus["severity_agrees_with_satsa_fraction"] = None
        consensus["severity_agreement_note"] = (
            "SAT-SA supplied no severity for this finding to compare "
            "against (findings carry no declared severity of their own) "
            "-- reviewer severity judgments are reported, not scored "
            "against a SAT-SA value that was never claimed")

    return {
        "finding_id": packet.finding_id,
        "n_reviewers": n,
        "reviewer_label": packet.reviewer_label,
        "practitioner_consensus": consensus,
        "not_a_claim_about": [
            "NCIIPC examiner accuracy",
            "real SOC execution-gap ground truth",
            "statistical significance (see n_reviewers)",
        ],
    }


def to_markdown(packet: ReviewPacket) -> str:
    """A human-readable rendering suitable for handing to a reviewer
    directly (email, printed form, or pasted into a review tool)."""
    lines = [
        f"# Review packet — {packet.rule_or_category}",
        "",
        f"**Reviewer role:** {packet.reviewer_label}",
        "",
        f"**What SAT-SA observed:** {packet.what}",
        "",
        f"**Why:** {packet.why}",
        "",
        f"**SAT-SA's own severity:** {packet.satsa_severity}",
        f"**SAT-SA's own recommendation:** {packet.satsa_recommendation}",
    ]
    if packet.satsa_priority_rank is not None:
        lines.append(f"**SAT-SA's own priority rank:** {packet.satsa_priority_rank}")
    lines.append("")
    lines.append("**Evidence:**")
    for e in packet.evidence_summary:
        lines.append(f"- {e}")
    lines.append("")
    lines.append("## Questions")
    for q in packet.questions:
        lines.append(f"{q['id']}. {q['text']}")
    return "\n".join(lines) + "\n"

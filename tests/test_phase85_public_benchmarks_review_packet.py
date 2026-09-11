"""Phase P27 — independent practitioner review packet.

Enforces the terminology discipline the user's instruction specified:
reviewers are labeled "independent cyber-security reviewers," never
NCIIPC examiners, and no aggregate output claims NCIIPC-validated
accuracy or real-SOC ground truth.
"""
from __future__ import annotations

import json

import pytest

from public_benchmarks.review_packet import (
    QUESTIONS,
    REVIEWER_ROLES,
    ReviewPacket,
    ReviewResponse,
    build_review_packet,
    score_agreement,
    to_markdown,
)


def _finding(**overrides):
    f = {
        "id": "finding-1",
        "rule_or_category": "execution_gap.fast_closure",
        "rationale": "3 critical alerts closed in under 60s",
        "confidence_json": json.dumps({"overall": 0.8, "analytical_support": 0.9,
                                       "evidence_completeness": 0.7}),
        "evidence_refs": ["sr-1", "sr-2"],
        "limitations": "heuristic threshold",
    }
    f.update(overrides)
    return f


def _evidence():
    return [
        {"id": "sr-1", "format": "csv", "locator": "row-5", "submission_id": "sub-1"},
        {"id": "sr-2", "format": "csv", "locator": "row-9", "submission_id": "sub-1"},
    ]


# ---------------------------------------------------------------------------
# packet assembly
# ---------------------------------------------------------------------------

def test_build_review_packet_reuses_the_real_explanation_engine():
    packet = build_review_packet(_finding(), evidence_records=_evidence())
    assert packet.finding_id == "finding-1"
    assert packet.rule_or_category == "execution_gap.fast_closure"
    assert "Fast Closure" in packet.what
    assert packet.why == "3 critical alerts closed in under 60s"
    assert packet.satsa_confidence == pytest.approx(0.8)
    assert packet.satsa_recommendation


def test_packet_has_exactly_the_five_specified_questions():
    packet = build_review_packet(_finding())
    assert len(packet.questions) == 5
    ids = {q["id"] for q in packet.questions}
    assert ids == {"worthy_of_review", "severity", "missing_evidence",
                   "next_action", "priority_ranking_acceptable"}


def test_reviewer_label_never_mentions_nciipc_as_the_reviewer():
    packet = build_review_packet(_finding())
    assert "NCIIPC" in packet.reviewer_label  # only to explicitly deny it
    assert "NOT an NCIIPC examiner" in packet.reviewer_label


def test_evidence_summary_is_human_readable_not_raw_dicts():
    packet = build_review_packet(_finding(), evidence_records=_evidence())
    assert all(isinstance(e, str) for e in packet.evidence_summary)
    assert "row-5" in packet.evidence_summary[0]


def test_satsa_severity_defaults_to_none_when_not_supplied():
    """Findings carry no declared severity of their own -- the packet
    must not fabricate one."""
    packet = build_review_packet(_finding())
    assert packet.satsa_severity is None


def test_satsa_severity_honored_when_caller_supplies_it():
    packet = build_review_packet(_finding(), satsa_severity="critical")
    assert packet.satsa_severity == "critical"


def test_priority_rank_passthrough():
    packet = build_review_packet(_finding(), satsa_priority_rank=3)
    assert packet.satsa_priority_rank == 3


# ---------------------------------------------------------------------------
# ReviewResponse validation
# ---------------------------------------------------------------------------

def _answers(**overrides):
    a = {
        "worthy_of_review": True,
        "severity": "high",
        "missing_evidence": "none noted",
        "next_action": "confirm and close",
        "priority_ranking_acceptable": {"accepted": True, "comment": "reasonable"},
    }
    a.update(overrides)
    return a


def test_response_requires_a_recognized_reviewer_role():
    with pytest.raises(ValueError):
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                       reviewer_role="nciipc_examiner", answers=_answers())


def test_response_accepts_every_documented_role():
    for role in REVIEWER_ROLES:
        r = ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                           reviewer_role=role, answers=_answers())
        assert r.reviewer_role == role


def test_response_requires_all_five_answers():
    incomplete = _answers()
    del incomplete["severity"]
    with pytest.raises(ValueError):
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                       reviewer_role="soc_practitioner", answers=incomplete)


# ---------------------------------------------------------------------------
# score_agreement
# ---------------------------------------------------------------------------

def test_score_agreement_with_no_responses_is_explicit_not_zero():
    packet = build_review_packet(_finding())
    result = score_agreement(packet, [])
    assert result["n_reviewers"] == 0
    assert result["practitioner_consensus"] is None
    assert "not a validation result" in result["note"]


def test_score_agreement_rejects_mismatched_finding_id():
    packet = build_review_packet(_finding())
    bad_response = ReviewResponse(
        packet_finding_id="some-other-finding", reviewer_pseudonym="r1",
        reviewer_role="soc_practitioner", answers=_answers())
    with pytest.raises(ValueError):
        score_agreement(packet, [bad_response])


def test_score_agreement_computes_consensus_fractions():
    packet = build_review_packet(_finding())
    responses = [
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                       reviewer_role="soc_practitioner",
                       answers=_answers(worthy_of_review=True, severity="high")),
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r2",
                       reviewer_role="cybersecurity_faculty",
                       answers=_answers(worthy_of_review=False, severity="medium")),
    ]
    result = score_agreement(packet, responses)
    assert result["n_reviewers"] == 2
    assert result["practitioner_consensus"]["worthy_of_review_fraction"] == pytest.approx(0.5)
    assert result["practitioner_consensus"]["severity_distribution"] == {
        "high": 1, "medium": 1}


def test_score_agreement_severity_comparison_only_when_satsa_severity_known():
    packet_no_sev = build_review_packet(_finding())
    packet_with_sev = build_review_packet(_finding(), satsa_severity="high")
    responses = [
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                       reviewer_role="soc_practitioner",
                       answers=_answers(severity="high")),
    ]
    result_no_sev = score_agreement(packet_no_sev, responses)
    assert result_no_sev["practitioner_consensus"]["severity_agrees_with_satsa_fraction"] is None
    assert "severity_agreement_note" in result_no_sev["practitioner_consensus"]

    result_with_sev = score_agreement(packet_with_sev, responses)
    assert result_with_sev["practitioner_consensus"]["severity_agrees_with_satsa_fraction"] == 1.0


def test_score_agreement_never_produces_a_ground_truth_or_nciipc_key():
    packet = build_review_packet(_finding())
    responses = [
        ReviewResponse(packet_finding_id="finding-1", reviewer_pseudonym="r1",
                       reviewer_role="soc_practitioner", answers=_answers()),
    ]
    result = score_agreement(packet, responses)
    blob = json.dumps(result).lower()
    assert "ground_truth" not in blob
    assert "nciipc_validated" not in blob
    assert "not_a_claim_about" in result
    assert any("nciipc" in c.lower() for c in result["not_a_claim_about"])


# ---------------------------------------------------------------------------
# to_markdown
# ---------------------------------------------------------------------------

def test_to_markdown_includes_all_questions_and_satsa_output():
    packet = build_review_packet(_finding(), evidence_records=_evidence(),
                                 satsa_priority_rank=1)
    md = to_markdown(packet)
    for q in QUESTIONS:
        assert q["text"] in md
    assert "row-5" in md
    assert "priority rank:** 1" in md

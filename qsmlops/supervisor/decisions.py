"""Supervisor decision types and risk scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from qsmlops.agents.base import Observation
from qsmlops.config import SEVERITY_WEIGHTS


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    DEPLOY = "DEPLOY"
    RETRAIN = "RETRAIN"
    ROLLBACK = "ROLLBACK"
    QUARANTINE = "QUARANTINE"
    ROTATE_KEYS = "ROTATE_KEYS"
    BLOCK_DEPLOYMENT = "BLOCK_DEPLOYMENT"
    ESCALATE = "ESCALATE"


@dataclass
class SupervisorPolicy:
    quarantine_risk: float = 40.0
    block_risk: float = 55.0
    escalate_risk: float = 70.0
    max_auto_recoveries: int = 2

    def decide(self, risk_score: float) -> Decision:
        if risk_score >= self.escalate_risk:
            return Decision.ESCALATE
        if risk_score >= self.block_risk:
            return Decision.BLOCK_DEPLOYMENT
        if risk_score >= self.quarantine_risk:
            return Decision.QUARANTINE
        return Decision.ACCEPT


@dataclass
class DecisionReport:
    decision: Decision
    risk_score: float
    category_scores: dict[str, float]
    observations: list[dict]
    rationale: str
    subject_id: str = ""
    facts: dict = field(default_factory=dict)
    policy_decisions: list[dict] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    validation: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "risk_score": round(self.risk_score, 2),
            "category_scores": {k: round(v, 2) for k, v in self.category_scores.items()},
            "rationale": self.rationale,
            "subject_id": self.subject_id,
            "observations": self.observations,
            "scores": {k: round(v, 2) for k, v in self.scores.items()},
            "policy_decisions": self.policy_decisions,
            "facts": self.facts,
            "validation": self.validation,
        }


def observation_risk(observation: Observation) -> float:
    """Legacy severity-only risk (Phase <10 semantics; retained verbatim)."""
    total = sum(
        SEVERITY_WEIGHTS.get(f.severity, 1.0)
        for f in observation.findings
        if not f.passed
    )
    return min(100.0, total)


# Phase 10 adaptive-risk constants (documented, deterministic).
ADAPTIVE_CONFIDENCE_FLOOR = 0.6   # a finding can never shed >40% of its weight
                                  # by claiming low confidence
ADAPTIVE_HIGH_SEVERITIES = {"HIGH", "CRITICAL"}
CRITICAL_RISK_FLOOR = 20.0        # any failed CRITICAL finding pins agent risk


def observation_risk_adaptive(observation: Observation) -> float:
    """Confidence-aware risk per §7.7 (Risk = Impact x Probability x Confidence).

    Impact      = severity weight (unchanged platform constants).
    Probability = agent-reported confidence of the finding, scaled into
                  [ADAPTIVE_CONFIDENCE_FLOOR, 1] so no failed finding can be
                  zeroed out by self-declared uncertainty.
    A failed CRITICAL finding additionally floors the result at
    CRITICAL_RISK_FLOOR regardless of confidence (anti-evasion).
    """
    total = 0.0
    critical_seen = False
    for f in observation.findings:
        if f.passed:
            continue
        weight = SEVERITY_WEIGHTS.get(f.severity, 1.0)
        conf = max(0.0, min(1.0, float(getattr(f, "confidence", 0.8) or 0.0)))
        probability = ADAPTIVE_CONFIDENCE_FLOOR + conf * (1 - ADAPTIVE_CONFIDENCE_FLOOR)
        total += weight * probability
        if f.severity == "CRITICAL":
            critical_seen = True
    risk = min(100.0, total)
    if critical_seen:
        risk = max(risk, CRITICAL_RISK_FLOOR)
    return round(risk, 4)


def aggregate_risk(observations: list[Observation],
                   adaptive: bool = True) -> tuple[float, dict[str, float]]:
    """Aggregate per-agent risk into a global score.

    Global score is the max of category scores blended with the mean, so a
    single catastrophic signal dominates while many moderate signals still
    accumulate. With ``adaptive=True`` (Phase 10) per-agent category scores use
    the confidence-aware :func:`observation_risk_adaptive`.
    """
    scorer = observation_risk_adaptive if adaptive else observation_risk
    per_agent = {obs.agent: scorer(obs) for obs in observations}
    if not per_agent:
        return 0.0, {}
    worst = max(per_agent.values())
    mean = sum(per_agent.values()) / len(per_agent)
    global_score = min(100.0, 0.6 * worst + 0.4 * mean)
    return global_score, per_agent

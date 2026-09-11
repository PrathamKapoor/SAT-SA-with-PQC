"""Agent interface and shared observation types.

Every agent converts raw context into an Observation containing discrete,
evidence-backed findings plus a recommendation. Agents never mutate state;
only the supervisor acts on observations. No agent may certify its own work:
the registry enforces verifier/signer separation independently.

Phase 2: every Finding carries structured evidence — an explicit observation
statement, one or more Evidence objects (source, kind, payload), a confidence
in [0,1], a derived risk level and a per-finding recommended action.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass
class Evidence:
    """A single verifiable datum backing a finding.

    kind    : metric | distribution | crypto | experiment | log | external
    source  : where the datum came from, e.g. "rolling_accuracy_window",
              "psi_detector", "keystore", "artifact_store"
    payload : structured values so downstream consumers (supervisor, API,
              auditors) can re-derive the conclusion without re-running the
              agent.
    """

    source: str
    kind: str = "metric"
    payload: dict = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "kind": self.kind,
            "payload": self.payload,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            source=d.get("source", ""),
            kind=d.get("kind", "metric"),
            payload=dict(d.get("payload", {})),
            description=d.get("description", ""),
        )


@dataclass
class Finding:
    name: str
    passed: bool
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    detail: str = ""
    observation: str = ""  # human-readable statement of what was seen
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.8  # agent certainty in [0, 1]
    recommendation: str = ""  # suggested action if failed (RETRAIN, ROTATE_KEYS, ...)
    # Phase 2: a stable identity for this finding, independent of its
    # position in an observation's findings list, so a provenance edge (or a
    # persisted findings-table row) can reference *this* finding specifically
    # — mirrors Observation.observation_id below.
    finding_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def risk(self) -> str:
        """Derived risk level: severity of an unresolved issue, else NONE."""
        if self.passed:
            return "NONE"
        return self.severity

    def add_evidence(
        self, source: str, kind: str = "metric", payload: dict | None = None,
        description: str = "",
    ) -> Evidence:
        ev = Evidence(source=source, kind=kind, payload=payload or {}, description=description)
        self.evidence.append(ev)
        return ev

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "risk": self.risk,
            "detail": self.detail,
            "observation": self.observation,
            "confidence": round(self.confidence, 4),
            "recommendation": self.recommendation,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        kwargs = dict(
            name=d["name"],
            passed=bool(d.get("passed", False)),
            severity=d.get("severity", "LOW"),
            detail=d.get("detail", ""),
            observation=d.get("observation", ""),
            evidence=[Evidence.from_dict(e) for e in d.get("evidence", [])],
            confidence=float(d.get("confidence", 0.8)),
            recommendation=d.get("recommendation", ""),
        )
        # Older persisted/serialized findings (pre-Phase-2) never had a
        # finding_id; only set it explicitly when present so the default
        # factory mints a fresh one for those, rather than forcing None.
        if d.get("finding_id"):
            kwargs["finding_id"] = d["finding_id"]
        return cls(**kwargs)


@dataclass
class Observation:
    agent: str
    subject_id: str
    recommendation: str
    findings: list[Finding] = field(default_factory=list)
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    observation_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def max_severity(self) -> str:
        worst = "LOW"
        for f in self.findings:
            if not f.passed and SEVERITY_ORDER.get(f.severity, 0) > SEVERITY_ORDER.get(worst, 0):
                worst = f.severity
        return worst

    @property
    def mean_confidence(self) -> float:
        if not self.findings:
            return 0.0
        return sum(f.confidence for f in self.findings) / len(self.findings)

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "agent": self.agent,
            "subject_id": self.subject_id,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "notes": self.notes,
            "max_severity": self.max_severity,
            "mean_confidence": round(self.mean_confidence, 4),
            "findings": [f.to_dict() for f in self.findings],
        }


def make_finding(
    name: str,
    passed: bool,
    severity: str,
    detail: str = "",
    observation: str = "",
    evidence: list[Evidence] | None = None,
    confidence: float = 0.9,
    recommendation: str = "",
) -> Finding:
    """Convenience constructor used by agents to emit complete evidence."""
    return Finding(
        name=name,
        passed=passed,
        severity=severity,
        detail=detail,
        observation=observation or detail,
        evidence=list(evidence or []),
        confidence=confidence,
        recommendation=recommendation if not passed else "",
    )


class BaseAgent(ABC):
    name: str = "base-agent"

    @abstractmethod
    def observe(self, context: dict) -> Observation: ...

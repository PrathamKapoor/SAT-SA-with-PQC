"""Quantum Verification Packet: immutable evidence for every important operation.

A packet records objective, inputs, artifacts (by digest), metrics, security
checks, cryptographic proofs and the decision taken. Packets are hashed into
the evidence ledger, making the operational history tamper-evident.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from qsmlops.crypto.hashing import digest_document


@dataclass
class SecurityCheck:
    name: str
    passed: bool
    severity: str = "LOW"
    detail: str = ""


@dataclass
class VerificationPacket:
    packet_id: str
    objective: str
    actor: str
    created_at: float
    inputs: dict
    artifacts: dict[str, str]
    metrics: dict
    security_checks: list[SecurityCheck]
    proofs: dict
    decision: str
    status: str

    @classmethod
    def create(
        cls,
        objective: str,
        actor: str,
        inputs: dict | None = None,
        artifacts: dict[str, str] | None = None,
        metrics: dict | None = None,
        security_checks: list[SecurityCheck] | None = None,
        proofs: dict | None = None,
        decision: str = "PENDING",
        status: str = "OPEN",
    ) -> "VerificationPacket":
        return cls(
            packet_id=uuid.uuid4().hex,
            objective=objective,
            actor=actor,
            created_at=time.time(),
            inputs=dict(inputs or {}),
            artifacts=dict(artifacts or {}),
            metrics=dict(metrics or {}),
            security_checks=list(security_checks or []),
            proofs=dict(proofs or {}),
            decision=decision,
            status=status,
        )

    def to_dict(self) -> dict:
        return {
            "packet_id": self.packet_id,
            "objective": self.objective,
            "actor": self.actor,
            "created_at": self.created_at,
            "inputs": self.inputs,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "security_checks": [c.__dict__ for c in self.security_checks],
            "proofs": self.proofs,
            "decision": self.decision,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VerificationPacket":
        checks = [SecurityCheck(**c) for c in d.get("security_checks", [])]
        return cls(
            packet_id=d["packet_id"],
            objective=d["objective"],
            actor=d["actor"],
            created_at=d["created_at"],
            inputs=d.get("inputs", {}),
            artifacts=d.get("artifacts", {}),
            metrics=d.get("metrics", {}),
            security_checks=checks,
            proofs=d.get("proofs", {}),
            decision=d.get("decision", "UNKNOWN"),
            status=d.get("status", "CLOSED"),
        )

    def digest(self) -> str:
        return digest_document(self.to_dict())

    def failed_checks(self, min_severity: str = "LOW") -> list[SecurityCheck]:
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        threshold = order[min_severity]
        return [
            c
            for c in self.security_checks
            if not c.passed and order.get(c.severity, 0) >= threshold
        ]

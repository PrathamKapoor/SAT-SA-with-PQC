"""AuditEvent: the platform's canonical audit record.

Every important action flows through this shape regardless of where it is
eventually persisted. Field vocabulary::

    event_id           — unique event identifier
    timestamp          — unix epoch seconds
    actor              — identity_id of the acting principal
    action             — verb in "domain.verb" form (e.g. identity.created)
    resource           — "<object_type>:<id>" reference of the target
    result             — SUCCESS | FAILURE | DENIED
    evidence_reference — pointer to ledger / packet / artifact evidence

Serialization is ledger-compatible: ``to_dict()`` emits exactly these fields
flat at the top level, so the evidence ledger stores them without wrapping and
``AuditEvent.from_entry`` round-trips them.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from qsmlops.core.errors import AuditError
from qsmlops.core.trusted_object import TrustedObject

RESULT_SUCCESS = "SUCCESS"
RESULT_FAILURE = "FAILURE"
RESULT_DENIED = "DENIED"
AUDIT_RESULTS = (RESULT_SUCCESS, RESULT_FAILURE, RESULT_DENIED)


@dataclass
class AuditEvent:
    event_id: str
    timestamp: float
    actor: str
    action: str
    resource: str
    result: str
    evidence_reference: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in AUDIT_RESULTS:
            raise AuditError(f"invalid audit result {self.result!r}")
        if not self.action:
            raise AuditError("audit event requires an action")
        if not self.actor:
            raise AuditError("audit event requires an actor")

    @classmethod
    def create(
        cls,
        actor: str,
        action: str,
        resource: str,
        result: str = RESULT_SUCCESS,
        evidence_reference: str = "",
        metadata: dict | None = None,
    ) -> "AuditEvent":
        return cls(
            event_id=uuid.uuid4().hex,
            timestamp=time.time(),
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            evidence_reference=evidence_reference,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_object(
        cls,
        obj: TrustedObject,
        actor: str,
        action: str,
        result: str = RESULT_SUCCESS,
        evidence_reference: str = "",
        metadata: dict | None = None,
    ) -> "AuditEvent":
        """Convenience: audit event targeting any TrustedObject."""
        return cls.create(
            actor=actor,
            action=action,
            resource=f"{obj.object_type}:{obj.id}",
            result=result,
            evidence_reference=evidence_reference,
            metadata=metadata,
        )

    def to_dict(self) -> dict:
        """Flat ledger-compatible document."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "evidence_reference": self.evidence_reference,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, doc: dict) -> "AuditEvent":
        return cls(
            event_id=doc["event_id"],
            timestamp=doc["timestamp"],
            actor=doc["actor"],
            action=doc["action"],
            resource=doc["resource"],
            result=doc["result"],
            evidence_reference=doc.get("evidence_reference", ""),
            metadata=doc.get("metadata", {}),
        )


def resource_for(obj: TrustedObject) -> str:
    return f"{obj.object_type}:{obj.id}"

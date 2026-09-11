"""Identity model.

An Identity is a TrustedObject: it carries the same identity/ownership/
version/hash/signature/verification vocabulary as every other governed
entity. Kinds:

* ``human``  — administrators, ML engineers, security analysts, operators
* ``service``— training, registry, deployment and serving services
* ``agent``  — security, performance, monitoring agents (least privilege)

Identities are created and deactivated through IdentityService, never mutated
directly; every change emits an audit event.
"""
from __future__ import annotations

from typing import Any

from qsmlops.core.errors import PermissionDeniedError
from qsmlops.core.trusted_object import TrustedObject
from qsmlops.security.permissions.model import has_permission

KIND_HUMAN = "human"
KIND_SERVICE = "service"
KIND_AGENT = "agent"
IDENTITY_KINDS = (KIND_HUMAN, KIND_SERVICE, KIND_AGENT)

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_REVOKED = "revoked"
IDENTITY_STATUSES = (STATUS_ACTIVE, STATUS_INACTIVE, STATUS_REVOKED)

IDENTITY_OBJECT_TYPE = "identity"


class Identity(TrustedObject):
    """A principal the platform can authorize and audit."""

    def __init__(
        self,
        kind: str,
        name: str,
        owner: str,
        role: str,
        *,
        permissions: set[str] | None = None,
        status: str = STATUS_ACTIVE,
        description: str = "",
        **trusted_kwargs: Any,
    ) -> None:
        if kind not in IDENTITY_KINDS:
            raise ValueError(f"invalid identity kind {kind!r}")
        if not name:
            raise ValueError("identity name is required")
        super().__init__(object_type=IDENTITY_OBJECT_TYPE, owner=owner, **trusted_kwargs)
        self.kind = kind
        self.name = name
        self.role = role
        self.permissions: set[str] = set(permissions or set())
        self.status = status
        self.description = description

    # -------------------- serialization --------------------
    def to_dict(self) -> dict[str, Any]:
        doc = super().to_dict()
        doc["kind"] = self.kind
        doc["name"] = self.name
        doc["role"] = self.role
        doc["permissions"] = sorted(self.permissions)
        doc["status"] = self.status
        doc["description"] = self.description
        return doc

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "Identity":
        if doc.get("object_type") != IDENTITY_OBJECT_TYPE:
            raise ValueError("document is not an identity record")
        identity = cls(
            kind=doc["kind"],
            name=doc["name"],
            owner=doc["owner"],
            role=doc["role"],
            permissions=set(doc.get("permissions", [])),
            status=doc.get("status", STATUS_ACTIVE),
            description=doc.get("description", ""),
            id=doc.get("id"),
            version=doc.get("version", 1),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            hash=doc.get("hash", ""),
            signature=doc.get("signature"),
            verification_status=doc.get("verification_status", "UNVERIFIED"),
            metadata=doc.get("metadata"),
        )
        return identity

    # -------------------- authorization --------------------
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    def grants(self) -> set[str]:
        """Effective permission strings: the role plus explicit extras."""
        if self.role:
            return {self.role, *self.permissions}
        return set(self.permissions)

    def has_permission(self, permission: str) -> bool:
        return has_permission(self.grants(), permission)

    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            raise PermissionDeniedError(
                f"identity {self.name!r} lacks permission {permission!r}"
            )

    @property
    def display(self) -> str:
        return f"{self.kind}:{self.name}"

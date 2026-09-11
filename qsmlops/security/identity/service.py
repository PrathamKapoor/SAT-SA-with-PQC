"""Identity service: lifecycle of platform identities.

Creation is the only mutate path; identities are authenticated by their
keypairs (managed by the KeyManagementService) rather than passwords. Every
lifecycle change emits an audit event, guaranteeing a provable trail.

Role name vocabulary lives in ``qsmlops.security.permissions``; the service
accepts both custom strings and the built-in set. Unknown roles are rejected
by the permission model at check time, but we validate existence here too so
bad data never persists.
"""
from __future__ import annotations

import time

from qsmlops.core.errors import (
    AuthenticationError,
    IdentityAlreadyExistsError,
    IdentityError,
    NotFoundError,
    PermissionDeniedError,
)
from qsmlops.core.logging import get_logger
from qsmlops.database.repositories import IdentityCredentialRepository, IdentityRepository
from qsmlops.security.audit.events import AuditEvent
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.auth import (
    AuthenticatedPrincipal,
    generate_credential,
    verify_credential,
)
from qsmlops.security.identity.models import (
    IDENTITY_KINDS,
    IDENTITY_STATUSES,
    Identity,
    KIND_AGENT,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    STATUS_REVOKED,
)
from qsmlops.security.permissions.model import ROLES, has_permission

log = get_logger(__name__)


class IdentityService:
    """Identity creation, authorization and deactivation."""

    def __init__(
        self,
        database,
        audit: AuditService,
        *,
        keystore=None,
        signature_service=None,
        agility=None,
    ) -> None:
        self._repo = IdentityRepository(database)
        self._credentials = IdentityCredentialRepository(database)
        self._audit = audit
        self._keystore = keystore
        self._signature_service = signature_service
        # Phase 2: accept an already-configured AgilityEngine (e.g. the
        # pipeline's) so identity key issuance uses the same suite as
        # evidence/passport signing, instead of independently constructing
        # an unconfigured engine that may auto-select a different default.
        # None preserves prior behaviour for callers that construct this
        # service directly without a shared engine.
        self._agility = agility

    # -------------------- creation --------------------
    def create_identity(
        self,
        kind: str,
        name: str,
        owner: str,
        role: str = "",
        *,
        permissions: set[str] | None = None,
        description: str = "",
        metadata: dict | None = None,
    ) -> Identity:
        if kind not in IDENTITY_KINDS:
            raise IdentityError(f"invalid identity kind {kind!r}")
        if role and role not in ROLES:
            raise IdentityError(f"unknown role {role!r}; define it in the permission model first")
        identity = Identity(
            kind=kind,
            name=name,
            owner=owner,
            role=role,
            permissions=permissions,
            description=description,
            metadata=metadata,
            status=STATUS_ACTIVE,
        )
        identity.compute_hash()
        # Optional key issuance for principals that will sign as themselves.
        if kind != KIND_AGENT and self._keystore is not None:
            try:
                if self._agility is not None:
                    agility = self._agility
                else:
                    from qsmlops.crypto.agility import AgilityEngine

                    agility = AgilityEngine()
                suite = agility.select_suite()
                self._keystore.generate_keypair(
                    "SIGNER", suite.signature_algorithm, owner=identity.display
                )
            except Exception as exc:  # key issuance is best-effort in Phase 1
                log.warning("identity key issuance failed for %s: %s", identity.display, exc)
        try:
            self._repo.insert(identity)
        except IdentityError:
            raise IdentityAlreadyExistsError(
                f"identity {kind}:{name} already exists"
            )
        self._audit.record(
            AuditEvent.from_object(
                identity,
                actor=owner or "system",
                action="identity.created",
                metadata={"kind": kind, "role": role},
            )
        )
        return identity

    # -------------------- lookup --------------------
    def get(self, identity_id: str) -> Identity:
        identity = self._repo.get(identity_id)
        if identity is None:
            raise NotFoundError(f"identity {identity_id} not found")
        return identity

    def find(self, kind: str, name: str) -> Identity | None:
        return self._repo.find_by_name(kind, name)

    def list(
        self, kind: str | None = None, status: str | None = None
    ) -> list[Identity]:
        return self._repo.list(kind=kind, status=status)

    # -------------------- authorization --------------------
    def authorize(self, identity: Identity | str, permission: str) -> Identity:
        """Return the identity iff it holds the permission; raise otherwise."""
        if isinstance(identity, str):
            identity = self.get(identity)
        if not identity.is_active():
            raise PermissionDeniedError(f"identity {identity.name!r} is not active")
        identity.require_permission(permission)
        return identity

    # -------------------- lifecycle --------------------
    def set_status(
        self,
        identity_id: str,
        status: str,
        *,
        actor: str = "system",
        reason: str = "",
    ) -> Identity:
        if status not in IDENTITY_STATUSES:
            raise IdentityError(f"invalid status {status!r}")
        identity = self.get(identity_id)
        if identity.status == STATUS_REVOKED and status != STATUS_REVOKED:
            raise IdentityError("revoked identities cannot be re-activated")
        identity.status = status
        identity.updated_at = time.time()
        identity.version += 1
        identity.compute_hash()
        self._repo.update(identity)
        self._audit.record(
            AuditEvent.from_object(
                identity,
                actor=actor,
                action=f"identity.status.{status.lower()}",
                metadata={"reason": reason},
            )
        )
        return identity

    def deactivate(self, identity_id: str, *, actor: str = "system") -> Identity:
        return self.set_status(identity_id, STATUS_INACTIVE, actor=actor)

    def revoke(self, identity_id: str, *, actor: str = "system", reason: str = "") -> Identity:
        return self.set_status(identity_id, STATUS_REVOKED, actor=actor, reason=reason)

    def grant_permissions(
        self,
        identity_id: str,
        permissions: set[str],
        *,
        actor: str = "system",
    ) -> Identity:
        identity = self.get(identity_id)
        identity.permissions |= set(permissions)
        identity.updated_at = time.time()
        identity.version += 1
        identity.compute_hash()
        self._repo.update(identity)
        self._audit.record(
            AuditEvent.from_object(
                identity,
                actor=actor,
                action="identity.permissions.granted",
                metadata={"permissions": sorted(permissions)},
            )
        )
        return identity

    # -------------------- authentication (Phase 2) --------------------
    def issue_credential(self, identity_id: str, *, actor: str = "system") -> str:
        """Mint a new API-key credential for an identity, returned once as the
        raw token. Re-issuing replaces (rotates) any prior credential for the
        same identity — the old token stops authenticating immediately."""
        identity = self.get(identity_id)
        raw_token, key_id, key_hash, salt = generate_credential()
        self._credentials.set_credential(
            identity.id, key_id, key_hash, salt, created_at=time.time()
        )
        self._audit.record(
            AuditEvent.from_object(
                identity,
                actor=actor,
                action="identity.credential.issued",
                metadata={"key_id": key_id},
            )
        )
        return raw_token

    def revoke_credential(self, identity_id: str, *, actor: str = "system") -> None:
        self._credentials.revoke(identity_id, revoked_at=time.time())
        self._audit.record(
            AuditEvent.from_object(
                self.get(identity_id),
                actor=actor,
                action="identity.credential.revoked",
                metadata={},
            )
        )

    def authenticate(self, raw_token: str) -> AuthenticatedPrincipal:
        """Resolve a presented ``key_id.secret`` token to the identity it was
        issued to. Raises AuthenticationError for every failure mode (no such
        key_id, hash mismatch, revoked credential, inactive identity) without
        distinguishing which — a caller must not be able to tell "this key_id
        doesn't exist" from "this key_id exists but the secret is wrong,"
        which would let an attacker enumerate valid key_ids."""
        if "." not in (raw_token or ""):
            raise AuthenticationError("missing or malformed credential")
        key_id = raw_token.split(".", 1)[0]
        row = self._credentials.get_by_key_id(key_id)
        if row is None or row.get("revoked_at") is not None:
            raise AuthenticationError("invalid credential")
        if not verify_credential(raw_token, row["key_hash"], row["salt"]):
            raise AuthenticationError("invalid credential")
        identity = self._repo.get(row["identity_id"])
        if identity is None or not identity.is_active():
            raise AuthenticationError("invalid credential")
        return AuthenticatedPrincipal(
            identity_id=identity.id,
            kind=identity.kind,
            name=identity.name,
            role=identity.role,
            grants=frozenset(identity.grants()),
        )

    def revoke_permissions(
        self,
        identity_id: str,
        permissions: set[str],
        *,
        actor: str = "system",
    ) -> Identity:
        identity = self.get(identity_id)
        identity.permissions -= set(permissions)
        identity.updated_at = time.time()
        identity.version += 1
        identity.compute_hash()
        self._repo.update(identity)
        self._audit.record(
            AuditEvent.from_object(
                identity,
                actor=actor,
                action="identity.permissions.revoked",
                metadata={"permissions": sorted(permissions)},
            )
        )
        return identity

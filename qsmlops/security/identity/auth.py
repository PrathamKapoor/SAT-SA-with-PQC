"""Local credential authentication (Phase 2 identity-security foundation).

Scope, deliberately: this is a local API-key credential store suitable for a
single-installation, air-gapped deployment — not enterprise SSO, not OAuth,
not a session/cookie system. Phase 1's audit found API routes accepted
``actor``/``approver`` as arbitrary unauthenticated request-body strings; this
module is the piece that lets a caller be resolved to a real, persisted
``Identity`` record instead, so a route can require "who does the platform
say you are" rather than trust "who you claim to be in this field."

A credential is a random high-entropy token, ``f"{key_id}.{secret}"``.
``key_id`` is a non-secret lookup prefix (stored in the clear, used as an
index); ``secret`` is never stored — only a per-credential-salted SHA3-256
hash of it is. Losing the raw token means it cannot be recovered, only
reissued (which invalidates the old one).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from qsmlops.core.errors import AuthenticationError
from qsmlops.security.permissions.model import ROLES, has_permission

_KEY_ID_BYTES = 8
_SECRET_BYTES = 32
_SALT_BYTES = 16


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Resolved caller identity for an authenticated request.

    ``grants`` is the raw role/permission-string set from the Identity
    record (as ``Identity.grants()`` returns it) — callers check specific
    permissions through :func:`has_permission`, not by inspecting this set
    directly, so a future custom-role definition does not require every
    call site to change.
    """

    identity_id: str
    kind: str
    name: str
    role: str
    grants: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        return has_permission(set(self.grants), permission)


def _hash_secret(secret: str, salt: str) -> str:
    return hashlib.sha3_256((salt + secret).encode("utf-8")).hexdigest()


def generate_credential() -> tuple[str, str, str, str]:
    """Create a new credential. Returns ``(raw_token, key_id, key_hash, salt)``.

    ``raw_token`` is shown to the caller exactly once and never stored;
    only ``key_id``/``key_hash``/``salt`` are persisted.
    """
    key_id = secrets.token_hex(_KEY_ID_BYTES)
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    salt = secrets.token_hex(_SALT_BYTES)
    key_hash = _hash_secret(secret, salt)
    raw_token = f"{key_id}.{secret}"
    return raw_token, key_id, key_hash, salt


def split_token(raw_token: str) -> tuple[str, str]:
    """Split ``key_id.secret``. Raises AuthenticationError on malformed input
    — never on missing input, since "no token presented" is the caller's
    responsibility to check before calling this (see resolve_principal)."""
    if not raw_token or "." not in raw_token:
        raise AuthenticationError("malformed credential")
    key_id, _, secret = raw_token.partition(".")
    if not key_id or not secret:
        raise AuthenticationError("malformed credential")
    return key_id, secret


def verify_credential(raw_token: str, key_hash: str, salt: str) -> bool:
    """Constant-time comparison against the stored hash."""
    _, secret = split_token(raw_token)
    candidate = _hash_secret(secret, salt)
    return hmac.compare_digest(candidate, key_hash)

"""SAT-SA authentication + authorization.

This module does not invent an authentication system — it wires the
UI and CLI to the *existing* qsmlops identity/credential system
(``qsmlops.security.identity``), which already has salted API-key
credentials, role/permission checks, and an audited lifecycle, with
14 passing tests (``tests/test_phase2_identity_auth.py``). Before
this module existed, the SAT-SA UI's review-decision endpoint read
``request.headers.get("x-satsa-principal", "ui-anonymous")`` — any
caller could set that header to any string and it would be recorded
verbatim in the permanent human-decision audit trail
(``satsa/analysis/review.py``, whose own docstring already disclosed
this: "the audit row records the id faithfully — it does not verify
the caller is who they claim").

No new crypto, no new session format: the only credential type is
the same ``key_id.secret`` bearer token
(``qsmlops.security.identity.auth``). An HTML ``<form>`` POST cannot
set a custom ``Authorization`` header, so a browser client carries
the token in an HttpOnly cookie (set once at ``/login``); an API/CLI
client carries it in the ``Authorization: Bearer`` header, exactly
like ``qsmlops.api.foundation``. Both paths resolve through the same
``IdentityService.authenticate()`` call — there is exactly one place
a credential is ever verified.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from qsmlops.core.errors import AuthenticationError
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.auth import AuthenticatedPrincipal
from qsmlops.security.identity.service import IdentityService

COOKIE_NAME = "satsa_credential"


def build_identity_service(db, *, ledger_dir: Path) -> IdentityService:
    """Construct a standalone ``IdentityService`` bound to the SAT-SA
    database.

    Deliberately independent of the full qsmlops MLOps pipeline
    object (``qsmlops.core.context``'s container wires
    ``IdentityService`` off ``pipeline.ledger`` and
    ``pipeline.agility``) — SAT-SA does not run the model-lifecycle
    pipeline, so pulling it in just to get an audit ledger would be
    a large, unrelated dependency. ``EvidenceLedger`` is a small,
    standalone, file-backed hash-chained ledger (see
    ``qsmlops/evidence/ledger.py``); this gives identity/auth
    lifecycle events (identity created, credential issued/revoked,
    permission granted/revoked) their own audited trail, separate
    from — and independent of — SAT-SA's own TRUST-SAT run/finding
    ledger.
    """
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = EvidenceLedger(ledger_dir / "identity_audit_ledger.jsonl")
    audit = AuditService(ledger=ledger, database=db)
    return IdentityService(database=db, audit=audit)


def bearer_token(request: Request) -> Optional[str]:
    """Extract a presented credential: ``Authorization: Bearer`` header
    first (API/CLI clients), falling back to the session cookie
    (browser clients that went through ``/login``)."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[len("bearer "):].strip()
        if token:
            return token
    cookie = request.cookies.get(COOKIE_NAME)
    return cookie or None


def resolve_principal(
    request: Request, identity_service: IdentityService
) -> Optional[AuthenticatedPrincipal]:
    """Resolve the caller's ``AuthenticatedPrincipal``, or ``None`` if
    no credential was presented at all. Raises 401 if a credential
    *was* presented but does not resolve (unknown key_id, wrong
    secret, revoked, or the identity is inactive) — mirroring
    ``qsmlops.api.foundation``'s distinction between "no credential"
    (may be legitimate, e.g. an anonymous read of a public page) and
    "a credential was presented and rejected" (always an error)."""
    token = bearer_token(request)
    if token is None:
        return None
    try:
        return identity_service.authenticate(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require(
    identity_service: IdentityService, request: Request, permission: str
) -> AuthenticatedPrincipal:
    """Require an authenticated principal holding ``permission``.

    401 if unauthenticated (no credential, or credential rejected);
    403 if authenticated but lacking the permission. The permission
    check is server-side and happens on every call — there is no
    "the UI hid the button" substitute for this (SIH prompt section
    93: authentication must survive a direct API attack that bypasses
    the UI entirely).
    """
    principal = resolve_principal(request, identity_service)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if not principal.has_permission(permission):
        raise HTTPException(
            status_code=403,
            detail=f"principal {principal.name!r} lacks permission {permission!r}",
        )
    return principal

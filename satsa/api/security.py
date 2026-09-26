"""API sessions reuse QSMLOps credentials and SAT-SA persistent sessions."""

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer

from qsmlops.core.errors import AuthenticationError, PermissionDeniedError
from qsmlops.security.audit.events import AuditEvent
from satsa.tenancy import SessionRepository, TenantRepository

COOKIE = "satsa_api_session"
bearer = HTTPBearer(auto_error=False)
cookie = APIKeyCookie(name=COOKIE, auto_error=False)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class RateLimiter:
    """Atomic fixed-window limits shared by API instances; no raw keys stored."""

    def __init__(self, db):
        self.db = db

    def check(self, scope: str, limit: int):
        at = int(time.time() // 60)
        hashed = hashlib.sha3_256(scope.encode()).hexdigest()
        row = self.db.query_one(
            "INSERT INTO satsa_api_rate_limits(scope_hash,window_id,count) VALUES (?,?,1)"
            " ON CONFLICT(scope_hash,window_id) DO UPDATE SET count=satsa_api_rate_limits.count+1 RETURNING count",
            (hashed, at),
        )
        if row["count"] > limit:
            raise ApiError(429, "RATE_LIMITED", "Request limit reached; retry shortly")
        # Old windows are unnecessary. This is bounded by configured deployment
        # traffic; a periodic maintenance task can replace cleanup at scale.
        self.db.execute(
            "DELETE FROM satsa_api_rate_limits WHERE window_id<?", (at - 2,)
        )


def csrf_token(token: str) -> str:
    return hmac.new(token.encode(), b"satsa-api-csrf-v1", hashlib.sha3_256).hexdigest()


@dataclass(frozen=True)
class Caller:
    user_id: str
    identity_id: str
    name: str
    role: str
    token: str
    session: dict | None
    cookie_auth: bool


def authenticate_token(app, token: str, cookie_auth: bool = False) -> Caller:
    db = app.state.db
    sessions = SessionRepository(db)
    session = sessions.resolve(token)
    if session:
        row = db.query_one(
            "SELECT u.id,u.identity_id,i.name,i.role,s.auth_key_id FROM satsa_users u"
            " JOIN identities i ON i.identity_id=u.identity_id JOIN satsa_sessions s ON s.user_id=u.id"
            " WHERE s.id=? AND u.id=?",
            (session["id"], session["user_id"]),
        )
        credential = db.query_one(
            "SELECT key_id FROM identity_credentials WHERE identity_id=? AND key_id=? AND revoked_at IS NULL",
            (row["identity_id"], row["auth_key_id"]),
        )
        if credential is None:
            raise AuthenticationError("invalid session")
        sessions.touch(token)
        return Caller(
            row["id"],
            row["identity_id"],
            row["name"],
            row["role"],
            token,
            session,
            cookie_auth,
        )
    if cookie_auth:
        raise AuthenticationError("invalid session")
    principal = app.state.identities.authenticate(token)
    row = db.query_one(
        "SELECT id FROM satsa_users WHERE identity_id=? AND status='active'",
        (principal.identity_id,),
    )
    if not row or principal.kind != "human":
        raise AuthenticationError("active user required")
    return Caller(
        row["id"],
        principal.identity_id,
        principal.name,
        principal.role,
        token,
        None,
        False,
    )


def caller(
    request: Request,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session_cookie: Annotated[str | None, Depends(cookie)],
) -> Caller:
    token = authorization.credentials if authorization else session_cookie
    if not token:
        peer = request.client.host if request.client else "unknown"
        request.app.state.limiter.check(
            f"unauthenticated:{peer}", request.app.state.settings.read_limit
        )
        raise AuthenticationError("authentication required")
    result = authenticate_token(request.app, token, not bool(authorization))
    if result.cookie_auth and request.method not in {"GET", "HEAD", "OPTIONS"}:
        received = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(received, csrf_token(token)):
            raise PermissionDeniedError("CSRF validation failed")
    request.state.caller = result
    settings = request.app.state.settings
    route = request.scope.get("route")
    operation = (
        "read" if request.method == "GET" else getattr(route, "path", request.url.path)
    )
    request.app.state.limiter.check(
        f"user:{result.user_id}:{operation}",
        settings.read_limit if request.method == "GET" else settings.mutation_limit,
    )
    return result


def tenant(
    request: Request, user: Annotated[Caller, Depends(caller)]
) -> TenantRepository:
    org = request.headers.get("X-Organization-ID", "")
    if not org or len(org) > 128:
        raise ApiError(400, "ORGANIZATION_REQUIRED", "X-Organization-ID is required")
    repository = TenantRepository(request.app.state.db, org, user.user_id)
    repository._require("finding.view")
    request.state.organization_id = org
    return repository


def audit_action(request, user, action, resource, result="SUCCESS", **metadata):
    request.app.state.audit.record(
        AuditEvent.create(
            actor=user.identity_id,
            action=action,
            resource=resource,
            result=result,
            metadata={
                "organization_id": getattr(request.state, "organization_id", None),
                "request_id": request.state.request_id,
                **metadata,
            },
        )
    )

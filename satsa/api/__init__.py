"""Dedicated tenant-aware SaaS API. Legacy demo routes are not mounted."""

import json
import re
import time
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from qsmlops.core.errors import NotFoundError, QSMLOPSError
from qsmlops.core.logging import get_logger
from satsa.analysis.execution import AnalysisExecutionService
from satsa.errors import DomainValidationError
from satsa.submissions.service import SubmissionService
from satsa.tenancy import SessionRepository, TenantRepository

from . import schemas as s
from .repository import ApiRepository
from .security import (
    COOKIE,
    ApiError,
    Caller,
    RateLimiter,
    audit_action,
    authenticate_token,
    caller,
    csrf_token,
    tenant,
)
from .settings import ApiSettings

log = get_logger(__name__)
User = Annotated[Caller, Depends(caller)]
Tenant = Annotated[TenantRepository, Depends(tenant)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=1000000)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def create_app(
    engine, *, storage, audit, identity_service, settings=None, trust_key_dir=None
):
    settings = settings or ApiSettings()
    app = FastAPI(
        title="SAT-SA Supervisory API",
        version="1.0.0",
        description="Periodic tenant-scoped assessment. Human review is authoritative.",
        responses={
            code: {"model": s.Error}
            for code in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503)
        },
    )
    app.state.db = engine
    app.state.storage = storage
    app.state.audit = audit
    app.state.identities = identity_service
    app.state.settings = settings
    app.state.limiter = RateLimiter(engine)
    app.state.trust_key_dir = trust_key_dir
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts)
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Organization-ID",
                "X-CSRF-Token",
                "Idempotency-Key",
            ],
            expose_headers=["X-Request-ID", "Retry-After"],
        )

    def error(request, status, code, message, details=None):
        headers = {
            "X-Request-ID": getattr(request.state, "request_id", ""),
            "Cache-Control": "no-store",
        }
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        if status == 429:
            headers["Retry-After"] = "60"
        return JSONResponse(
            status_code=status,
            headers=headers,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": getattr(request.state, "request_id", ""),
                    "details": details or [],
                }
            },
        )

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(QSMLOPSError)
    async def platform_error(request, exc):
        messages = {
            401: "Authentication required or credential invalid",
            403: "Operation or resource access denied",
            404: "Resource not found",
            409: "Resource conflict",
            503: "Service unavailable",
        }
        return error(
            request,
            exc.status_code,
            exc.code,
            messages.get(exc.status_code, "Service failure"),
        )

    @app.exception_handler(DomainValidationError)
    async def domain_error(request, exc):
        message = str(exc)
        conflict = any(
            term in message.lower()
            for term in ("already", "immutable", "duplicate", "conflict")
        )
        return error(
            request,
            409 if conflict else 422,
            "DOMAIN_CONFLICT" if conflict else "DOMAIN_INVALID",
            message,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [
            {"location": list(e["loc"]), "code": e["type"], "message": e["msg"]}
            for e in exc.errors()
        ]
        return error(
            request, 422, "VALIDATION_ERROR", "Request validation failed", details
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(
            request, exc.status_code, "HTTP_ERROR", "Request could not be processed"
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error(
            "api.request_failed",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "error_type": type(exc).__name__,
            },
        )
        return error(
            request,
            500,
            "INTERNAL_ERROR",
            "Request failed; contact the administrator with the request ID",
        )

    # Request bodies are bounded before multipart parsing, including requests
    # without Content-Length. Content checks remain in SubmissionService.
    class Edge:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)
            headers = dict(scope["headers"])
            incoming = headers.get(b"x-request-id", b"").decode("ascii", "ignore")
            request_id = (
                incoming
                if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming)
                else uuid4().hex
            )
            scope.setdefault("state", {})["request_id"] = request_id
            request = Request(scope)
            started_at = time.monotonic()
            peer = scope.get("client")
            # Health probes must reach their own checks when database-backed
            # rate limiting is unavailable; readiness handles DB failure safely.
            if scope.get("path") not in {"/health/live", "/health/ready"}:
                try:
                    app.state.limiter.check(
                        f"ip:{peer[0] if peer else 'unknown'}", settings.read_limit
                    )
                except ApiError as exc:
                    return await error(request, exc.status, exc.code, exc.message)(
                        scope, receive, send
                    )
            # NUL cannot be stored in PostgreSQL text; identifiers carrying it
            # are malformed input and must not reach the database as a 500.
            query = scope.get("query_string", b"")
            if "\x00" in scope.get("path", "") or b"%00" in query or b"\x00" in query:
                return await error(
                    request, 400, "MALFORMED_REQUEST", "Malformed request"
                )(scope, receive, send)
            try:
                declared = int(headers.get(b"content-length", b"0"))
            except ValueError:
                return await error(
                    request, 400, "MALFORMED_REQUEST", "Invalid content length"
                )(scope, receive, send)
            if declared > settings.max_request_bytes or declared < 0:
                return await error(
                    request, 413, "REQUEST_TOO_LARGE", "Request exceeds size limit"
                )(scope, receive, send)
            count = 0

            async def bounded_receive():
                nonlocal count
                message = await receive()
                count += len(message.get("body", b""))
                if count > settings.max_request_bytes:
                    raise ApiError(
                        413, "REQUEST_TOO_LARGE", "Request exceeds size limit"
                    )
                return message

            async def secured_send(message):
                if message["type"] == "http.response.start":
                    route = scope.get("route")
                    actor = getattr(request.state, "caller", None)
                    log.info(
                        "api.response",
                        extra={
                            "event": "api.response",
                            "request_id": request_id,
                            "organization_id": getattr(
                                request.state, "organization_id", ""
                            ),
                            "user_id": getattr(actor, "user_id", ""),
                            "method": scope.get("method", ""),
                            "route": getattr(route, "path", ""),
                            "status_code": message.get("status", 0),
                            "duration_ms": round(
                                (time.monotonic() - started_at) * 1000, 2
                            ),
                        },
                    )
                    message["headers"] = [
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower() not in {b"x-request-id", b"cache-control"}
                    ] + [
                        (b"x-request-id", request_id.encode()),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-robots-tag", b"noindex, nofollow"),
                    ]
                    if settings.secure_cookies:
                        message["headers"].append(
                            (b"strict-transport-security", b"max-age=31536000")
                        )
                await send(message)

            await self.app(scope, bounded_receive, secured_send)

    app.add_middleware(Edge)

    def submissions(t):
        return SubmissionService(
            engine, t.organization_id, t.user_id, storage=storage, audit=audit
        )

    def execution(t):
        return AnalysisExecutionService(
            engine, t.organization_id, t.user_id, audit=audit
        )

    def run_view(row, svc=None):
        if (
            row["graph_enabled"]
            and svc is not None
            and row["status"] in {"running", "awaiting_review"}
        ):
            row["current_stage"] = svc.get_graph_progress(row["id"]).get(
                "current_stage", row["status"]
            )
        return {
            **row,
            "execution_mode": "graph" if row["graph_enabled"] else "standard",
            "review_required": bool(row["review_required"]),
            "current_stage": next(
                (
                    step["worker_name"]
                    for step in row["steps"]
                    if step["status"] == "running"
                ),
                row["status"],
            ),
        }

    def finding_view(row, run_id=None):
        return {
            **row,
            "run_id": run_id or row["run_id"],
            "confidence": json.loads(row["confidence_json"] or "null"),
            "evidence_refs": json.loads(row["evidence_refs_json"]),
            "scoped_subjects": json.loads(row["scoped_subjects_json"]),
        }

    @app.get("/health/live", tags=["health"], operation_id="liveness")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"], operation_id="readiness")
    def ready():
        try:
            from qsmlops.database.migrations import MIGRATIONS

            engine.query_one("SELECT 1 AS ready")
            row = engine.query_one(
                "SELECT MAX(version) AS version FROM schema_migrations"
            )
            if row is None or row["version"] != max(m.version for m in MIGRATIONS):
                raise RuntimeError("migrations pending")
            if trust_key_dir is None:
                raise RuntimeError("trust not configured")
            storage.check_ready()
        except Exception as exc:
            raise ApiError(
                503, "NOT_READY", "Critical dependencies are not ready"
            ) from exc
        return {"status": "ready"}

    @app.post(
        "/api/v1/session",
        response_model=s.Session,
        tags=["session"],
        operation_id="login",
    )
    def login(body: s.Login, request: Request, response: Response):
        app.state.limiter.check(
            f"login:{request.client.host if request.client else 'unknown'}", 5
        )
        # Browser login is protected against login-CSRF by exact Origin policy.
        origin = request.headers.get("Origin")
        if (
            origin
            and origin not in settings.allowed_origins
            and origin != str(request.base_url).rstrip("/")
        ):
            raise ApiError(403, "ORIGIN_DENIED", "Origin is not allowed")
        user = authenticate_token(app, body.credential)
        token = SessionRepository(engine).create(
            user.user_id, ttl_seconds=settings.session_ttl
        )
        engine.execute(
            "UPDATE satsa_sessions SET auth_key_id=? WHERE token_digest=?",
            (
                body.credential.split(".", 1)[0],
                __import__("hashlib").sha3_256(token.encode()).hexdigest(),
            ),
        )
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.session_ttl,
            httponly=True,
            secure=settings.secure_cookies,
            samesite=settings.cookie_samesite,
            path="/api/v1",
        )
        audit_action(request, user, "session.login", f"user:{user.user_id}")
        return {
            "identity_id": user.identity_id,
            "name": user.name,
            "role": user.role,
            "user_id": user.user_id,
            "expires_at": time.time() + settings.session_ttl,
            "csrf_token": csrf_token(token),
        }

    @app.get(
        "/api/v1/session",
        response_model=s.Session,
        tags=["session"],
        operation_id="current_session",
    )
    def session(user: User):
        return {
            "identity_id": user.identity_id,
            "name": user.name,
            "role": user.role,
            "user_id": user.user_id,
            "expires_at": user.session["expires_at"] if user.session else None,
            "csrf_token": csrf_token(user.token) if user.session else None,
        }

    @app.delete(
        "/api/v1/session", status_code=204, tags=["session"], operation_id="logout"
    )
    def logout(request: Request, user: User):
        if user.session:
            SessionRepository(engine).revoke(user.token)
        else:
            # A bearer key has no server-side session to revoke independently.
            app.state.identities.revoke_credential(
                user.identity_id, actor=user.identity_id
            )
        audit_action(request, user, "session.logout", f"user:{user.user_id}")
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE,
            path="/api/v1",
            secure=settings.secure_cookies,
            httponly=True,
            samesite=settings.cookie_samesite,
        )
        return response

    @app.get(
        "/api/v1/organizations",
        response_model=s.Page[s.Organization],
        tags=["organizations"],
        operation_id="list_organizations",
    )
    def organizations(user: User, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(
            TenantRepository(engine, "membership-discovery", user.user_id)
        ).organizations(limit, offset)

    @app.post(
        "/api/v1/organizations",
        response_model=s.Organization,
        status_code=201,
        tags=["organizations"],
        operation_id="create_organization",
    )
    def create_organization(body: s.OrganizationInput, request: Request, user: User):
        from qsmlops.security.permissions.model import has_permission
        from satsa.tenancy import TenantAdministration

        if not has_permission({user.role}, "identity.manage"):
            raise ApiError(
                403, "PERMISSION_DENIED", "Platform administration permission required"
            )
        name = body.name
        with engine.transaction():
            org = TenantAdministration(engine).create_organization(name)
            engine.execute(
                "INSERT INTO satsa_memberships(organization_id,user_id,role,created_at) VALUES (?,?,?,?)",
                (org, user.user_id, "satsa_admin", time.time()),
            )
        request.state.organization_id = org
        audit_action(request, user, "organization.created", f"organization:{org}")
        return {
            "id": org,
            "name": name.strip(),
            "status": "active",
            "role": "satsa_admin",
        }

    @app.get(
        "/api/v1/members",
        response_model=s.Page[s.Member],
        tags=["organizations"],
        operation_id="list_members",
    )
    def members(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(t).members(limit, offset)

    @app.post(
        "/api/v1/members",
        response_model=s.Invitation,
        status_code=201,
        tags=["organizations"],
        operation_id="invite_member",
    )
    def invite_member(body: s.MemberInput, t: Tenant, request: Request, user: User):
        t._require("identity.manage")
        from satsa.tenancy import TenantAdministration

        identity = app.state.identities.create_identity(
            "human", body.name, f"organization:{t.organization_id}", body.role
        )
        try:
            with engine.transaction():
                user_id = TenantAdministration(engine).create_user(
                    identity.id, body.email
                )
                TenantAdministration(engine).add_membership(
                    t.organization_id, user_id, body.role
                )
                credential = app.state.identities.issue_credential(
                    identity.id, actor=user.identity_id
                )
        except Exception:
            app.state.identities.revoke(
                identity.id, actor=user.identity_id, reason="membership setup failed"
            )
            raise
        audit_action(
            request,
            user,
            "organization.member_invited",
            f"user:{user_id}",
            metadata_role=body.role,
        )
        response = {
            "id": user_id,
            "identity_id": identity.id,
            "name": body.name,
            "email": body.email,
            "role": body.role,
            "status": "active",
            "credential": credential,
        }
        return response

    @app.delete(
        "/api/v1/members/{user_id}",
        status_code=204,
        tags=["organizations"],
        operation_id="revoke_member",
    )
    def revoke_member(user_id: str, t: Tenant, request: Request, user: User):
        ApiRepository(t).set_member_status(user_id, "revoked")
        audit_action(request, user, "organization.member_revoked", f"user:{user_id}")
        return Response(status_code=204)

    @app.get(
        "/api/v1/entities",
        response_model=s.Page[s.Entity],
        tags=["entities"],
        operation_id="list_entities",
    )
    def entities(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(t).collection("entities", limit=limit, offset=offset)

    @app.post(
        "/api/v1/entities",
        response_model=s.Entity,
        status_code=201,
        tags=["entities"],
        operation_id="create_entity",
    )
    def create_entity(body: s.EntityInput, t: Tenant, request: Request, user: User):
        identity = t.create_entity(**body.model_dump())
        audit_action(request, user, "entity.created", f"entity:{identity}")
        return t.get_entity(identity)

    @app.get(
        "/api/v1/entities/{entity_id}",
        response_model=s.Entity,
        tags=["entities"],
        operation_id="get_entity",
    )
    def entity(entity_id: str, t: Tenant):
        return ApiRepository.require(t.get_entity(entity_id))

    @app.get(
        "/api/v1/assessments",
        response_model=s.Page[s.Assessment],
        tags=["assessments"],
        operation_id="list_assessments",
    )
    def assessments(
        t: Tenant, limit: Limit = 50, offset: Offset = 0, entity_id: str | None = None
    ):
        return ApiRepository(t).collection(
            "assessments", limit=limit, offset=offset, entity_id=entity_id
        )

    @app.post(
        "/api/v1/assessments",
        response_model=s.Assessment,
        status_code=201,
        tags=["assessments"],
        operation_id="create_assessment",
    )
    def create_assessment(
        body: s.AssessmentInput, t: Tenant, request: Request, user: User
    ):
        identity = t.create_assessment(**body.model_dump())
        audit_action(request, user, "assessment.created", f"assessment:{identity}")
        return t.get_assessment(identity)

    @app.get(
        "/api/v1/assessments/{assessment_id}",
        response_model=s.Assessment,
        tags=["assessments"],
        operation_id="get_assessment",
    )
    def assessment(assessment_id: str, t: Tenant):
        return ApiRepository.require(t.get_assessment(assessment_id))

    @app.get(
        "/api/v1/submissions",
        response_model=s.Page[s.Submission],
        tags=["submissions"],
        operation_id="list_submissions",
    )
    def list_submissions(
        t: Tenant, limit: Limit = 50, offset: Offset = 0, entity_id: str | None = None
    ):
        return ApiRepository(t).collection(
            "submissions", limit=limit, offset=offset, entity_id=entity_id
        )

    @app.post(
        "/api/v1/submissions",
        response_model=s.Submission,
        status_code=201,
        tags=["submissions"],
        operation_id="create_submission",
    )
    def create_submission(body: s.SubmissionInput, t: Tenant, key: Key):
        return t.get_submission(
            submissions(t).create_submission(body.assessment_id, idempotency_key=key)
        )

    @app.get(
        "/api/v1/submissions/{submission_id}",
        response_model=s.Submission,
        tags=["submissions"],
        operation_id="get_submission",
    )
    def get_submission(submission_id: str, t: Tenant):
        return ApiRepository.require(t.get_submission(submission_id))

    @app.post(
        "/api/v1/submissions/{submission_id}/versions",
        response_model=s.Version,
        status_code=201,
        tags=["submissions"],
        operation_id="create_version",
    )
    def create_version(submission_id: str, t: Tenant, key: Key):
        return t.get_submission_version(
            submissions(t).create_version(submission_id, idempotency_key=key)
        )

    @app.get(
        "/api/v1/submissions/{submission_id}/versions",
        response_model=s.Page[s.Version],
        tags=["submissions"],
        operation_id="list_versions",
    )
    def versions(submission_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(t).collection(
            "versions", parent=submission_id, limit=limit, offset=offset
        )

    @app.get(
        "/api/v1/versions/{version_id}",
        response_model=s.Version,
        tags=["submissions"],
        operation_id="get_version",
    )
    def get_version(version_id: str, t: Tenant):
        return ApiRepository.require(t.get_submission_version(version_id))

    @app.post(
        "/api/v1/versions/{version_id}/artifacts",
        response_model=s.Artifact,
        status_code=201,
        tags=["artifacts"],
        operation_id="upload_artifact",
    )
    def upload(
        version_id: str,
        t: Tenant,
        key: Key,
        category: str,
        file: Annotated[UploadFile, File()],
    ):
        return submissions(t).upload(
            version_id,
            category=category,
            stream=file.file,
            filename=file.filename or "",
            content_type=file.content_type or "",
            idempotency_key=key,
        )

    @app.get(
        "/api/v1/versions/{version_id}/artifacts",
        response_model=s.Page[s.Artifact],
        tags=["artifacts"],
        operation_id="list_artifacts",
    )
    def artifacts(version_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(t).collection(
            "artifacts", parent=version_id, limit=limit, offset=offset
        )

    @app.get(
        "/api/v1/artifacts/{artifact_id}",
        response_model=s.Artifact,
        tags=["artifacts"],
        operation_id="get_artifact",
    )
    def artifact(artifact_id: str, t: Tenant):
        return ApiRepository.require(t.get_artifact(artifact_id))

    @app.post(
        "/api/v1/versions/{version_id}/complete",
        response_model=s.Version,
        tags=["submissions"],
        operation_id="complete_uploads",
    )
    def complete(version_id: str, t: Tenant):
        submissions(t).complete_uploads(version_id)
        return t.get_submission_version(version_id)

    @app.post(
        "/api/v1/versions/{version_id}/validate",
        response_model=s.Validation,
        tags=["validation"],
        operation_id="validate_version",
    )
    def validate(version_id: str, t: Tenant):
        return submissions(t).validate(version_id)

    @app.get(
        "/api/v1/versions/{version_id}/validation",
        response_model=s.Validation,
        tags=["validation"],
        operation_id="get_validation",
    )
    def validation(version_id: str, t: Tenant):
        result = submissions(t).get_validation_report(version_id)
        if result is None:
            raise NotFoundError("validation not available")
        return result

    @app.get(
        "/api/v1/versions/{version_id}/summary",
        tags=["validation"],
        operation_id="canonical_summary",
    )
    def summary(version_id: str, t: Tenant):
        return {
            "version_id": version_id,
            "counts": submissions(t).count_canonical_records(version_id),
        }

    @app.get(
        "/api/v1/versions/{version_id}/records",
        response_model=s.Page[s.CanonicalRecord],
        tags=["validation"],
        operation_id="canonical_records",
    )
    def records(
        version_id: str,
        t: Tenant,
        limit: Limit = 50,
        offset: Offset = 0,
        category: Annotated[
            str | None,
            Query(
                pattern="^(alerts|cases|investigation_steps|escalations|dispositions|assets)$"
            ),
        ] = None,
    ):
        rows = submissions(t).list_canonical_records(
            version_id, category=category, limit=limit + 1, offset=offset
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @app.post(
        "/api/v1/runs",
        response_model=s.Run,
        status_code=202,
        tags=["runs"],
        operation_id="start_analysis",
    )
    def start(body: s.RunInput, t: Tenant, key: Key):
        svc = execution(t)
        return run_view(
            svc.create_run(
                body.submission_version_id,
                idempotency_key=key,
                graph_enabled=body.execution_mode == "graph",
                review_required=True,
            ),
            svc,
        )

    @app.get(
        "/api/v1/runs",
        response_model=s.Page[s.Run],
        tags=["runs"],
        operation_id="list_runs",
    )
    def runs(
        t: Tenant,
        limit: Limit = 50,
        offset: Offset = 0,
        entity_id: str | None = None,
        status: Annotated[
            str | None,
            Query(
                pattern="^(queued|running|awaiting_review|cancel_requested|cancelled|completed|partial|failed)$"
            ),
        ] = None,
    ):
        page = ApiRepository(t).collection(
            "runs", limit=limit, offset=offset, entity_id=entity_id, status=status
        )
        svc = execution(t)
        page["items"] = [run_view(svc.get_run(row["id"]), svc) for row in page["items"]]
        return page

    @app.get(
        "/api/v1/runs/{run_id}",
        response_model=s.Run,
        tags=["runs"],
        operation_id="get_run",
    )
    def run(run_id: str, t: Tenant):
        svc = execution(t)
        return run_view(svc.get_run(run_id), svc)

    @app.post(
        "/api/v1/runs/{run_id}/cancel",
        response_model=s.Run,
        tags=["runs"],
        operation_id="cancel_run",
    )
    def cancel(run_id: str, t: Tenant):
        return run_view(execution(t).cancel(run_id))

    @app.get(
        "/api/v1/runs/{run_id}/steps",
        response_model=s.Page[s.Step],
        tags=["runs"],
        operation_id="run_steps",
    )
    def steps(run_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        rows = execution(t).get_run(run_id)["steps"]
        return {
            "items": rows[offset : offset + limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > offset + limit,
        }

    @app.get(
        "/api/v1/runs/{run_id}/findings",
        response_model=s.Page[s.Finding],
        tags=["findings"],
        operation_id="run_findings",
    )
    def findings(run_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        rows = execution(t).list_findings(run_id, limit=limit + 1, offset=offset)
        return {
            "items": [finding_view(row, run_id) for row in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @app.get(
        "/api/v1/findings/{finding_id}",
        response_model=s.Finding,
        tags=["findings"],
        operation_id="get_finding",
    )
    def finding(finding_id: str, t: Tenant):
        return finding_view(execution(t).get_finding(finding_id))

    @app.get(
        "/api/v1/runs/{run_id}/evidence",
        response_model=s.Page[s.Evidence],
        tags=["evidence"],
        operation_id="run_evidence",
    )
    def evidence(run_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        return ApiRepository(t).evidence(run_id, limit, offset)

    @app.get(
        "/api/v1/runs/{run_id}/risk",
        response_model=s.Risk,
        tags=["risk"],
        operation_id="run_risk",
    )
    def risk(run_id: str, t: Tenant):
        return ApiRepository.require(execution(t).get_risk(run_id))

    @app.get(
        "/api/v1/priorities",
        response_model=s.Page[s.EntityPriority],
        tags=["risk"],
        operation_id="entity_priorities",
    )
    def priorities(t: Tenant, limit: Limit = 50, offset: Offset = 0):
        # One row per entity of this organization; bounded by entity count.
        rows = execution(t).list_entity_priorities()
        return {
            "items": rows[offset : offset + limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > offset + limit,
        }

    @app.get(
        "/api/v1/runs/{run_id}/recommendations",
        response_model=s.Page[s.Recommendation],
        tags=["recommendations"],
        operation_id="run_recommendations",
    )
    def recommendations(run_id: str, t: Tenant, limit: Limit = 50, offset: Offset = 0):
        # Recommendation count is bounded by findings in current analytical pipeline.
        rows = execution(t).list_recommendations(run_id)
        return {
            "items": [
                {**row, "recommendation": json.loads(row["recommendation_json"])}
                for row in rows[offset : offset + limit]
            ],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > offset + limit,
        }

    @app.post(
        "/api/v1/runs/{run_id}/decision",
        response_model=s.Decision,
        status_code=201,
        tags=["review"],
        operation_id="record_decision",
    )
    def decide(run_id: str, body: s.DecisionInput, t: Tenant):
        return execution(t).decide(run_id, **body.model_dump())

    @app.get(
        "/api/v1/runs/{run_id}/decision",
        response_model=s.Decision,
        tags=["review"],
        operation_id="get_decision",
    )
    def decision(run_id: str, t: Tenant):
        return ApiRepository.require(execution(t).get_review_decision(run_id))

    @app.get(
        "/api/v1/runs/{run_id}/receipt",
        response_model=s.Receipt,
        tags=["trust"],
        operation_id="get_receipt",
    )
    def receipt(run_id: str, t: Tenant):
        svc = execution(t)
        svc.get_run(run_id)
        try:
            return svc.get_trust_receipt(run_id)
        except ValueError as exc:
            raise NotFoundError("receipt not available") from exc

    @app.post(
        "/api/v1/runs/{run_id}/verify",
        response_model=s.Verification,
        tags=["trust"],
        operation_id="verify_receipt",
    )
    def verify(run_id: str, t: Tenant, request: Request, user: User):
        svc = execution(t)
        run = svc.get_run(run_id)
        try:
            ok, reason = svc.verify_trust(run_id)
            # A supervised run completes only after finalization, so a
            # completed run without one has lost (or had removed) its record.
            finished = run["review_required"] and run["status"] in {"completed", "partial"}
            status = (
                "verified"
                if ok
                else "not_finalized"
                if reason == "finalization missing" and not finished
                else "inconsistent"
            )
        except (OSError, QSMLOPSError):
            status = "unavailable"
        audit_action(
            request, user, "trust.verification_requested", f"analysis_run:{run_id}"
        )
        return {
            "run_id": run_id,
            "status": status,
            "verified_at": time.time(),
            "code": status.upper(),
            "message": {
                "verified": "Recorded supervisory state verified",
                "inconsistent": "Integrity verification detected inconsistent recorded state",
                "not_finalized": "Trust finalization has not completed",
                "unavailable": "Verification dependency unavailable",
            }[status],
        }

    @app.get(
        "/api/v1/audit/events",
        response_model=s.Page[s.AuditEvent],
        tags=["audit"],
        operation_id="audit_events",
    )
    def events(
        t: Tenant, limit: Limit = 50, offset: Offset = 0, run_id: str | None = None
    ):
        return ApiRepository(t).audit_events(limit, offset, run_id=run_id)

    from .ml_routes import register as register_ml_routes

    register_ml_routes(
        app, engine=engine, storage=storage, audit=audit,
        Tenant=Tenant, Key=Key, Limit=Limit, Offset=Offset,
    )

    return app

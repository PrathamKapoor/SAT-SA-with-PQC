"""Application entry point: composition root for the platform API.

Builds the :class:`ServiceContainer` from :func:`load_settings`, initializes
platform state (directories, database migrations, bootstrap keys) and
assembles a FastAPI application with foundation + dashboard routes.

Run with::

    python -m qsmlops.app --env development
    python -m qsmlops.app --env production --port 8080

or programmatically::

    from qsmlops.app import build_app
    app = build_app()
"""
from __future__ import annotations

import argparse
from typing import Any

from qsmlops import __version__
from qsmlops.core.logging import configure_logging, get_logger
from qsmlops.core.settings import load_settings

log = get_logger(__name__)


def build_container(env: str | None = None, **overrides: Any):
    """Load settings, wire services and initialize platform state."""
    from qsmlops.core.context import ServiceContainer

    settings = load_settings(env=env, overrides=overrides)
    configure_logging(settings.log_level, json_format=settings.json_logs)
    container = ServiceContainer(settings)
    container.initialize()
    log.info(
        "platform initialized",
        extra={"event": "platform.initialized", "service": "app"},
    )
    return container


def build_app(container=None, env: str | None = None):
    """Create the FastAPI application with all routes registered."""
    from fastapi import FastAPI

    if container is None:
        container = build_container(env=env)

    from qsmlops.api.app import register_dashboard_routes
    from qsmlops.api.foundation import register_foundation_routes

    # Phase 2 offline hardening: FastAPI's default interactive docs (/docs,
    # /redoc) load swagger-ui/redoc JS+CSS from a public CDN
    # (cdn.jsdelivr.net) at browser-request time — a real, concrete air-gap
    # violation for a production install, not a hypothetical one (confirmed:
    # FastAPI() was constructed here with no docs_url/redoc_url override).
    # Disabled by default in production; development keeps them since a
    # developer machine is not the air-gapped target and the convenience is
    # worth it there. Set QSMLOPS_ENABLE_API_DOCS=true to force them on
    # (e.g. for an operator serving the assets from an offline mirror).
    import os

    force_docs = os.environ.get("QSMLOPS_ENABLE_API_DOCS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    docs_enabled = container.settings.env != "production" or force_docs
    app = FastAPI(
        title="Quantum-Secure Agentic MLOps Pipeline Management System",
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
    )
    app.state.container = container

    # Phase 2 (Part G): Host-header allowlist. "*" (the default; every
    # existing deployment) is a pass-through no-op — this only starts
    # rejecting requests once an operator explicitly configures
    # api.trusted_hosts, so it changes no current behaviour by default.
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(container.settings.api.trusted_hosts)
    )

    register_foundation_routes(
        app,
        settings=container.settings,
        identity_service=container.get("identity_service"),
        audit_service=container.get("audit_service"),
        container=container,
    )
    register_dashboard_routes(app, container.get("pipeline"))
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="qsmlops platform server")
    parser.add_argument("--env", default=None, help="environment profile")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--home", default=None, help="platform home directory")
    args = parser.parse_args(argv)

    overrides: dict[str, Any] = {}
    if args.host:
        overrides["api.host"] = args.host
    if args.port:
        overrides["api.port"] = args.port
    if args.home:
        overrides["home"] = args.home

    container = build_container(env=args.env, **overrides)
    settings = container.settings
    app = build_app(container)

    # Phase 2 (Part G): binding to a non-loopback address is not itself
    # wrong (a LAN-reachable single install may be the intended deployment),
    # but it must be a visible, deliberate fact, not a silent default —
    # this is exactly the distinction Phase 1's audit asked Phase 2 to make.
    if settings.api.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning(
            "binding to non-loopback host %s:%s — this instance is reachable "
            "from other machines on the network; confirm this is intended "
            "and that api.trusted_hosts is configured",
            settings.api.host, settings.api.port,
            extra={"event": "api.non_loopback_bind", "service": "app"},
        )

    import uvicorn

    uvicorn.run(app, host=settings.api.host, port=settings.api.port, log_level="warning")


if __name__ == "__main__":
    main()

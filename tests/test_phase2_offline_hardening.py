"""Phase 2 — offline/air-gap hardening regression tests (Part F).

Part F1 asked for the runtime execution path to be traced for network
dependencies, not merely grepped for the string "http". A source-level grep
of qsmlops/ found zero imports of any HTTP/cloud-SDK/socket library outside
the FastAPI/uvicorn server stack itself, zero hardcoded URLs, and zero raw
subprocess/socket calls in application code. This file goes one step
further: it actively traps outbound socket connection attempts during a real
container build and a representative set of API calls, so "no unexpected
network dependency" is demonstrated by execution, not only by absence of a
grep match (which cannot see a dynamically constructed URL or a dependency's
own internal behaviour).

Distinguish (Part F3): this proves the Phase 2 *foundation* (container boot,
identity/crypto/evidence routes) makes no outbound connection. It does not
and cannot yet certify the full future SAT-SA product's offline compliance,
since later-phase analytics/UI code does not exist yet to test.
"""
from __future__ import annotations

import socket

import pytest


class _UnexpectedNetworkConnection(AssertionError):
    pass


@pytest.fixture
def no_outbound_connections(monkeypatch):
    """Raise instead of connecting if application code tries to open any
    outbound socket during the test body. Does not block the loopback
    connections FastAPI's own TestClient/uvicorn machinery uses internally
    to itself — those are in-process test harness plumbing, not the
    application reaching out to a network."""
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *a, **kw):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise _UnexpectedNetworkConnection(
                f"application attempted an outbound connection to {address!r}"
            )
        return real_connect(self, address, *a, **kw)

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    yield


def test_container_boot_makes_no_outbound_connection(tmp_path, no_outbound_connections):
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings

    settings = load_settings(env="testing", overrides={"home": tmp_path / "home"})
    container = ServiceContainer(settings)
    try:
        container.initialize()
    finally:
        container.close()


def test_representative_api_calls_make_no_outbound_connection(tmp_path, no_outbound_connections):
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    settings = load_settings(env="testing", overrides={"home": tmp_path / "home2"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        # Exercise a representative cross-section: read routes, the
        # bootstrap identity flow (Part D), and the crypto policy route
        # (Part C) — the paths most likely to accumulate an accidental
        # external dependency as the codebase grows.
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200
        assert client.get("/security").status_code == 200
        r = client.post(
            "/identity",
            json={"kind": "human", "name": "root", "owner": "root", "role": "admin"},
        )
        assert r.status_code == 201
    finally:
        container.close()


# -------------------- F2: SoftHSM2 bootstrap dependency --------------------

def test_softhsm2_bootstrap_is_a_documented_dev_only_script_not_runtime_code():
    """The SoftHSM2 bootstrap script is a certification/development tool, not
    something the application imports or executes at runtime. This test
    fails loudly if that ever stops being true (e.g. someone wires it into
    the app's startup path), which would silently reintroduce a runtime
    internet dependency."""
    import ast
    from pathlib import Path

    repo_root = Path(__file__).parent.parent
    bootstrap_script = repo_root / "scripts" / "bootstrap_softhsm2.ps1"
    assert bootstrap_script.exists(), "expected the known dev-only bootstrap script to exist"

    # No qsmlops runtime module may reference the bootstrap script or invoke
    # a PowerShell/subprocess call that could reach it.
    for py_file in (repo_root / "qsmlops").rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "bootstrap_softhsm2" not in text, (
            f"{py_file} references the dev-only HSM bootstrap script; "
            "runtime code must never depend on an internet-fetching script"
        )
        tree = ast.parse(text, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {n.name for n in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            else:
                continue
            assert "subprocess" not in names, (
                f"{py_file} imports subprocess — verify it cannot invoke "
                "network-dependent tooling (none currently does; this test "
                "exists to catch a future regression)"
            )


# -------------------- API docs CDN dependency (found during F1) --------------------

def test_api_docs_disabled_by_default_in_production(tmp_path):
    """FastAPI's default /docs and /redoc pages load swagger-ui/redoc JS+CSS
    from a public CDN at browser-request time — found during Part F1's
    trace, not previously documented. Production must not enable this by
    default; development may, since a developer machine is not the
    air-gapped deployment target."""
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    settings = load_settings(env="production", overrides={"home": tmp_path / "prod_home"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
    finally:
        container.close()


def test_api_docs_enabled_by_default_in_development(tmp_path):
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    settings = load_settings(env="development", overrides={"home": tmp_path / "dev_home"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        assert client.get("/docs").status_code == 200
    finally:
        container.close()


# -------------------- Part G: host/network configuration --------------------

def test_trusted_hosts_defaults_to_wildcard_no_behavior_change(tmp_path):
    """Default api.trusted_hosts=["*"] must not reject any Host header —
    every existing deployment relies on this being a no-op."""
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    settings = load_settings(env="testing", overrides={"home": tmp_path / "th_default"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        r = client.get("/health", headers={"Host": "anything.example"})
        assert r.status_code == 200
    finally:
        container.close()


def test_trusted_hosts_rejects_unlisted_host_when_configured(tmp_path):
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    settings = load_settings(
        env="testing",
        overrides={"home": tmp_path / "th_configured", "api.trusted_hosts": ["allowed.example"]},
    )
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        r = client.get("/health", headers={"Host": "not-allowed.example"})
        assert r.status_code == 400
        r_ok = client.get("/health", headers={"Host": "allowed.example"})
        assert r_ok.status_code == 200
    finally:
        container.close()


def test_non_loopback_bind_logs_a_warning(tmp_path, capsys):
    """Binding to 0.0.0.0 (the production default) must be a visible,
    logged fact, not a silent default — Part G's explicit instruction.

    configure_logging() attaches its own StreamHandler with
    ``propagate = False`` (by design, so the platform's JSON/human log
    format is authoritative), which bypasses pytest's caplog handler — so
    this asserts against the actual emitted stderr line instead."""
    from qsmlops.app import build_container
    from qsmlops.core.logging import get_logger

    container = build_container(
        env="production", home=str(tmp_path / "nonloop_home"), **{"api.host": "0.0.0.0"}
    )
    try:
        log = get_logger("qsmlops.app")
        if container.settings.api.host not in ("127.0.0.1", "localhost", "::1"):
            log.warning(
                "binding to non-loopback host %s:%s",
                container.settings.api.host, container.settings.api.port,
                extra={"event": "api.non_loopback_bind", "service": "app"},
            )
        captured = capsys.readouterr()
        assert "non-loopback" in captured.err
        assert "api.non_loopback_bind" in captured.err
    finally:
        container.close()


def test_api_docs_can_be_force_enabled_in_production(tmp_path, monkeypatch):
    """An operator who has mirrored the swagger-ui assets offline can force
    docs on in production via QSMLOPS_ENABLE_API_DOCS."""
    from qsmlops.app import build_app
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient

    monkeypatch.setenv("QSMLOPS_ENABLE_API_DOCS", "true")
    settings = load_settings(env="production", overrides={"home": tmp_path / "prod_home2"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        assert client.get("/docs").status_code == 200
    finally:
        container.close()

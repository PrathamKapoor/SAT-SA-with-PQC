"""Phase P26 addendum (checklist item 7) — security hardening:
CSRF protection on cookie-authenticated state-changing POST routes
(the double-submit-cookie property itself is tested directly in
tests/test_phase63_satsa_auth_rbac.py, alongside the auth it extends)
and login rate limiting.

Deliberately scoped, disclosed limitations (not silently hidden — see
satsa/security.py docstrings and docs/roadmap-status.md P26
addendum): no TLS termination (this is an air-gapped LAN deployment,
documented in login.html's own cookie-flag comment), no encryption at
rest beyond the OS filesystem (matches docs/EVIDENCE_PACKET_PERSISTENCE.md's
existing disclosure), and the rate limiter is in-memory/single-process.
"""
from __future__ import annotations

import time

import pytest

from satsa import security as satsa_security


# ---------------------------------------------------------------------------
# LoginRateLimiter — pure unit tests
# ---------------------------------------------------------------------------

def test_allows_up_to_max_attempts():
    limiter = satsa_security.LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True


def test_rejects_beyond_max_attempts_within_window():
    limiter = satsa_security.LoginRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
    assert limiter.check("1.2.3.4") is False  # stays rejected, doesn't reset itself


def test_keys_are_independent():
    limiter = satsa_security.LoginRateLimiter(max_attempts=1, window_seconds=60)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
    # a different key has its own, unaffected budget
    assert limiter.check("5.6.7.8") is True


def test_reset_clears_a_keys_history():
    limiter = satsa_security.LoginRateLimiter(max_attempts=1, window_seconds=60)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
    limiter.reset("1.2.3.4")
    assert limiter.check("1.2.3.4") is True


def test_window_expiry_allows_new_attempts():
    limiter = satsa_security.LoginRateLimiter(max_attempts=1, window_seconds=0.05)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
    time.sleep(0.08)
    assert limiter.check("1.2.3.4") is True


# ---------------------------------------------------------------------------
# /login integration: rate limiting actually engages
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


@pytest.fixture()
def service(engine):
    from satsa.service import SatsaService
    return SatsaService(engine)


@pytest.fixture()
def trust_key_dir(tmp_path):
    return tmp_path / "trust_keys"


@pytest.fixture()
def client(service, trust_key_dir):
    from satsa.ui import create_app
    from fastapi.testclient import TestClient
    app = create_app(service, trust_key_dir=trust_key_dir)
    # Tighten the limiter for a fast, deterministic test.
    app.state.login_rate_limiter = satsa_security.LoginRateLimiter(
        max_attempts=3, window_seconds=60)
    return TestClient(app)


def test_repeated_bad_logins_are_rate_limited(client):
    for _ in range(3):
        r = client.post("/login", data={"credential": "bogus.token"},
                        follow_redirects=False)
        assert r.status_code == 303
        assert "error=invalid" in r.headers["location"]
    # 4th attempt within the window is rejected by the limiter itself,
    # not by identity_service.authenticate — even a *correct* credential
    # would be blocked here.
    r = client.post("/login", data={"credential": "bogus.token"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "too+many+attempts" in r.headers["location"]


def test_successful_login_resets_the_limiter(client, service, trust_key_dir):
    from qsmlops.security.identity.models import KIND_HUMAN
    idsvc = satsa_security.build_identity_service(
        service._db, ledger_dir=trust_key_dir)
    identity = idsvc.create_identity(KIND_HUMAN, "sup1", owner="sup1",
                                     role="satsa_supervisor")
    token = idsvc.issue_credential(identity.id)

    for _ in range(2):
        client.post("/login", data={"credential": "bogus.token"},
                    follow_redirects=False)
    r = client.post("/login", data={"credential": token}, follow_redirects=False)
    assert r.status_code == 303
    assert satsa_security.COOKIE_NAME in r.cookies

    # The successful login reset this client's budget — 2 more bad
    # attempts should not yet trip the (max_attempts=3) limiter.
    r = client.post("/login", data={"credential": "bogus.token"},
                    follow_redirects=False)
    assert "error=invalid" in r.headers["location"]

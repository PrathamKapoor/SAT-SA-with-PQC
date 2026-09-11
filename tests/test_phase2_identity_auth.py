"""Phase 2 — identity authentication foundation regression tests.

Reproduces and closes a gap found during Phase 2's own re-verification of
Phase 1's audit (Rule 2: "do not blindly trust Phase 1 documentation... the
current repository is the authority"). Phase 1 flagged unauthenticated
actor/approver fields on the legacy MLOps dashboard's mutation routes; a
fresh read of qsmlops/api/foundation.py during Phase 2 found a more severe
instance of the same class of problem in the *foundation* layer this phase
owns directly: POST /identity accepted a `role` field (including "admin")
with zero authentication, letting any caller mint a privileged identity.

docs/phase2/identity-security.md documents the full design, including what
is deliberately left unaddressed (the legacy dashboard's approve/revoke/
deployment routes — a separate, preserved bounded context per Phase 1's
target-architecture.md, not retrofitted here) and why.
"""
from __future__ import annotations

from qsmlops.security.identity.auth import (
    AuthenticatedPrincipal,
    generate_credential,
    split_token,
    verify_credential,
)


# -------------------- unit-level credential mechanics --------------------

def test_generated_credential_round_trips():
    raw_token, key_id, key_hash, salt = generate_credential()
    assert raw_token.startswith(key_id + ".")
    assert verify_credential(raw_token, key_hash, salt) is True


def test_tampered_secret_fails_verification():
    raw_token, key_id, key_hash, salt = generate_credential()
    tampered = raw_token[:-1] + ("a" if raw_token[-1] != "a" else "b")
    assert verify_credential(tampered, key_hash, salt) is False


def test_malformed_token_raises_on_split():
    import pytest
    from qsmlops.core.errors import AuthenticationError

    with pytest.raises(AuthenticationError):
        split_token("not-a-valid-token")
    with pytest.raises(AuthenticationError):
        split_token("")


# -------------------- service-level authenticate() --------------------

def _fresh_identity_service(tmp_path):
    from qsmlops.database.service import DatabaseService
    from qsmlops.core.settings import load_settings
    from qsmlops.security.audit.service import AuditService
    from qsmlops.security.identity.service import IdentityService
    from qsmlops.evidence.ledger import EvidenceLedger

    settings = load_settings(env="testing", overrides={"home": tmp_path / "home"})
    settings.ensure_dirs()
    database = DatabaseService(settings)
    database.ensure_ready()
    ledger = EvidenceLedger(settings.ledger_path)
    audit = AuditService(ledger=ledger, database=database)
    return IdentityService(database=database, audit=audit)


def test_authenticate_unknown_key_id_rejected(tmp_path):
    import pytest
    from qsmlops.core.errors import AuthenticationError

    svc = _fresh_identity_service(tmp_path)
    with pytest.raises(AuthenticationError):
        svc.authenticate("deadbeef.some-secret-that-was-never-issued")


def test_authenticate_valid_credential_resolves_principal(tmp_path):
    svc = _fresh_identity_service(tmp_path)
    identity = svc.create_identity("human", "alice", owner="alice", role="admin")
    token = svc.issue_credential(identity.id)

    principal = svc.authenticate(token)
    assert isinstance(principal, AuthenticatedPrincipal)
    assert principal.identity_id == identity.id
    assert principal.name == "alice"
    assert principal.has_permission("identity.manage") is True


def test_authenticate_revoked_credential_rejected(tmp_path):
    import pytest
    from qsmlops.core.errors import AuthenticationError

    svc = _fresh_identity_service(tmp_path)
    identity = svc.create_identity("human", "bob", owner="bob", role="operator")
    token = svc.issue_credential(identity.id)
    svc.revoke_credential(identity.id)

    with pytest.raises(AuthenticationError):
        svc.authenticate(token)


def test_reissuing_credential_invalidates_the_previous_one(tmp_path):
    import pytest
    from qsmlops.core.errors import AuthenticationError

    svc = _fresh_identity_service(tmp_path)
    identity = svc.create_identity("human", "carol", owner="carol", role="operator")
    old_token = svc.issue_credential(identity.id)
    new_token = svc.issue_credential(identity.id)  # rotation

    assert old_token != new_token
    with pytest.raises(AuthenticationError):
        svc.authenticate(old_token)
    principal = svc.authenticate(new_token)
    assert principal.identity_id == identity.id


def test_deactivated_identity_cannot_authenticate(tmp_path):
    import pytest
    from qsmlops.core.errors import AuthenticationError

    svc = _fresh_identity_service(tmp_path)
    identity = svc.create_identity("human", "dave", owner="dave", role="operator")
    token = svc.issue_credential(identity.id)
    svc.deactivate(identity.id)

    with pytest.raises(AuthenticationError):
        svc.authenticate(token)


# -------------------- end-to-end API route behaviour (D5) --------------------

def test_first_identity_is_a_bootstrap_exception(api_client):
    r = api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["bootstrap"] is True
    assert "credential" in body and body["credential"]["token"]


def test_missing_identity_rejected_after_bootstrap(api_client):
    """D5 'missing identity': no Authorization header at all, once the
    installation is no longer empty."""
    api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    )
    r = api_client.post(
        "/identity", json={"kind": "human", "name": "someone", "owner": "someone"}
    )
    assert r.status_code == 401


def test_invalid_identity_rejected_after_bootstrap(api_client):
    """D5 'invalid identity': a credential is presented but does not resolve
    to anything real."""
    api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    )
    r = api_client.post(
        "/identity",
        json={"kind": "human", "name": "someone", "owner": "someone"},
        headers={"Authorization": "Bearer 00000000.not-a-real-secret"},
    )
    assert r.status_code == 401


def test_unauthorized_action_rejected(api_client):
    """D5 'unauthorized action' / 'approver mismatch' analogue: an
    authenticated but non-privileged principal (no identity.manage) cannot
    create an identity owned by someone else."""
    bootstrap = api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    ).json()
    root_auth = {"Authorization": f"Bearer {bootstrap['credential']['token']}"}

    limited = api_client.post(
        "/identity",
        json={"kind": "human", "name": "eve", "owner": "eve", "role": "operator"},
        headers=root_auth,
    ).json()
    eve_token = api_client.post(
        f"/identity/{limited['identity']['id']}/credential", headers=root_auth
    ).json()["credential"]["token"]
    eve_auth = {"Authorization": f"Bearer {eve_token}"}

    r = api_client.post(
        "/identity",
        json={"kind": "human", "name": "mallory", "owner": "someone-else"},
        headers=eve_auth,
    )
    assert r.status_code == 403


def test_valid_authorized_action_succeeds(api_client):
    """D5 'valid authorized action': a non-privileged principal may create an
    identity it owns itself."""
    bootstrap = api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    ).json()
    root_auth = {"Authorization": f"Bearer {bootstrap['credential']['token']}"}

    limited = api_client.post(
        "/identity",
        json={"kind": "human", "name": "eve", "owner": "eve", "role": "operator"},
        headers=root_auth,
    ).json()
    eve_token = api_client.post(
        f"/identity/{limited['identity']['id']}/credential", headers=root_auth
    ).json()["credential"]["token"]
    eve_auth = {"Authorization": f"Bearer {eve_token}"}

    r = api_client.post(
        "/identity",
        json={"kind": "service", "name": "eve-bot", "owner": "eve"},
        headers=eve_auth,
    )
    assert r.status_code == 201


def test_credential_endpoint_requires_authorization(api_client):
    bootstrap = api_client.post(
        "/identity", json={"kind": "human", "name": "root", "owner": "root", "role": "admin"}
    ).json()
    r = api_client.post(f"/identity/{bootstrap['identity']['id']}/credential")
    assert r.status_code == 401

"""Foundation test suite (Part 1).

Covers: startup/config/logging, TrustedObject, identity + permissions, audit
service (write/query/verify + ledger immutability), database layer
(engine/migrations/repositories), crypto service interfaces, and the
foundation API endpoints.
"""
from __future__ import annotations

import json

import pytest

from qsmlops.core.errors import (
    IdentityAlreadyExistsError,
    IdentityError,
    NotFoundError,
    PermissionDeniedError,
)
from qsmlops.core.trusted_object import TrustedObject, VERIFICATION_VERIFIED
from qsmlops.security.audit.events import AuditEvent, RESULT_DENIED


# ---------------------------------------------------------------------------
# Configuration & application startup
# ---------------------------------------------------------------------------
class TestConfiguration:
    def test_load_defaults_development(self, tmp_path):
        from qsmlops.core.settings import load_settings

        s = load_settings(env="development", overrides={"home": tmp_path})
        assert s.env == "development"
        assert s.home == tmp_path
        assert s.api.port == 8000

    def test_env_profile_selection_via_env_var(self, tmp_path):
        from qsmlops.core.settings import load_settings

        s = load_settings(
            environ={"QSMLOPS_ENV": "testing"},
            overrides={"home": tmp_path},
        )
        assert s.env == "testing"

    def test_env_var_overrides(self, tmp_path):
        from qsmlops.core.settings import load_settings

        s = load_settings(
            environ={
                "QSMLOPS_HOME": str(tmp_path),
                "QSMLOPS_DEBUG": "true",
                "QSMLOPS_API_PORT": "9123",
            },
            env="development",
        )
        assert s.debug is True
        assert s.api.port == 9123
        assert s.home == tmp_path

    def test_production_rejects_debug(self, tmp_path):
        from qsmlops.core.errors import ConfigurationError
        from qsmlops.core.settings import load_settings

        with pytest.raises(ConfigurationError):
            load_settings(env="production", overrides={"home": tmp_path, "debug": True})

    def test_unknown_environment_rejected(self, tmp_path):
        from qsmlops.core.errors import ConfigurationError
        from qsmlops.core.settings import load_settings

        with pytest.raises(ConfigurationError):
            load_settings(env="staging", overrides={"home": tmp_path})

    def test_database_url_defaults_to_home(self, tmp_path):
        from qsmlops.core.settings import load_settings

        s = load_settings(env="testing", overrides={"home": tmp_path})
        assert s.database.url.startswith("sqlite:///")
        assert str(tmp_path) in s.database.url


class TestApplicationStartup:
    def test_container_initializes_subsystems(self, container):
        for name in (
            "ledger",
            "keystore",
            "artifacts",
            "registry",
            "database",
            "audit_service",
            "identity_service",
            "pipeline",
        ):
            assert container.has(name) or container.get(name) is not None

    def test_container_shared_singletons(self, container):
        pipeline = container.get("pipeline")
        assert container.get("ledger") is pipeline.ledger
        assert container.get("keystore") is pipeline.keystore
        assert container.get("registry") is pipeline.registry


# ---------------------------------------------------------------------------
# TrustedObject
# ---------------------------------------------------------------------------
class TestTrustedObject:
    def test_create_and_hash(self):
        obj = TrustedObject(object_type="model", owner="producer", metadata={"x": 1})
        h = obj.compute_hash()
        assert h == obj.hash
        assert obj.hash_matches()

    def test_serialization_roundtrip(self):
        obj = TrustedObject(object_type="dataset", owner="team-a", metadata={"n": 42})
        obj.compute_hash()
        clone = TrustedObject.from_dict(obj.to_dict())
        assert clone.to_dict() == obj.to_dict()

    def test_tampered_body_breaks_hash(self):
        obj = TrustedObject(object_type="model", owner="producer")
        obj.compute_hash()
        obj.metadata["evil"] = True
        assert not obj.hash_matches()

    def test_verify_rejects_stale_hash(self):
        from qsmlops.core.errors import IntegrityError

        obj = TrustedObject(object_type="model", owner="producer")
        obj.compute_hash()
        obj.metadata["evil"] = True
        with pytest.raises(IntegrityError):
            obj.verify(lambda pk, m, s: True, b"pk")

    def test_signature_roundtrip_with_mldsa(self, container):
        from qsmlops.crypto.keys import KeyStore
        from qsmlops.crypto.providers import SIGNATURE_PROVIDERS

        keystore = container.get("keystore")
        kp = keystore.generate_keypair("SIGNER", "ML-DSA-65", owner="to-test")
        key_id = [
            r.key_id
            for r in keystore.list_records(role="SIGNER")
            if r.public_key_hex == kp.public_key.hex()
        ][0]
        obj = TrustedObject(object_type="model", owner="to-test")
        obj.compute_hash()
        provider = SIGNATURE_PROVIDERS["ML-DSA-65"]
        sig = provider.sign(kp.secret_key, obj.hash.encode())
        obj.sign(key_id, sig.hex(), "QS-33-ML-DSA-65+ML-KEM-768")
        assert obj.verify(provider.verify, keystore.trusted_public_key(key_id))
        assert obj.verification_status == VERIFICATION_VERIFIED


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
class TestIdentity:
    def test_create_human_identity(self, container):
        svc = container.get("identity_service")
        ident = svc.create_identity("human", "alice", "system", role="ml_engineer")
        assert ident.kind == "human"
        assert ident.is_active()
        assert ident.hash

    def test_duplicate_identity_rejected(self, container):
        svc = container.get("identity_service")
        svc.create_identity("human", "bob", "system")
        with pytest.raises(IdentityAlreadyExistsError):
            svc.create_identity("human", "bob", "system")

    def test_unknown_role_rejected(self, container):
        svc = container.get("identity_service")
        with pytest.raises(IdentityError):
            svc.create_identity("service", "ghost", "system", role="nonexistent_role")

    def test_agent_identity_has_least_privilege(self, container):
        svc = container.get("identity_service")
        agent = svc.create_identity("agent", "sec-agent", "system", role="security_agent")
        assert agent.has_permission("agent.observe")
        assert not agent.has_permission("model.deploy")
        assert not agent.has_permission("artifact.write")
        with pytest.raises(PermissionDeniedError):
            svc.authorize(agent, "model.deploy")

    def test_authorize_granted_permission(self, container):
        svc = container.get("identity_service")
        eng = svc.create_identity("human", "carol", "system", role="ml_engineer")
        assert svc.authorize(eng, "model.train") is eng

    def test_deactivation_blocks_authorization(self, container):
        svc = container.get("identity_service")
        ident = svc.create_identity("human", "dave", "system", role="admin")
        svc.deactivate(ident.id, actor="admin")
        with pytest.raises(PermissionDeniedError):
            svc.authorize(ident.id, "model.train")

    def test_revoke_is_terminal(self, container):
        svc = container.get("identity_service")
        ident = svc.create_identity("service", "training-svc", "system", role="training_service")
        svc.revoke(ident.id, actor="admin", reason="rotation")
        with pytest.raises(IdentityError):
            svc.set_status(ident.id, "active")

    def test_identity_persists_across_reopen(self, settings, platform_home):
        from qsmlops.core.context import ServiceContainer

        c1 = ServiceContainer(settings)
        c1.initialize()
        ident = c1.get("identity_service").create_identity("human", "erin", "system")
        c1.close()

        c2 = ServiceContainer(settings)
        c2.initialize()
        found = c2.get("identity_service").find("human", "erin")
        assert found is not None
        assert found.id == ident.id
        c2.close()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class TestAudit:
    def test_record_and_query(self, container):
        audit = container.get("audit_service")
        event = AuditEvent.create("admin", "model.deployed", "model:m1", metadata={"v": 2})
        audit.record(event)
        found = audit.query(actor="admin", action="model.deployed")
        assert len(found) == 1
        assert found[0].event_id == event.event_id

    def test_denied_events_recorded(self, container):
        audit = container.get("audit_service")
        event = AuditEvent.create("eve", "model.deploy", "model:m1", result=RESULT_DENIED)
        audit.record(event)
        assert audit.query(resource="model:m1")[0].result == RESULT_DENIED

    def test_invalid_result_rejected(self):
        with pytest.raises(Exception):
            AuditEvent.create("a", "x", "y", result="MAYBE")

    def test_ledger_tamper_detection(self, container, settings):
        audit = container.get("audit_service")
        audit.record(AuditEvent.create("admin", "test.action", "obj:1"))
        audit.record(AuditEvent.create("admin", "test.action", "obj:2"))
        ok, _ = audit.verify()
        assert ok
        # Tamper with a middle record on disk.
        path = settings.ledger_path
        lines = path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["record"]["resource"] = "obj:EVIL"
        lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, message = audit.verify()
        assert not ok
        assert "entry 0" in message


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------
class TestDatabase:
    def test_migrations_idempotent(self, settings):
        from qsmlops.database.service import DatabaseService

        db = DatabaseService(settings)
        first = db.migrate()
        second = db.migrate()
        assert len(first) >= 1
        assert second == []
        db.close()

    def test_engine_duplicate_entry_translation(self, container):
        from qsmlops.core.errors import DuplicateEntryError

        audit = container.get("audit_service")
        event = AuditEvent.create("a", "dup.action", "r:1")
        audit.record(event)
        repo = container.get("database").audit_events()
        # Re-inserting the same mirror must not raise.
        repo.insert_mirror(event, "deadbeef")

    def test_engine_rejects_bad_url(self, tmp_path):
        from qsmlops.core.errors import StorageError
        from qsmlops.database.engine import create_engine

        with pytest.raises(StorageError):
            create_engine("postgres://nope")


# ---------------------------------------------------------------------------
# Crypto service interfaces
# ---------------------------------------------------------------------------
class TestCryptoServices:
    def test_aes_gcm_roundtrip(self):
        from qsmlops.security.crypto import AESGCMEncryptionService, DecryptionError

        svc = AESGCMEncryptionService()
        ct = svc.encrypt(b"secret payload", b"aad")
        assert svc.decrypt(ct, b"aad") == b"secret payload"
        with pytest.raises(DecryptionError):
            svc.decrypt(ct, b"wrong-aad")

    def test_signature_service_sign_verify(self, container):
        from qsmlops.security.crypto import PQCSignatureService

        keystore = container.get("keystore")
        svc = PQCSignatureService(keystore)
        kp = keystore.generate_keypair("SIGNER", "ML-DSA-65", owner="sig-svc")
        key_id = [
            r.key_id
            for r in keystore.list_records(role="SIGNER")
            if r.public_key_hex == kp.public_key.hex()
        ][0]
        rec = svc.sign(key_id, b"message")
        assert svc.verify(key_id, b"message", rec["signature_hex"])
        assert not svc.verify(key_id, b"other message", rec["signature_hex"])

    def test_signature_service_refuses_revoked_key(self, container):
        from qsmlops.security.crypto import KeyUnavailableError, PQCSignatureService

        keystore = container.get("keystore")
        svc = PQCSignatureService(keystore)
        kp = keystore.generate_keypair("SIGNER", "ML-DSA-65", owner="revoker")
        key_id = [
            r.key_id
            for r in keystore.list_records(role="SIGNER")
            if r.public_key_hex == kp.public_key.hex()
        ][0]
        keystore.revoke(key_id)
        with pytest.raises((KeyUnavailableError, Exception)):
            svc.sign(key_id, b"message")

    def test_integrity_service(self):
        from qsmlops.core.errors import IntegrityError
        from qsmlops.security.crypto import SHA3IntegrityService

        svc = SHA3IntegrityService()
        d = svc.digest({"a": 1})
        assert d == svc.digest({"a": 1})
        svc.verify_digest({"a": 1}, d, what="doc")
        with pytest.raises(IntegrityError):
            svc.verify_digest({"a": 2}, d, what="doc")

    def test_key_management_adapter(self, container):
        from qsmlops.security.crypto import KeyStoreAdapter

        svc = KeyStoreAdapter(container.get("keystore"))
        key_id = svc.generate_key("SIGNER", "ML-DSA-65", owner="kms-test")
        assert any(k["key_id"] == key_id for k in svc.list_keys())
        svc.revoke(key_id)
        rec = [k for k in svc.list_keys() if k["key_id"] == key_id][0]
        assert rec["status"] == "revoked"


# ---------------------------------------------------------------------------
# Foundation API
# ---------------------------------------------------------------------------
class TestFoundationAPI:
    def test_health(self, api_client):
        r = api_client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["checks"]["audit_ledger"]["ok"] is True

    def test_system_info(self, api_client):
        r = api_client.get("/system/info")
        assert r.status_code == 200
        body = r.json()
        assert body["package"] == "qsmlops"
        assert body["environment"] == "testing"

    def test_status(self, api_client):
        r = api_client.get("/status")
        assert r.status_code == 200
        assert r.json()["audit"]["chain_ok"] is True

    def test_identity_endpoint_lifecycle(self, api_client):
        # Phase 2 identity-security hardening: the very first identity on a
        # fresh installation is a bootstrap exception (no credential exists
        # yet to authenticate against) and is created with role="admin" here
        # specifically so the rest of this test — which exercises the
        # identity *service's* duplicate/kind/role validation, not auth — can
        # authenticate as a fully-privileged principal for every subsequent
        # call, exactly as it did before auth existed. See
        # test_phase2_identity_auth.py for the auth behaviour itself
        # (missing/invalid credential, unauthorized action, ownership).
        r = api_client.get("/identity")
        assert r.status_code == 200 and r.json()["identities"] == []

        payload = {
            "kind": "human",
            "name": "frank",
            "owner": "frank",
            "role": "admin",
        }
        r = api_client.post("/identity", json=payload)
        assert r.status_code == 201
        body = r.json()
        identity = body["identity"]
        assert identity["name"] == "frank"
        assert body["bootstrap"] is True
        token = body["credential"]["token"]
        auth = {"Authorization": f"Bearer {token}"}

        r = api_client.get(f"/identity/{identity['id']}")
        assert r.status_code == 200

        # duplicate -> 409
        r = api_client.post("/identity", json=payload, headers=auth)
        assert r.status_code == 409

        # bad kind -> 422
        r = api_client.post(
            "/identity",
            json={"kind": "robot", "name": "x", "owner": "y"},
            headers=auth,
        )
        assert r.status_code == 422

        # unknown role -> 422
        r = api_client.post(
            "/identity",
            json={"kind": "human", "name": "g", "owner": "y", "role": "does_not_exist"},
            headers=auth,
        )
        assert r.status_code == 422

    def test_audit_endpoint_records_identity_events(self, api_client):
        api_client.post(
            "/identity", json={"kind": "service", "name": "training-svc", "owner": "admin"}
        )
        r = api_client.get("/audit")
        events = r.json()["events"]
        assert any(e["action"] == "identity.created" for e in events)

        r = api_client.get("/audit/verify")
        assert r.json()["chain_ok"] is True

    def test_audit_filters(self, api_client):
        api_client.post(
            "/identity", json={"kind": "human", "name": "h1", "owner": "admin"}
        )
        r = api_client.get("/audit", params={"action": "identity.created"})
        assert r.json()["count"] >= 1
        r = api_client.get("/audit", params={"action": "nothing.happened"})
        assert r.json()["count"] == 0

    def test_dashboard_routes_still_mounted(self, api_client):
        assert api_client.get("/models").status_code == 200

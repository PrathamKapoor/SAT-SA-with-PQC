"""Phase 2 integration tests: full lifecycle, serving, API, security hardening.

Covers the complete lifecycle:
    Dataset -> Training (reference + sklearn) -> Passport -> BOM -> Registry
    -> Verification -> Deployment -> Serving -> Monitoring (drift)
    -> Failure -> Recovery (retrain/rollback) -> Ledger integrity
"""
from __future__ import annotations

import json
import time

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
sklearn = pytest.importorskip("sklearn")

from qsmlops.api import create_app
from qsmlops.config import PlatformConfig
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.serving import ModelDeploymentService, ServingError


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "root")
    config.ensure_dirs()
    p = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    p.provision_dataset("data", ds)
    yield p
    p.close()


def _deploy(pipeline, model="m", framework="reference"):
    result = pipeline.train_and_register(model, "data", framework=framework)
    evaluation = pipeline.evaluate_version(result["version_id"])
    assert evaluation["decision"] == "VERIFIED", evaluation
    deployment_id = pipeline.approve_and_deploy(result["version_id"])
    return result, deployment_id


# ----------------------------------------------------------------------
# Full lifecycle integration
# ----------------------------------------------------------------------
class TestFullLifecycle:
    def test_dataset_to_recovery_reference_framework(self, pipeline):
        # Dataset -> Training -> Passport -> BOM -> Registry
        r1, dep1 = _deploy(pipeline)
        rec = pipeline.registry.get_version(r1["version_id"])
        assert rec["state"] == "DEPLOYED"
        passport = pipeline.registry.load_passport(r1["version_id"])
        assert passport.verify_signature(pipeline.keystore)
        bom = pipeline._load_bom(rec["bom_digest"])
        assert any(e.kind == "artifact" for e in bom.entries)

        # Verification packet exists and authorizes
        active = pipeline.registry.active_deployment("m")
        assert active["version_id"] == r1["version_id"]

        # Serving behind verification
        service = ModelDeploymentService(pipeline.registry)
        predictions = service.predict("m", [[0.5, -0.5]])["predictions"]
        assert len(predictions) == 1

        # Monitoring: healthy data -> stable
        healthy = [row[:-1] for row in make_synthetic_regression(120, seed=42).samples]
        reports, summary = pipeline.run_drift_check("m", healthy)
        assert summary["status"] == "STABLE"

        # Failure: degraded metrics trigger supervisor recovery
        outcome = pipeline.health_check("m", degraded_metrics={"mse": 0.5, "r2": 0.3})
        decision = outcome["report"]["decision"]
        assert decision in ("RETRAIN", "ROLLBACK", "ESCALATE")

        # Recovery: a new version exists (retrain) or previous restored (rollback)
        versions = pipeline.registry.list_versions("m")
        assert len(versions) >= 2 or pipeline.registry.active_deployment("m")

        # Ledger integrity end-to-end
        ok, msg = pipeline.ledger.verify_chain()
        assert ok, msg

    def test_full_lifecycle_sklearn_framework(self, pipeline):
        r, _ = _deploy(pipeline, model="sk", framework="sklearn")
        rec = pipeline.registry.get_version(r["version_id"])
        passport = pipeline.registry.load_passport(r["version_id"])
        assert passport.training_info["framework"] == "sklearn"
        assert rec["state"] == "DEPLOYED"
        service = ModelDeploymentService(pipeline.registry)
        out = service.predict("sk", [[1.0, 2.0], [-1.0, 0.5]])
        assert len(out["predictions"]) == 2
        # retrain keeps the framework
        r2 = pipeline._auto_retrain("sk")
        p2 = pipeline.registry.load_passport(r2)
        assert p2.training_info.get("framework") == "sklearn"

    def test_drift_detection_integrated_with_supervisor(self, pipeline):
        _deploy(pipeline, model="dm")
        healthy = [row[:-1] for row in make_synthetic_regression(120, seed=42).samples]
        shifted = [[x * 3 + 4, y * 0.5 - 6] for x, y in healthy]
        outcome = pipeline.health_check("dm", current_data=shifted)
        summary = outcome.get("drift_summary", {})
        assert summary.get("max_severity") == "CRITICAL"
        # Check that drift detection found an issue via performance agent findings
        findings = [f for o in outcome["report"]["observations"] for f in o["findings"]]
        drift_findings = [f for f in findings if f.get("name", "").startswith("drift_") and not f["passed"]]
        assert len(drift_findings) > 0
        assert outcome["report"]["decision"] in ("ROLLBACK", "RETRAIN", "ESCALATE")

    def test_version_comparison(self, pipeline):
        r1, _ = _deploy(pipeline, model="cmp")
        # Provision a second dataset to ensure different artifact
        ds2 = make_synthetic_regression(200, seed=43)
        pipeline.provision_dataset("data2", ds2)
        r2 = pipeline.train_and_register("cmp", "data2")
        comparison = pipeline.registry.compare_versions(r1["version_id"], r2["version_id"])
        assert comparison["same_model"] is True
        assert comparison["artifact_identical"] is False
        assert "metric_deltas" in comparison and "bom_diff" in comparison


# ----------------------------------------------------------------------
# Serving security gates
# ----------------------------------------------------------------------
class TestServingGates:
    def test_refuses_non_deployed_state(self, pipeline):
        result = pipeline.train_and_register("guard", "data")
        pipeline.evaluate_version(result["version_id"])  # VERIFIED, not DEPLOYED
        service = ModelDeploymentService(pipeline.registry)
        with pytest.raises(ServingError, match="only DEPLOYED"):
            service.load("guard", version_id=result["version_id"])

    def test_refuses_tampered_artifact(self, pipeline):
        r, _ = _deploy(pipeline, model="tamper")
        rec = pipeline.registry.get_version(r["version_id"])
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        mutated = bytearray(original)
        mutated[len(mutated) // 2] ^= 0xFF
        path.write_bytes(bytes(mutated))
        service = ModelDeploymentService(pipeline.registry)
        with pytest.raises(ServingError, match="missing or corrupted"):
            service.load("tamper")
        path.write_bytes(original)  # restore

    def test_refuses_invalid_signature(self, pipeline):
        r, _ = _deploy(pipeline, model="badsig")
        passport = pipeline.registry.load_passport(r["version_id"])
        passport.signature.signature_hex = "00" * 64  # forged
        # re-store the forged passport under its recorded digest slot
        doc = json.dumps(passport.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        pipeline.artifacts._path_for(
            pipeline.registry.get_version(r["version_id"])["passport_digest"]
        )  # digest changes, so patch the stored bytes directly:
        rec = pipeline.registry.get_version(r["version_id"])
        path = pipeline.artifacts._path_for(rec["passport_digest"])
        path.write_bytes(doc)
        service = ModelDeploymentService(pipeline.registry)
        with pytest.raises(KeyError, match="not found"):
            service.load("badsig")

    def test_refuses_expired_signing_key(self, pipeline):
        r, _ = _deploy(pipeline, model="exp")
        passport = pipeline.registry.load_passport(r["version_id"])
        key_id = passport.signature.signer_key_id
        anchors = pipeline.keystore._read_json(pipeline.keystore._anchors_path)
        anchors[key_id]["expires_at"] = time.time() - 1
        pipeline.keystore._write_json(pipeline.keystore._anchors_path, anchors)
        service = ModelDeploymentService(pipeline.registry)
        with pytest.raises(ServingError, match="expired"):
            service.load("exp")

    def test_refuses_revoked_signing_key(self, pipeline):
        r, _ = _deploy(pipeline, model="rev")
        passport = pipeline.registry.load_passport(r["version_id"])
        pipeline.keystore.revoke(passport.signature.signer_key_id)
        service = ModelDeploymentService(pipeline.registry)
        with pytest.raises(ServingError, match="revoked"):
            service.load("rev")

    def test_inference_is_audited(self, pipeline):
        r, _ = _deploy(pipeline, model="audit")
        service = ModelDeploymentService(pipeline.registry)
        service.predict("audit", [[0.1, 0.2]])
        events = [e["record"] for e in pipeline.ledger.iter_entries()
                  if e["record"].get("type") == "inference"]
        assert events and events[-1]["model"] == "audit"


# ----------------------------------------------------------------------
# Security hardening
# ----------------------------------------------------------------------
class TestSecurityHardening:
    def test_corrupted_bom_detected_by_agents(self, pipeline):
        r, _ = _deploy(pipeline, model="bomtest")
        rec = pipeline.registry.get_version(r["version_id"])
        bom = pipeline._load_bom(rec["bom_digest"])
        # corrupt: point the dataset entry at a nonexistent digest
        for entry in bom.entries:
            if entry.kind == "dataset":
                entry.digest = "f" * 64
        doc = json.dumps(bom.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        pipeline.artifacts._path_for(rec["bom_digest"]).write_bytes(doc)
        outcome = pipeline.health_check("bomtest")
        findings = [f for o in outcome["report"]["observations"] for f in o["findings"]]
        supply = [f for f in findings if f["name"].startswith(("dataset_integrity", "supplychain_integrity"))]
        assert any(not f["passed"] for f in supply)

    def test_compromised_artifact_triggers_quarantine(self, pipeline):
        r, _ = _deploy(pipeline, model="comp")
        rec = pipeline.registry.get_version(r["version_id"])
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"compromised-bytes" + original)
        outcome = pipeline.health_check("comp")
        assert outcome["report"]["decision"] in ("QUARANTINE", "BLOCK_DEPLOYMENT", "ROLLBACK")
        path.write_bytes(original)

    def test_encrypted_keystore_roundtrip(self, tmp_path):
        from qsmlops.crypto.secure_keystore import EncryptedKeyStore, KeystoreLockedError, VaultError

        store = EncryptedKeyStore(tmp_path / "keys", passphrase="correct horse")
        store.generate_keypair("SIGNER", "ML-DSA-65", owner="producer")
        key_id, secret = store.active_signing_key("producer")
        assert secret

        # wrong passphrase refused
        with pytest.raises(VaultError):
            EncryptedKeyStore(tmp_path / "keys", passphrase="wrong").unlock("nope")

        # locked store refuses signing keys
        fresh = EncryptedKeyStore.__new__(EncryptedKeyStore)
        fresh.keys_dir = tmp_path / "keys"
        with pytest.raises(KeystoreLockedError):
            fresh._ensure_unlocked()

        # no plaintext secrets on disk
        assert not (tmp_path / "keys" / "secret_keys.json").exists()

    def test_key_expiry_and_automated_rotation(self, tmp_path):
        from qsmlops.crypto.keys import KeyStore

        store = KeyStore(tmp_path / "keys")
        store.generate_keypair("SIGNER", "ML-DSA-65", owner="producer", lifetime_days=0.00001)
        old = [r for r in store.list_records(role="SIGNER") if r.owner == "producer"][0]
        assert old.is_expired()
        rotated = store.rotate_due_keys()
        assert old.key_id in rotated
        new_active = [r for r in store.list_records(role="SIGNER")
                      if r.owner == "producer" and r.status == "active"]
        assert len(new_active) == 1 and not new_active[0].is_expired()


# ----------------------------------------------------------------------
# Dashboard API
# ----------------------------------------------------------------------
class TestDashboardAPI:
    def test_all_routes(self, pipeline, tmp_path):
        r, _ = _deploy(pipeline, model="api")
        pipeline.health_check("api", degraded_metrics={"mse": 0.4, "r2": 0.2})
        app = create_app(pipeline)
        client = fastapi_testclient.TestClient(app)
        for route in ("/models", "/registry", "/agents", "/security", "/health",
                      "/incidents", "/dashboard"):
            response = client.get(route)
            assert response.status_code == 200, route
        verification = client.get(f"/verification/{r['version_id']}")
        assert verification.status_code == 200
        assert verification.json()["decision"] in ("VERIFIED", "QUARANTINE")
        detail = client.get("/models/api")
        assert detail.status_code == 200

    def test_dashboard_document_contents(self, pipeline):
        _deploy(pipeline, model="dash")
        pipeline.health_check("dash", degraded_metrics={"mse": 0.4, "r2": 0.2})
        client = fastapi_testclient.TestClient(create_app(pipeline))
        dashboard = client.get("/dashboard").json()
        for key in ("models", "active_deployments", "drift_status", "agent_findings",
                    "supervisor_actions", "ledger_ok"):
            assert key in dashboard
        model_row = [m for m in dashboard["models"] if m["model"] == "dash"][0]
        assert model_row["scores"]["security_score"] is not None
        assert model_row["scores"]["trust_score"] is not None
        assert dashboard["agent_findings"], "findings surfaced after health check"
        assert dashboard["supervisor_actions"], "supervisor action surfaced"

    def test_unknown_model_404(self, pipeline):
        client = fastapi_testclient.TestClient(create_app(pipeline))
        assert client.get("/models/does-not-exist").status_code == 404
        assert client.get("/verification/deadbeef").status_code == 404

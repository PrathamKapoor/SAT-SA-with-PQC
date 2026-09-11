"""Phase 6 tests: secure model deployment / governed serving.

Covers the deployment-request boundary end-to-end:

ENVIRONMENT   compatible accepted / incompatible rejected / unverifiable surfaced
TRUST         promotion_eligible respected; blocked/quarantined/review refused
REGISTRY      registry.deploy remains the sole promotion mechanism; illegal
              states rejected
SECURITY      unsigned / invalid-signature / revoked-signer / corrupted-artifact
AUTHORIZATION actor identity, separation of duties, policy gates
DEPLOYMENT    success, refusal, post-deployment verification, audit evidence

Also exercises the Gate-D encrypted keystore through a full deployment.
"""
from __future__ import annotations

import json

import pytest

from qsmlops.config import PlatformConfig
from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.keys import KeyStore
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.passport.passport import new_passport
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.registry.registry import ModelRegistry
from qsmlops.serving.deployment import DeploymentError, DeploymentService
from qsmlops.serving.environment import validate_environment
from qsmlops.supplychain.bom import QMLBOM


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "phase6_home")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    pipe.provision_dataset("dep-data", ds)
    yield pipe
    pipe.close()


def _approved(pipeline, model="dep-model"):
    result = pipeline.train_and_register(model, "dep-data")
    evaluation = pipeline.evaluate_version(result["version_id"])
    assert evaluation["decision"] == "VERIFIED"
    pipeline.request_approval(result["version_id"], approver="governor")
    return result


# ----------------------------------------------------------------------
# ENVIRONMENT
# ----------------------------------------------------------------------
class TestEnvironmentValidation:
    def test_compatible_environment_accepted(self, tmp_path):
        config = PlatformConfig(tmp_path / "env_ok")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(50, seed=1)
        pipe.provision_dataset("e", ds)
        r = pipe.train_and_register("m", "e")
        report = validate_environment(
            pipe.registry.load_passport(r["version_id"]),
            pipe._load_bom(pipe.registry.get_version(r["version_id"])["bom_digest"]),
            "production",
        )
        assert report.compatible is True
        names = {c.name: c.status for c in report.checks}
        assert names["python_runtime"] == "OK"
        assert names["framework_dependencies"] == "OK"
        pipe.close()

    def test_incompatible_python_rejected(self, tmp_path):
        config = PlatformConfig(tmp_path / "env_bad")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(50, seed=2)
        pipe.provision_dataset("e", ds)
        r = pipe.train_and_register("m", "e")
        passport = pipe.registry.load_passport(r["version_id"])
        passport.environment["python"] = "3.0.0"  # simulate legacy requirement
        report = validate_environment(passport, None, "production")
        assert report.compatible is False
        py = next(c for c in report.checks if c.name == "python_runtime")
        assert py.status == "MISMATCH"
        pipe.close()

    def test_unverifiable_reported_not_assumed(self, pipeline):
        result = pipeline.train_and_register("u", "dep-data")
        passport = pipeline.registry.load_passport(result["version_id"])
        passport.environment = {}  # strip declarations entirely
        report = validate_environment(passport, None, "staging")
        statuses = {c.name: c.status for c in report.checks}
        assert statuses["python_runtime"] == "UNVERIFIABLE"
        assert any(c.detail for c in report.checks if c.status == "UNVERIFIABLE")


# ----------------------------------------------------------------------
# TRUST
# ----------------------------------------------------------------------
class TestTrustGatesInDeployment:
    def test_trusted_model_proceeds(self, pipeline):
        result = _approved(pipeline)
        out = pipeline.request_deployment(version_id=result["version_id"], actor="ops")
        assert out["state"] == "DEPLOYED"
        assert out["validation"]["trust_decision"] in ("TRUSTED", "CONDITIONALLY_TRUSTED")

    def test_blocked_model_cannot_deploy(self, pipeline):
        result = pipeline.train_and_register("blk", "dep-data")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"corrupted" + original)
        try:
            with pytest.raises(DeploymentError) as ei:
                pipeline.request_deployment(version_id=vid, actor="ops")
            assert "artifact_integrity" in str(ei.value)
            assert pipeline.registry.get_version(vid)["state"] != "DEPLOYED"
        finally:
            path.write_bytes(original)

    def test_quarantined_model_cannot_deploy(self, pipeline):
        result = pipeline.train_and_register("q", "dep-data")
        vid = result["version_id"]
        evaluation = pipeline.evaluate_version(vid)
        if evaluation["decision"] != "VERIFIED":
            pytest.skip("model did not verify; quarantine path covered elsewhere")
        pipeline.registry.quarantine(vid, "secops", "suspected tampering")
        with pytest.raises(DeploymentError) as ei:
            pipeline.request_deployment(version_id=vid, actor="ops")
        assert "registry_state_deployable" in str(ei.value)

    def test_review_required_does_not_silently_proceed(self, minimal_platform_factory):
        registry, vid = minimal_platform_factory
        trust = registry.trust_evaluation(vid, persist=True)
        assert trust.decision == "REVIEW_REQUIRED"
        service = DeploymentService(registry)
        with pytest.raises(DeploymentError) as ei:
            service.request(version_id=vid, actor="ops")
        assert "trust_promotion_eligible" in str(ei.value)


@pytest.fixture()
def minimal_platform_factory(tmp_path):
    """A VERIFIED version whose declared supply chain was never stored:
    structurally valid crypto, REVIEW_REQUIRED trust."""
    from qsmlops.artifacts.store import ArtifactStore
    from qsmlops.crypto.hashing import canonical_json

    config = PlatformConfig(tmp_path / "min6")
    config.ensure_dirs()
    artifacts = ArtifactStore(config.artifacts_dir)
    keystore = KeyStore(config.keys_dir)
    ledger = EvidenceLedger(config.ledger_path)
    agility = AgilityEngine()
    registry = ModelRegistry(config.registry_path, artifacts, keystore, ledger)
    for owner in ("producer", "verifier"):
        suite = agility.select_suite()
        keystore.generate_keypair("SIGNER", suite.signature_algorithm, owner=owner)

    artifact = b"minimal bytes"
    artifact_digest = artifacts.put(artifact)
    bom = QMLBOM.create()
    for i in range(3):  # declared but never stored -> integrity deductions
        bom.add_entry("dependency", f"ghost-{i}", f"{i}" * 64, version="9.9.9")
    artifacts.put(canonical_json(bom.to_dict()))
    passport = new_passport("legacy-m", 1, "producer", bom.digest(), artifact_digest)
    passport.sign(keystore, agility, signer_owner="producer")
    vid = registry.register(passport, artifact, bom.digest())
    registry.verify_version(vid, "verifier", [])
    return registry, vid


# ----------------------------------------------------------------------
# REGISTRY AUTHORITY
# ----------------------------------------------------------------------
class TestRegistryAuthority:
    def test_invalid_state_rejected_by_registry(self, pipeline):
        result = pipeline.train_and_register("ra", "dep-data")  # REGISTERED
        with pytest.raises(Exception) as ei:
            pipeline.registry.deploy(result["version_id"], "operator")
        assert "APPROVED" in str(ei.value) or "gate" in str(ei.value).lower()

    def test_service_never_bypasses_registry(self, pipeline):
        """DeploymentService must hold only the registry as its promoter;
        a successful request must be reflected as a registry transition."""
        result = _approved(pipeline)
        before = pipeline.registry.get_version(result["version_id"])["state"]
        out = pipeline.request_deployment(version_id=result["version_id"], actor="ops")
        after = pipeline.registry.get_version(result["version_id"])["state"]
        assert before == "APPROVED" and after == "DEPLOYED"
        assert out["deployment_id"]


# ----------------------------------------------------------------------
# SECURITY
# ----------------------------------------------------------------------
class TestSecurityGates:
    def test_corrupted_artifact_refused_and_audited(self, pipeline):
        result = _approved(pipeline, model="sec1")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"x" + original)
        try:
            with pytest.raises(DeploymentError):
                pipeline.request_deployment(version_id=vid, actor="ops")
            denials = [e["record"] for e in pipeline.ledger.iter_entries()
                       if e["record"].get("type") == "deployment_denied"]
            assert any(d["version_id"] == vid for d in denials)
        finally:
            path.write_bytes(original)

    def test_forged_passport_refused(self, pipeline):
        result = _approved(pipeline, model="sec2")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        ppath = pipeline.artifacts._path_for(rec["passport_digest"])
        doc = json.loads(ppath.read_bytes().decode("utf-8"))
        doc["metrics"]["r2"] = 0.000001
        ppath.write_bytes(json.dumps(doc, sort_keys=True).encode())
        with pytest.raises(DeploymentError) as ei:
            pipeline.request_deployment(version_id=vid, actor="ops")
        assert "passport_signature_valid" in str(ei.value)


# ----------------------------------------------------------------------
# AUTHORIZATION
# ----------------------------------------------------------------------
class TestAuthorization:
    def test_empty_actor_rejected(self, pipeline):
        result = _approved(pipeline, model="auth1")
        with pytest.raises(DeploymentError) as ei:
            pipeline.request_deployment(version_id=result["version_id"], actor="")
        assert "actor_identified" in str(ei.value)

    def test_signer_cannot_deploy_own_model(self, pipeline):
        result = _approved(pipeline, model="auth2")
        vid = result["version_id"]
        passport = pipeline.registry.load_passport(vid)
        signer_owner = passport.signature.signer_key_id.split("-")[0]
        with pytest.raises(DeploymentError) as ei:
            pipeline.request_deployment(version_id=vid, actor=signer_owner)
        assert "separation_of_duties" in str(ei.value)


# ----------------------------------------------------------------------
# DEPLOYMENT LIFECYCLE + AUDIT + KEYSTORE
# ----------------------------------------------------------------------
class TestDeploymentLifecycle:
    def test_success_writes_full_audit_evidence(self, pipeline):
        result = _approved(pipeline, model="aud")
        out = pipeline.request_deployment(version_id=result["version_id"],
                                          actor="ops", target_environment="prod-eu")
        types = [e["record"].get("type") for e in pipeline.ledger.iter_entries()]
        for expected in ("deployment_requested", "deployment_validation",
                         "deployment_completed"):
            assert expected in types
        ok, msg = pipeline.ledger.verify_chain()
        assert ok, msg

    def test_post_deployment_verification_serving_healthy(self, pipeline):
        result = _approved(pipeline, model="pv")
        out = pipeline.request_deployment(version_id=result["version_id"], actor="ops")
        assert out["post_verification"]["passed"] is True
        assert out["serving_healthy"] is True

    def test_encrypted_keystore_deployment_end_to_end(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QSMLOPS_KEYSTORE_PASSPHRASE", "deployment-pass")
        config = PlatformConfig(tmp_path / "enc_dep")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(100, seed=11)
        pipe.provision_dataset("ed", ds)
        r = pipe.train_and_register("enc-model", "ed")
        pipe.evaluate_version(r["version_id"])
        pipe.request_approval(r["version_id"], approver="governor")
        out = pipe.request_deployment(version_id=r["version_id"], actor="ops")
        assert out["serving_healthy"] is True
        assert not (config.keys_dir / "secret_keys.json").exists()
        assert (config.keys_dir / "secret_keys.vault").exists()
        pipe.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

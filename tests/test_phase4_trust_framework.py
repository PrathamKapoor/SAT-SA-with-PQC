"""Phase 4 trust framework tests (Quantum Model Trust Framework).

Verifies the original Phase 4 requirements from PART 14 §14.3 / §23.14 of
the architecture document against the live platform:

* Quantum Model Passport carrying model identity, full dataset lineage,
  training metadata and security information, signed with ML-DSA;
* QML-BOM tracking dataset, code, framework, runtime environment and
  third-party dependencies, with every declared digest verifiable;
* Verification packets that embed cryptographic evidence (suite, signer,
  hash) for every verification decision;
* end-to-end trust flow with audit evidence in the evidence ledger.
"""
from __future__ import annotations

import importlib.metadata
import json

import pytest

from qsmlops.agents.security_agent import SecurityAgent
from qsmlops.config import PlatformConfig
from qsmlops.crypto.hashing import HASH_ALGORITHM
from qsmlops.evidence.packet import VerificationPacket
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "phase4_home")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    pipe.provision_dataset("lineage-data", ds)
    yield pipe
    pipe.close()


def _train(pipeline, model="trust-model", framework="reference"):
    return pipeline.train_and_register(model, "lineage-data", framework=framework)


# ----------------------------------------------------------------------
# Passport: full lineage, training metadata, security information
# ----------------------------------------------------------------------
class TestPassportLineage:
    def test_passport_carries_full_dataset_lineage(self, pipeline):
        result = _train(pipeline)
        passport = pipeline.registry.load_passport(result["version_id"])
        prov = passport.dataset_provenance

        assert prov["dataset_name"] == "lineage-data"
        # dataset digest must match what provision_dataset stored
        index = json.loads(
            (pipeline.config.root / "datasets_index.json").read_text(encoding="utf-8")
        )
        assert prov["dataset_digest"] == index["lineage-data"]
        # and the recorded dataset bytes must actually verify in the store
        assert pipeline.artifacts.verify(prov["dataset_digest"])
        assert prov["n_samples"] == 200
        assert prov["feature_names"]
        assert prov["bom_digest"]

    def test_passport_records_training_metadata(self, pipeline):
        result = _train(pipeline)
        passport = pipeline.registry.load_passport(result["version_id"])
        info = passport.training_info

        assert info["algorithm"]
        assert info["framework"] == "reference"
        assert info["hyperparameters"]["epochs"] == 300
        assert "lr" in info["hyperparameters"] and "seed" in info["hyperparameters"]
        assert info["training_duration_ms"] >= 0
        assert passport.environment["python"]
        assert passport.environment["hardware"] == "cpu"

    def test_passport_security_metadata_names_crypto_and_signature_matches(self, pipeline):
        result = _train(pipeline)
        passport = pipeline.registry.load_passport(result["version_id"])
        sec = passport.security_status

        assert sec["hash_algorithm"] == HASH_ALGORITHM == "sha3-256"
        assert sec["signature_algorithm"].startswith("ML-DSA")
        assert sec["suite_id"]
        assert sec["artifact_digest"] == result["artifact_digest"]
        # the declared suite must be the one actually used for signing
        assert passport.signature.algorithm_id == sec["signature_algorithm"]
        assert passport.verify_signature(pipeline.keystore)


# ----------------------------------------------------------------------
# QML-BOM: environment + dependency components, all digests verifiable
# ----------------------------------------------------------------------
class TestBOMSupplyChain:
    def test_bom_declares_runtime_environment(self, pipeline):
        result = _train(pipeline)
        rec = pipeline.registry.get_version(result["version_id"])
        bom = pipeline._load_bom(rec["bom_digest"])

        env_entries = bom.by_kind("hardware")
        assert len(env_entries) == 1
        entry = env_entries[0]
        assert entry.name.endswith("-environment")
        assert entry.metadata.get("python")
        # environment fingerprint is stored and re-verifiable
        assert pipeline.artifacts.verify(entry.digest)

    def test_bom_declares_real_dependency_for_sklearn(self, pipeline):
        pytest.importorskip("sklearn")
        result = _train(pipeline, model="sk-model", framework="sklearn")
        rec = pipeline.registry.get_version(result["version_id"])
        bom = pipeline._load_bom(rec["bom_digest"])

        deps = bom.by_kind("dependency")
        assert len(deps) == 1
        dep = deps[0]
        assert dep.name == "scikit-learn"
        # version must be the genuinely installed one, not a fabricated value
        assert dep.version == importlib.metadata.version("scikit-learn")
        assert dep.origin == "pypi"
        assert pipeline.artifacts.verify(dep.digest)

    def test_reference_trainer_honestly_has_no_third_party_dependency(self, pipeline):
        result = _train(pipeline)
        rec = pipeline.registry.get_version(result["version_id"])
        bom = pipeline._load_bom(rec["bom_digest"])
        assert bom.by_kind("dependency") == []

    def test_every_bom_entry_verifies_in_store_security_agent_accepts(self, pipeline):
        """The Phase-4 BOM must give the SecurityAgent zero integrity failures."""
        result = _train(pipeline)
        rec = pipeline.registry.get_version(result["version_id"])
        bom = pipeline._load_bom(rec["bom_digest"])
        for e in bom.entries:
            assert pipeline.artifacts.verify(e.digest), f"{e.kind}:{e.name}"

        passport = pipeline.registry.load_passport(result["version_id"])
        context = {
            "subject_id": result["version_id"],
            "passport": passport,
            "keystore": pipeline.keystore,
            "bom": bom,
            "artifact_digest": rec["artifact_digest"],
            "metrics": passport.metrics,
            "probe_inputs": [[0.1, -0.2], [0.5, 0.3]],
        }
        obs = SecurityAgent(pipeline.artifacts).observe(context)
        failed = [f for f in obs.findings if not f.passed]
        assert failed == []
        assert obs.recommendation == "ACCEPT"


# ----------------------------------------------------------------------
# Verification packets: cryptographic evidence embedded
# ----------------------------------------------------------------------
class TestVerificationPacketCryptoEvidence:
    def test_packet_proves_suite_signer_and_hash(self, pipeline):
        result = _train(pipeline)
        packet = pipeline.registry.verify_version(
            result["version_id"], "verifier", [("agent_check", True)]
        )
        crypto = packet.proofs["crypto"]
        passport = pipeline.registry.load_passport(result["version_id"])

        assert crypto["hash_algorithm"] == "sha3-256"
        assert crypto["suite_id"] == passport.signature.suite_id
        assert crypto["signature_algorithm"] == passport.signature.algorithm_id
        assert crypto["signer_key_id"] == passport.signature.signer_key_id
        assert crypto["signed_digest"] == passport.signature.signed_digest
        assert crypto["signature_verified"] is True
        assert crypto["artifact_integrity"] is True

    def test_packet_crypto_evidence_survives_roundtrip(self, pipeline):
        result = _train(pipeline)
        packet = pipeline.registry.verify_version(result["version_id"], "verifier", [])
        restored = VerificationPacket.from_dict(packet.to_dict())
        assert restored.proofs["crypto"]["signer_key_id"] == packet.proofs["crypto"]["signer_key_id"]


# ----------------------------------------------------------------------
# End-to-end trust flow with audit evidence
# ----------------------------------------------------------------------
class TestTrustFlowEndToEnd:
    def test_train_verify_deploy_leaves_complete_audit_evidence(self, pipeline):
        result = _train(pipeline)
        evaluation = pipeline.evaluate_version(result["version_id"])
        assert evaluation["decision"] == "VERIFIED"

        deployment_id = pipeline.approve_and_deploy(result["version_id"])
        assert deployment_id

        ok, msg = pipeline.ledger.verify_chain()
        assert ok, msg

        record_types = [e["record"].get("type") for e in pipeline.ledger.iter_entries()]
        assert "registration" in record_types
        assert "verification_packet" in record_types
        assert "state_transition" in record_types

    def test_retrained_version_repeats_full_trust_flow(self, pipeline):
        first = _train(pipeline)
        second = _train(pipeline)  # auto-versioning
        assert second["version"] == first["version"] + 1
        evaluation = pipeline.evaluate_version(second["version_id"])
        assert evaluation["decision"] == "VERIFIED"
        ok, msg = pipeline.ledger.verify_chain()
        assert ok, msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

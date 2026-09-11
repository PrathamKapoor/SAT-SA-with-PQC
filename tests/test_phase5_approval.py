"""Phase 5 governed approval tests.

The approval gate must inspect real trust evidence, respect separation of
duties, preserve registry state-machine invariants and audit every denial.
Integration covers train -> register -> verify -> trust evaluate -> approve
-> deployment eligibility on the actual platform.
"""
from __future__ import annotations

import json

import pytest

from qsmlops.artifacts.store import ArtifactStore
from qsmlops.config import PlatformConfig
from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.keys import KeyStore
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.evidence.packet import VerificationPacket
from qsmlops.passport.passport import new_passport
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.registry.registry import ModelRegistry
from qsmlops.supplychain.bom import QMLBOM


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "phase5_approval")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    pipe.provision_dataset("appr-data", ds)
    yield pipe
    pipe.close()


@pytest.fixture()
def minimal_platform(tmp_path):
    """Registry-level fixture for constructing legacy-style minimal versions."""
    config = PlatformConfig(tmp_path / "phase5_min")
    config.ensure_dirs()
    artifacts = ArtifactStore(config.artifacts_dir)
    keystore = KeyStore(config.keys_dir)
    ledger = EvidenceLedger(config.ledger_path)
    agility = AgilityEngine()
    registry = ModelRegistry(config.registry_path, artifacts, keystore, ledger)
    for owner in ("producer", "verifier"):
        suite = agility.select_suite()
        keystore.generate_keypair("SIGNER", suite.signature_algorithm, owner=owner)
    return {
        "artifacts": artifacts,
        "keystore": keystore,
        "ledger": ledger,
        "agility": agility,
        "registry": registry,
    }


def _verified(pipeline, model="am"):
    result = pipeline.train_and_register(model, "appr-data")
    evaluation = pipeline.evaluate_version(result["version_id"])
    assert evaluation["decision"] == "VERIFIED"
    return result, evaluation


class TestApprovalGate:
    def test_trusted_model_passes_approval_with_structured_result(self, pipeline):
        result, _ = _verified(pipeline)
        approval = pipeline.request_approval(result["version_id"], approver="release-manager")

        assert approval["state"] == "APPROVED"
        assert approval["approver"] == "release-manager"
        assert approval["trust_decision"] in ("TRUSTED", "CONDITIONALLY_TRUSTED")
        assert isinstance(approval["trust_score"], float)
        assert approval["packet_id"]
        assert "explanation" in approval

    def test_low_trust_model_is_refused_and_audited(self, minimal_platform):
        """A version whose declared supply chain was never stored scores low.

        Real state, no fabrication: signed passport, stored artifact, but a
        BOM declaring three components with no backing bytes — exactly what
        a careless legacy flow produces. The composite lands below the
        conditional threshold and the gate must refuse + audit the denial.
        """
        platform = minimal_platform
        artifacts, keystore, registry = (
            platform["artifacts"], platform["keystore"], platform["registry"],
        )

        artifact = b"minimal model bytes"
        artifact_digest = artifacts.put(artifact)
        bom = QMLBOM.create()
        for i in range(3):  # declared but never stored -> integrity deductions
            bom.add_entry("dependency", f"ghost-lib-{i}", f"{i}" * 64, version="9.9.9")
        # store the BOM document itself, exactly as train_and_register does,
        # so the declared entries (not the BOM) are what fails verification
        from qsmlops.crypto.hashing import canonical_json

        artifacts.put(canonical_json(bom.to_dict()))
        passport = new_passport(
            name="legacy-model", version=1, owner="producer",
            bom_digest=bom.digest(), artifact_digest=artifact_digest,
        )
        passport.sign(keystore, platform["agility"], signer_owner="producer")
        vid = registry.register(passport, artifact, bom.digest())

        packet = registry.verify_version(vid, "verifier", [])
        assert packet.decision == "VERIFIED"

        trust = registry.trust_evaluation(vid, persist=True)
        assert trust.decision == "REVIEW_REQUIRED"
        assert trust.trust_score < 70.0

        gate_packet = VerificationPacket.create(
            objective="premature promotion", actor="operator",
            decision="ACCEPT", status="CLOSED",
        )
        with pytest.raises(Exception) as excinfo:
            registry.approve_deployment(vid, "operator", gate_packet)
        assert "trust evaluation returned REVIEW_REQUIRED" in str(excinfo.value)
        assert registry.get_version(vid)["state"] == "VERIFIED"

        denials = [
            e["record"] for e in registry.ledger.iter_entries()
            if e["record"].get("type") == "approval_denied"
        ]
        assert any(d["version_id"] == vid and "REVIEW_REQUIRED" in d["reason"]
                   for d in denials)

    def test_blocked_signature_prevents_approval(self, pipeline):
        result, _ = _verified(pipeline, model="forged")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        # forge: rewrite the passport body after signing
        ppath = pipeline.artifacts._path_for(rec["passport_digest"])
        doc = json.loads(ppath.read_bytes().decode("utf-8"))
        doc["identity"]["version"] = 999
        ppath.write_bytes(json.dumps(doc, sort_keys=True).encode())

        gate_packet = VerificationPacket.create(
            objective="attempt", actor="insider", decision="ACCEPT", status="CLOSED",
        )
        with pytest.raises(Exception) as excinfo:
            pipeline.registry.approve_deployment(vid, "insider", gate_packet)
        assert "refused" in str(excinfo.value).lower()
        assert pipeline.registry.get_version(vid)["state"] == "VERIFIED"
        denials = [
            e["record"] for e in pipeline.ledger.iter_entries()
            if e["record"].get("type") == "approval_denied"
        ]
        assert any(d["version_id"] == vid for d in denials)

    def test_approver_cannot_equal_signer(self, pipeline):
        result, _ = _verified(pipeline, model="sod")
        vid = result["version_id"]
        passport = pipeline.registry.load_passport(vid)
        signer_owner = passport.signature.signer_key_id.split("-")[0]

        gate_packet = VerificationPacket.create(
            objective="self-approval attempt", actor=signer_owner,
            decision="ACCEPT", status="CLOSED",
        )
        with pytest.raises(Exception) as excinfo:
            pipeline.registry.approve_deployment(vid, signer_owner, gate_packet)
        assert "separation of duties" in str(excinfo.value)
        assert pipeline.registry.get_version(vid)["state"] == "VERIFIED"

    def test_only_verified_versions_can_be_approved(self, pipeline):
        result = pipeline.train_and_register("raw", "appr-data")  # REGISTERED
        gate_packet = VerificationPacket.create(
            objective="skip verification", actor="operator",
            decision="ACCEPT", status="CLOSED",
        )
        with pytest.raises(Exception) as excinfo:
            pipeline.registry.approve_deployment(result["version_id"], "operator", gate_packet)
        assert "VERIFIED" in str(excinfo.value)
        assert pipeline.registry.get_version(result["version_id"])["state"] == "REGISTERED"


class TestApprovalIntegration:
    def test_full_promotion_chain_train_to_deployment_eligibility(self, pipeline):
        result = pipeline.train_and_register("chain", "appr-data")
        vid = result["version_id"]

        assert pipeline.registry.get_version(vid)["state"] == "REGISTERED"

        evaluation = pipeline.evaluate_version(vid)
        assert evaluation["decision"] == "VERIFIED"
        trust = evaluation["trust"]
        assert trust["promotion_eligible"] is True

        pipeline.request_approval(vid, approver="governor")
        assert pipeline.registry.get_version(vid)["state"] == "APPROVED"

        # deployment remains a separate, gated step (existing mechanism)
        dep_id = pipeline.registry.deploy(vid, "supervisor")
        assert dep_id
        assert pipeline.registry.active_deployment("chain")["version_id"] == vid

        ok, msg = pipeline.ledger.verify_chain()
        assert ok, msg

    def test_denied_approval_leaves_no_deployment_path(self, pipeline):
        result, _ = _verified(pipeline, model="denied")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"compromised" + original)
        try:
            with pytest.raises(RuntimeError):
                pipeline.request_approval(vid, approver="operator")
            # deployment requires APPROVED: still VERIFIED here
            with pytest.raises(Exception):
                pipeline.registry.deploy(vid, "supervisor")
            assert pipeline.registry.active_deployment("denied") is None
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

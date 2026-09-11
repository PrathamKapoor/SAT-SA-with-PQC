"""Tests for artifact store, passport, BOM, registry."""
from __future__ import annotations

import pytest

from qsmlops.artifacts.store import ArtifactStore
from qsmlops.evidence.packet import VerificationPacket, SecurityCheck
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.passport.passport import new_passport, Passport
from qsmlops.supplychain.bom import QMLBOM
from qsmlops.registry.registry import ModelRegistry
from qsmlops.config import PlatformConfig
from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.keys import KeyStore


@pytest.fixture
def platform(tmp_path):
    config = PlatformConfig(tmp_path / "qsmlops_test")
    config.ensure_dirs()
    artifacts = ArtifactStore(config.artifacts_dir)
    keystore = KeyStore(config.keys_dir)
    ledger = EvidenceLedger(config.ledger_path)
    agility = AgilityEngine()
    registry = ModelRegistry(config.registry_path, artifacts, keystore, ledger)
    # bootstrap keys
    for owner in ("producer", "verifier"):
        suite = agility.select_suite()
        keystore.generate_keypair("SIGNER", suite.signature_algorithm, owner=owner)
    return {
        "config": config,
        "artifacts": artifacts,
        "keystore": keystore,
        "ledger": ledger,
        "agility": agility,
        "registry": registry,
    }


def test_artifact_store_put_get(tmp_path):
    store = ArtifactStore(tmp_path / "art")
    data = b"test artifact"
    digest = store.put(data)
    assert store.get(digest) == data
    assert store.exists(digest)
    assert store.verify(digest)


def test_artifact_store_integrity(tmp_path):
    store = ArtifactStore(tmp_path / "art")
    data = b"original"
    digest = store.put(data)
    # corrupt on disk
    path = store._path_for(digest)
    path.write_bytes(b"corrupted")
    with pytest.raises(IOError):
        store.get(digest)
    
def test_artifact_store_dedup(tmp_path):
    store = ArtifactStore(tmp_path / "art")
    d1 = store.put(b"same")
    d2 = store.put(b"same")
    assert d1 == d2


def test_passport_create_and_sign(platform):
    ks = platform["keystore"]
    agility = platform["agility"]
    bom = QMLBOM.create()
    bom.add_entry("artifact", "model1", "a" * 64)
    passport = new_passport(
        name="model1",
        version=1,
        owner="producer",
        bom_digest=bom.digest(),
        artifact_digest="b" * 64,
        metrics={"mse": 0.01, "r2": 0.95},
    )
    passport.sign(ks, agility, signer_owner="producer")
    assert passport.signature is not None
    assert passport.verify_signature(ks) is True
    assert passport.signature.signer_key_id.startswith("producer-")


def test_passport_rejects_unsigned(platform):
    passport = new_passport(
        name="model2",
        version=1,
        owner="producer",
        bom_digest="x" * 64,
        artifact_digest="y" * 64,
    )
    assert passport.signature is None
    assert passport.verify_signature(platform["keystore"]) is False


def test_bom_diff():
    bom1 = QMLBOM.create()
    bom1.add_entry("dataset", "ds1", "a" * 64)
    bom1.add_entry("code", "trainer", "b" * 64)
    bom2 = QMLBOM.create()
    bom2.add_entry("dataset", "ds1", "a" * 64)
    bom2.add_entry("code", "trainer", "c" * 64)
    diff = bom1.diff(bom2)
    assert len(diff["added"]) == 1
    assert len(diff["removed"]) == 1


def test_registry_register_and_transition(platform):
    registry = platform["registry"]
    artifacts = platform["artifacts"]
    ks = platform["keystore"]
    agility = platform["agility"]
    bom = QMLBOM.create()
    bom.add_entry("dataset", "ds1", "d" * 64)
    artifact = b"model bytes v1"
    artifact_digest = artifacts.put(artifact)
    passport = new_passport(
        name="modelX",
        version=1,
        owner="producer",
        bom_digest=bom.digest(),
        artifact_digest=artifact_digest,
    )
    passport.sign(ks, agility, signer_owner="producer")
    vid = registry.register(passport, artifact, bom.digest())
    assert vid is not None
    rec = registry.get_version(vid)
    assert rec["state"] == "REGISTERED"


def test_registry_verify_enforces_separation_of_duties(platform):
    registry = platform["registry"]
    artifacts = platform["artifacts"]
    ks = platform["keystore"]
    agility = platform["agility"]
    bom = QMLBOM.create()
    bom.add_entry("dataset", "ds1", "d" * 64)
    artifact = b"model bytes v2"
    artifact_digest = artifacts.put(artifact)
    passport = new_passport(
        name="modelY",
        version=1,
        owner="producer",
        bom_digest=bom.digest(),
        artifact_digest=artifact_digest,
    )
    passport.sign(ks, agility, signer_owner="producer")
    vid = registry.register(passport, artifact, bom.digest())
    # verifier == signer owner -> should fail
    with pytest.raises(Exception):
        registry.verify_version(vid, "producer", [])


def test_registry_state_transitions(platform):
    registry = platform["registry"]
    artifacts = platform["artifacts"]
    ks = platform["keystore"]
    agility = platform["agility"]
    bom = QMLBOM.create()
    bom.add_entry("dataset", "ds1", "d" * 64)
    artifact = b"model bytes v3"
    artifact_digest = artifacts.put(artifact)
    passport = new_passport(
        name="modelZ",
        version=1,
        owner="producer",
        bom_digest=bom.digest(),
        artifact_digest=artifact_digest,
    )
    passport.sign(ks, agility, signer_owner="producer")
    vid = registry.register(passport, artifact, bom.digest())
    # register -> verified
    packet = registry.verify_version(vid, "verifier", [("check1", True)])
    assert packet.decision == "VERIFIED"
    rec = registry.get_version(vid)
    assert rec["state"] == "VERIFIED"
    # verified -> approved
    from qsmlops.evidence.packet import VerificationPacket
    gate = VerificationPacket.create(
        objective="approve", actor="supervisor", decision="ACCEPT", status="CLOSED",
    )
    registry.approve_deployment(vid, "supervisor", gate)
    rec = registry.get_version(vid)
    assert rec["state"] == "APPROVED"
    # approved -> deployed
    dep_id = registry.deploy(vid, "supervisor")
    rec = registry.get_version(vid)
    assert rec["state"] == "DEPLOYED"
    # deployed -> rolled_back
    prev = registry.rollback("modelZ", "supervisor")
    rec = registry.get_version(vid)
    assert rec["state"] == "ROLLED_BACK"


def test_verification_packet_and_ledger(platform):
    ledger = platform["ledger"]
    packet = VerificationPacket.create(
        objective="test", actor="tester", decision="TEST", status="CLOSED",
    )
    entry = ledger.append_packet(packet)
    ok, msg = ledger.verify_chain()
    assert ok
    assert entry["record"]["packet_id"] == packet.packet_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
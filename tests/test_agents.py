"""Tests for the agent system."""
from __future__ import annotations

import pytest

from qsmlops.agents.data_agent import DataAgent
from qsmlops.agents.performance_agent import PerformanceAgent
from qsmlops.agents.security_agent import SecurityAgent
from qsmlops.agents.quantum_agent import QuantumSecurityAgent
from qsmlops.agents.redteam import RedTeamAgent
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.config import PlatformConfig
from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.keys import KeyStore
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.passport.passport import new_passport
from qsmlops.registry.registry import ModelRegistry
from qsmlops.supplychain.bom import QMLBOM


@pytest.fixture
def platform(tmp_path):
    config = PlatformConfig(tmp_path / "qsmlops_test")
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
        "config": config,
        "artifacts": artifacts,
        "keystore": keystore,
        "ledger": ledger,
        "agility": agility,
        "registry": registry,
    }


def test_data_agent_passes_with_valid_dataset(platform):
    artifacts = platform["artifacts"]
    ds_payload = b"dataset content"
    ds_digest = artifacts.put(ds_payload)
    bom = QMLBOM.create()
    bom.add_entry("dataset", "test-ds", ds_digest, origin="test")
    agent = DataAgent(artifacts)
    context = {"subject_id": "test", "bom": bom}
    obs = agent.observe(context)
    assert obs.recommendation == "ACCEPT"
    assert all(f.passed for f in obs.findings)


def test_data_agent_fails_on_missing_dataset(platform):
    artifacts = platform["artifacts"]
    bom = QMLBOM.create()
    bom.add_entry("dataset", "missing-ds", "a" * 64, origin="test")
    agent = DataAgent(artifacts)
    context = {"subject_id": "test", "bom": bom}
    obs = agent.observe(context)
    assert obs.recommendation == "QUARANTINE"
    assert any(not f.passed and f.severity == "CRITICAL" for f in obs.findings)


def test_performance_agent_passes_thresholds():
    agent = PerformanceAgent(thresholds={"min_r2": 0.5, "max_mse": 0.1})
    context = {"subject_id": "test", "metrics": {"r2": 0.9, "mse": 0.01}}
    obs = agent.observe(context)
    assert obs.recommendation == "ACCEPT"
    assert all(f.passed for f in obs.findings)


def test_performance_agent_fails_low_r2():
    agent = PerformanceAgent(thresholds={"min_r2": 0.9, "max_mse": 0.1})
    context = {"subject_id": "test", "metrics": {"r2": 0.5, "mse": 0.01}}
    obs = agent.observe(context)
    assert obs.recommendation == "RETRAIN"
    assert any(not f.passed and f.name == "r2_above_threshold" for f in obs.findings)


def test_performance_agent_fails_high_mse():
    # MSE check is MEDIUM severity, so it alone doesn't trigger RETRAIN
    # Need both R2 (HIGH) and MSE to fail for RETRAIN
    agent = PerformanceAgent(thresholds={"min_r2": 0.9, "max_mse": 0.05})
    context = {"subject_id": "test", "metrics": {"r2": 0.5, "mse": 0.1}}
    obs = agent.observe(context)
    assert obs.recommendation == "RETRAIN"
    assert any(not f.passed and f.name == "r2_above_threshold" for f in obs.findings)
    assert any(not f.passed and f.name == "mse_below_threshold" for f in obs.findings)


def test_performance_agent_drift_detected():
    agent = PerformanceAgent()
    context = {"subject_id": "test", "metrics": {"r2": 0.9, "mse": 0.01}, "drift_detected": True}
    obs = agent.observe(context)
    assert any(not f.passed and f.name == "input_distribution_stable" for f in obs.findings)


def test_security_agent_no_vulns(platform):
    artifacts = platform["artifacts"]
    bom = QMLBOM.create()
    # Add dependency with a real artifact in store
    dep_content = b"torch-2.5.0"
    dep_digest = artifacts.put(dep_content)
    bom.add_entry("dependency", "torch", dep_digest, version="2.5.0")
    agent = SecurityAgent(artifacts)
    context = {"subject_id": "test", "bom": bom}
    obs = agent.observe(context)
    assert obs.recommendation == "ACCEPT"


def test_security_agent_detects_vuln(platform):
    artifacts = platform["artifacts"]
    bom = QMLBOM.create()
    bom.add_entry("dependency", "torch", "a" * 64, version="2.0.0")
    agent = SecurityAgent(artifacts)
    context = {"subject_id": "test", "bom": bom}
    obs = agent.observe(context)
    assert obs.recommendation == "BLOCK_DEPLOYMENT"
    assert any("dependency_vulnerability" in f.name for f in obs.findings)


def test_security_agent_detects_corrupted_artifact(platform):
    artifacts = platform["artifacts"]
    bom = QMLBOM.create()
    bom.add_entry("artifact", "model", "a" * 64)
    agent = SecurityAgent(artifacts)
    context = {"subject_id": "test", "bom": bom}
    obs = agent.observe(context)
    assert obs.recommendation == "BLOCK_DEPLOYMENT"
    assert any(not f.passed and f.severity == "CRITICAL" for f in obs.findings)


def test_quantum_agent_valid_passport(platform):
    keystore = platform["keystore"]
    agility = platform["agility"]
    artifacts = platform["artifacts"]
    bom = QMLBOM.create()
    bom.add_entry("artifact", "model", "b" * 64)
    passport = new_passport("model1", 1, "producer", bom.digest(), "b" * 64)
    passport.sign(keystore, agility, "producer")
    agent = QuantumSecurityAgent(agility)
    context = {"subject_id": "test", "passport": passport, "keystore": keystore}
    obs = agent.observe(context)
    assert obs.recommendation == "ACCEPT"
    assert all(f.passed for f in obs.findings)


def test_quantum_agent_unsigned_passport(platform):
    agility = platform["agility"]
    keystore = platform["keystore"]
    bom = QMLBOM.create()
    passport = new_passport("model1", 1, "producer", bom.digest(), "b" * 64)
    agent = QuantumSecurityAgent(agility)
    context = {"subject_id": "test", "passport": passport, "keystore": keystore}
    obs = agent.observe(context)
    assert obs.recommendation == "QUARANTINE"
    assert any(not f.passed and f.name == "passport_signed" for f in obs.findings)


def test_redteam_agent_integrity_tripwire(platform):
    artifacts = platform["artifacts"]
    model_bytes = b"model content"
    artifact_digest = artifacts.put(model_bytes)
    agent = RedTeamAgent(artifacts)
    context = {"subject_id": "test", "artifact_digest": artifact_digest}
    obs = agent.observe(context)
    assert any(f.name == "tamper_detection_effective" and f.passed for f in obs.findings)


def test_redteam_agent_passport_binding(platform):
    artifacts = platform["artifacts"]
    keystore = platform["keystore"]
    agility = platform["agility"]
    model_bytes = b"model content"
    artifact_digest = artifacts.put(model_bytes)
    bom = QMLBOM.create()
    bom.add_entry("artifact", "model", artifact_digest)
    passport = new_passport("model1", 1, "producer", bom.digest(), artifact_digest)
    passport.sign(keystore, agility, "producer")
    agent = RedTeamAgent(artifacts)
    context = {"subject_id": "test", "artifact_digest": artifact_digest, "passport": passport, "bom": bom}
    obs = agent.observe(context)
    assert any(f.name == "passport_binds_served_artifact" and f.passed for f in obs.findings)
    assert any(f.name == "bom_declares_artifact" and f.passed for f in obs.findings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
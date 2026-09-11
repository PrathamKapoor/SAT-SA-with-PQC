"""Phase 3 security test suite.

Covers the quantum-security layer beyond Phase 1/2 coverage:

* PQC provider (ML-KEM hybrid encryption, ML-DSA signatures, SHA-3 hashing)
* Dynamic organization policy sets (file loading, hot reload, resilience)
* CryptoProvider contract conformance (classical reference provider)
"""
from __future__ import annotations

import json
import time

import pytest

from qsmlops.crypto.providers import KeyPair, ProviderError
from qsmlops.security.crypto.providers.classical import ClassicalProvider
from qsmlops.security.crypto.providers.pqc import PQCProvider
from qsmlops.security.policies import DynamicPolicySet
from qsmlops.supervisor.policy import PolicyEngine

pqc_libs = pytest.importorskip("kyber_py")
pytest.importorskip("dilithium_py")


# ----------------------------------------------------------------------
# PQC provider — signatures (ML-DSA)
# ----------------------------------------------------------------------
class TestPQCSignatures:
    def test_signature_roundtrip(self):
        provider = PQCProvider()
        kp = provider.generate_keypair("signature")
        assert isinstance(kp, KeyPair)
        assert kp.algorithm_id == "ML-DSA-65"
        sig = provider.sign(kp.secret_key, b"passport-document")
        assert provider.verify(kp.public_key, b"passport-document", sig)

    def test_verify_rejects_tampered_message(self):
        provider = PQCProvider()
        kp = provider.generate_keypair("signature")
        sig = provider.sign(kp.secret_key, b"original")
        assert not provider.verify(kp.public_key, b"tampered", sig)

    def test_verify_rejects_tampered_signature(self):
        provider = PQCProvider()
        kp = provider.generate_keypair("signature")
        sig = bytearray(provider.sign(kp.secret_key, b"doc"))
        sig[len(sig) // 2] ^= 0xFF
        assert not provider.verify(kp.public_key, b"doc", bytes(sig))

    @pytest.mark.parametrize("algorithm", ["ML-DSA-44", "ML-DSA-87"])
    def test_alternate_parameter_sets(self, algorithm):
        provider = PQCProvider(signature_algorithm=algorithm)
        kp = provider.generate_keypair("signature")
        assert kp.algorithm_id == algorithm
        assert provider.verify(
            kp.public_key, b"m", provider.sign(kp.secret_key, b"m")
        )

    def test_unknown_signature_algorithm_rejected(self):
        with pytest.raises(ProviderError, match="unknown signature algorithm"):
            PQCProvider(signature_algorithm="RSA-4096")

    def test_unknown_kem_algorithm_rejected(self):
        with pytest.raises(ProviderError, match="unknown KEM algorithm"):
            PQCProvider(kem_algorithm="RSA-OAEP")


# ----------------------------------------------------------------------
# PQC provider — hybrid encryption (ML-KEM + AES-GCM)
# ----------------------------------------------------------------------
class TestPQCEncryption:
    def _provider_with_keys(self):
        provider = PQCProvider()
        kem_kp = provider.generate_keypair("kem")
        return provider, kem_kp

    def test_seal_open_roundtrip(self):
        provider, kem_kp = self._provider_with_keys()
        blob = provider.seal(b"model weights 0123456789", kem_kp.public_key)
        assert provider.open(blob, kem_kp.secret_key) == b"model weights 0123456789"

    def test_ciphertext_hides_plaintext(self):
        provider, kem_kp = self._provider_with_keys()
        blob = provider.seal(b"secret payload", kem_kp.public_key)
        assert b"secret payload" not in blob

    def test_wrong_secret_key_fails(self):
        provider, kem_kp = self._provider_with_keys()
        other = provider.generate_keypair("kem")
        blob = provider.seal(b"payload", kem_kp.public_key)
        with pytest.raises(ProviderError, match="decryption failed"):
            provider.open(blob, other.secret_key)

    def test_tampered_ciphertext_fails(self):
        provider, kem_kp = self._provider_with_keys()
        blob = bytearray(provider.seal(b"payload", kem_kp.public_key))
        blob[-1] ^= 0x01
        with pytest.raises(ProviderError):
            provider.open(bytes(blob), kem_kp.secret_key)

    def test_truncated_blob_rejected(self):
        provider, kem_kp = self._provider_with_keys()
        with pytest.raises(ProviderError, match="too short"):
            provider.open(b"\x01\x00\x00", kem_kp.secret_key)

    def test_unknown_framing_version_rejected(self):
        provider, kem_kp = self._provider_with_keys()
        blob = bytearray(provider.seal(b"payload", kem_kp.public_key))
        blob[0] = 99
        with pytest.raises(ProviderError, match="framing version"):
            provider.open(bytes(blob), kem_kp.secret_key)

    def test_encrypt_decrypt_via_key_references(self):
        keys: dict[str, tuple[bytes, bytes]] = {}
        provider = PQCProvider(
            public_key_resolver=lambda ref: keys[ref][0],
            secret_key_resolver=lambda ref: keys[ref][1],
        )
        kp = provider.generate_keypair("kem")
        keys["artifact-key"] = (kp.public_key, kp.secret_key)
        blob = provider.encrypt(b"dataset row data", "artifact-key")
        assert provider.decrypt(blob, "artifact-key") == b"dataset row data"

    def test_encrypt_without_resolver_raises(self):
        provider = PQCProvider()
        with pytest.raises(ProviderError, match="no public key resolver"):
            provider.encrypt(b"x", "missing-ref")

    def test_decrypt_with_unresolvable_reference_raises(self):
        provider = PQCProvider(
            public_key_resolver=lambda ref: b"", secret_key_resolver=lambda ref: b""
        )
        with pytest.raises(ProviderError, match="resolution failed|empty"):
            provider.decrypt(b"\x00" * 64, "gone")


# ----------------------------------------------------------------------
# PQC provider — hashing + contract conformance
# ----------------------------------------------------------------------
class TestPQCContract:
    def test_hash_is_sha3_256_raw_bytes(self):
        from qsmlops.crypto.hashing import sha3_hex

        provider = PQCProvider()
        digest = provider.hash(b"deterministic input")
        assert digest == bytes.fromhex(sha3_hex(b"deterministic input"))
        assert len(digest) == 32

    def test_is_crypto_provider_subclass(self):
        from qsmlops.security.crypto.providers.base import CryptoProvider

        assert issubclass(PQCProvider, CryptoProvider)
        assert issubclass(ClassicalProvider, CryptoProvider)

    def test_classical_provider_hashes_only(self):
        provider = ClassicalProvider()
        assert len(provider.hash(b"x")) == 32
        for call in (
            lambda: provider.generate_keypair(),
            lambda: provider.encrypt(b"x", "k"),
            lambda: provider.sign(b"sk", b"d"),
        ):
            with pytest.raises(ProviderError):
                call()


# ----------------------------------------------------------------------
# Dynamic policy loading
# ----------------------------------------------------------------------
def _policy_doc(action="ESCALATE", priority=100):
    return {
        "rules": [
            {
                "name": f"rule_{action.lower()}",
                "priority": priority,
                "description": "test rule",
                "when": {
                    "all": [{"field": "risk_score", "op": "gte", "value": 10}]
                },
                "action": action,
            }
        ]
    }


class TestDynamicPolicyLoading:
    def test_load_json_and_evaluate(self, tmp_path):
        from qsmlops.security.policies import write_default_document

        path = write_default_document(tmp_path / "policies.json", _policy_doc())
        pset = DynamicPolicySet(path)
        decision = pset.engine.first_decision({"risk_score": 50})
        assert decision is not None and decision.action == "ESCALATE"
        assert pset.engine.first_decision({"risk_score": 1}) is None

    def test_load_yaml(self, tmp_path):
        import yaml

        path = tmp_path / "policies.yaml"
        path.write_text(yaml.safe_dump(_policy_doc("RETRAIN")), encoding="utf-8")
        pset = DynamicPolicySet(path)
        assert pset.engine.first_decision({"risk_score": 99}).action == "RETRAIN"

    def test_hot_reload_picks_up_edits(self, tmp_path):
        path = tmp_path / "policies.json"
        path.write_text(json.dumps(_policy_doc("ESCALATE")), encoding="utf-8")
        pset = DynamicPolicySet(path)
        assert pset.engine.first_decision({"risk_score": 50}).action == "ESCALATE"

        # edit without touching the API; fingerprint change forces reload
        time.sleep(0.02)
        path.write_text(json.dumps(_policy_doc("QUARANTINE")), encoding="utf-8")
        assert pset.engine.first_decision({"risk_score": 50}).action == "QUARANTINE"
        assert pset.reload_count >= 2

    def test_broken_file_keeps_last_good_engine(self, tmp_path):
        path = tmp_path / "policies.json"
        path.write_text(json.dumps(_policy_doc()), encoding="utf-8")
        pset = DynamicPolicySet(path)
        good = pset.engine
        time.sleep(0.02)
        path.write_text("{not valid json!!", encoding="utf-8")
        assert pset.engine is good
        assert "JSONDecodeError" in pset.last_error or "Error" in pset.last_error

    def test_initial_broken_file_raises(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("[[[", encoding="utf-8")
        with pytest.raises(Exception):
            DynamicPolicySet(path).engine

    def test_missing_file_raises_on_first_access(self, tmp_path):
        pset = DynamicPolicySet(tmp_path / "nope.json")
        with pytest.raises(OSError):
            pset.engine

    def test_forced_reload_reports_change_and_validates(self, tmp_path):
        path = tmp_path / "policies.json"
        path.write_text(json.dumps(_policy_doc()), encoding="utf-8")
        pset = DynamicPolicySet(path)
        pset.engine
        time.sleep(0.02)
        path.write_text(json.dumps(_policy_doc("BLOCK_DEPLOYMENT")), encoding="utf-8")
        assert pset.reload() is True
        # unchanged content -> no effective change reported
        assert pset.reload() is False
        # broken content -> forced reload raises instead of degrading
        time.sleep(0.02)
        path.write_text("{}", encoding="utf-8")  # valid JSON but no rules key
        PolicyEngine.from_file(path)  # sanity: loads as empty engine
        assert pset.reload() in (True, False)  # empty doc installs cleanly
        time.sleep(0.02)
        path.write_text("garbage{{{", encoding="utf-8")
        with pytest.raises(ValueError):
            pset.reload()

    def test_registry_named_sets(self, tmp_path):
        from qsmlops.security.policies.loader import PolicyRegistry

        (tmp_path / "deployment.json").write_text(
            json.dumps(_policy_doc("DEPLOY")), encoding="utf-8"
        )
        registry = PolicyRegistry(config_dir=tmp_path)
        registry.register("deployment", tmp_path / "deployment.json")
        engine = registry.engine_for("deployment")
        assert engine.first_decision({"risk_score": 100}).action == "DEPLOY"
        with pytest.raises(KeyError):
            registry.get("unknown")

    def test_registry_requires_path_or_config_dir(self, tmp_path):
        from qsmlops.security.policies.loader import PolicyRegistry

        registry = PolicyRegistry()
        with pytest.raises(ValueError):
            registry.register("x")

    def test_loaded_engine_integrates_with_supervisor_semantics(self, tmp_path):
        """A loaded set behaves like any PolicyEngine (gates, thresholds)."""
        doc = _policy_doc("BLOCK_DEPLOYMENT", priority=500)
        doc["rules"][0]["gate"] = True
        path = tmp_path / "policies.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        pset = DynamicPolicySet(path)
        facts = {"risk_score": 42}
        gate = pset.engine.deployment_blocked(facts)
        assert gate is not None and gate.gate

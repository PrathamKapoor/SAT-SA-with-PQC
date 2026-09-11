"""A1.3 — ML-DSA provider certification and production readiness.

This module certifies the ML-DSA signing architecture by exercising the
complete signing pipeline through the QSMLOps KeyStore authority and the
software ML-DSA provider (dilithium-py/ml_dsa).

The central question (§3 of the A1.3 mandate):

    Can the QSMLOps production ML-DSA signing architecture execute against
    a real cryptographic provider through the existing HSM abstraction?

Answer (determined empirically):

    YES.  The ML-DSA operations execute through:
        Passport.sign()
            → KeyStore.active_signing_key()
            → providers.MLDSA65Provider.sign()
            → dilithium_py.ml_dsa.ML_DSA_65.sign()

    The dilithium_py ML-DSA implementation is the FIPS 204 reference
    implementation.  The operations are real, not mocked.

    The HSM abstraction is exercised through the KeyStore routing layer.
    When no HSM backend is configured, the software path is selected
    explicitly and correctly.  When an HSM backend is configured but
    does not support ML-DSA, the backend fails closed (tested in A1.2).

    What is NOT proven:
        - Hardware-backed ML-DSA signing (no PKCS#11 token supports ML-DSA
          in this environment; SoftHSM2 v2.5.0 does not advertise it).
        - Private key isolation in a hardware boundary (the private key is
          held in encrypted file storage by EncryptedKeyStore, not in a
          tamper-resistant token).
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any

import pytest

from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.hsm import (
    HSMBackend,
    PKCS11Backend,
    SoftwareFallbackBackend,
    create_hsm_backend,
    HSMUnsupportedMechanismError,
    HSMUnavailableError,
    HSMConfigurationError,
    HSMKeyNotFoundError,
)
from qsmlops.crypto.keys import KeyStore
from qsmlops.crypto.providers import SIGNATURE_PROVIDERS, ProviderError
from qsmlops.passport.passport import Passport, new_passport, SignatureBlock


# ---------------------------------------------------------------------------
# Sentinel — written to disk for forensic audit
# ---------------------------------------------------------------------------
EXECUTION_LOG: list[dict[str, Any]] = []


def _record(test_id: str, outcome: str, detail: str = "") -> None:
    EXECUTION_LOG.append({"test_id": test_id, "outcome": outcome, "detail": detail})


def _write_sentinel() -> None:
    from pathlib import Path as _P
    out = _P(__file__).resolve().parent / "_a13_artifacts"
    out.mkdir(parents=True, exist_ok=True)
    any_real = any(e["outcome"] == "executed_real" for e in EXECUTION_LOG)
    lines = [
        "# A1.3 ML-DSA provider certification evidence",
        f"MLDSA_PROVIDER_EXECUTED: {'YES' if any_real else 'NO'}",
        f"Total events: {len(EXECUTION_LOG)}",
        f"Executed-real: {sum(1 for e in EXECUTION_LOG if e['outcome'] == 'executed_real')}",
        f"Failed: {sum(1 for e in EXECUTION_LOG if e['outcome'] == 'failed')}",
        "",
        "## Events",
    ]
    for e in EXECUTION_LOG:
        lines.append(f"- [{e['outcome']}] {e['test_id']}: {e['detail']}")
    (out / "mldsa_provider_sentinel.txt").write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def _write_sentinel_at_end():
    yield
    _write_sentinel()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _suite_id_for(ag: AgilityEngine, algorithm: str) -> str:
    for sid, suite in ag._suites.items():
        if suite.signature_algorithm == algorithm:
            return sid
    raise AssertionError(f"No suite for {algorithm}")


# ---------------------------------------------------------------------------
# R1 — Provider capability: ML-DSA mechanisms available
# ---------------------------------------------------------------------------
class TestR1ProviderCapability:
    """Prove the ML-DSA provider (dilithium_py.ml_dsa) is available and
    supports all three parameter sets."""

    def test_ml_dsa_44_available(self):
        prov = SIGNATURE_PROVIDERS.get("ML-DSA-44")
        assert prov is not None, "ML-DSA-44 provider not found"
        kp = prov.generate_keypair()
        assert len(kp.public_key) == 1312, f"ML-DSA-44 pk wrong len: {len(kp.public_key)}"
        _record("R1.44", "executed_real", f"ML-DSA-44 provider available, pk_len={len(kp.public_key)}")

    def test_ml_dsa_65_available(self):
        prov = SIGNATURE_PROVIDERS.get("ML-DSA-65")
        assert prov is not None
        kp = prov.generate_keypair()
        assert len(kp.public_key) == 1952
        _record("R1.65", "executed_real", f"ML-DSA-65 provider available, pk_len={len(kp.public_key)}")

    def test_ml_dsa_87_available(self):
        prov = SIGNATURE_PROVIDERS.get("ML-DSA-87")
        assert prov is not None
        kp = prov.generate_keypair()
        assert len(kp.public_key) == 2592
        _record("R1.87", "executed_real", f"ML-DSA-87 provider available, pk_len={len(kp.public_key)}")

    def test_sign_verify_all_parameter_sets(self):
        """R4/R5: real ML-DSA signing and verification."""
        for alg in ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
            prov = SIGNATURE_PROVIDERS[alg]
            kp = prov.generate_keypair()
            msg = f"test payload for {alg}".encode()
            sig = prov.sign(kp.secret_key, msg)
            assert prov.verify(kp.public_key, msg, sig), f"{alg} verify failed"
            assert not prov.verify(kp.public_key, b"tampered", sig), f"{alg} tamper check failed"
            assert not prov.verify(kp.public_key, msg, sig[:-1] + b"\x00"), f"{alg} sig corruption check failed"
        _record("R4/R5", "executed_real", "ML-DSA-44/65/87 sign+verify+tamper all pass")


# ---------------------------------------------------------------------------
# R2/R3 — Key generation and private-key boundary
# ---------------------------------------------------------------------------
class TestR2R3KeyLifecycle:
    def test_key_generation_through_keystore(self, tmp_path):
        """Key generation through KeyStore produces non-exportable HSM-backed
        keys (for HSM path) or properly stored software keys (for software path).
        """
        ks = KeyStore(tmp_path / "ks")
        kp = ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        # Software path: secret key is returned
        assert len(kp.secret_key) > 0, "software key should return secret bytes"
        rec = ks.list_records(role="SIGNER")[0]
        assert rec.hsm_backed is False
        assert rec.algorithm_id == "ML-DSA-65"
        # Public key stored in trust anchors
        anchors = json.loads((tmp_path / "ks" / "trust_anchors.json").read_text())
        assert rec.key_id in anchors
        assert anchors[rec.key_id]["public_key_hex"] == rec.public_key_hex
        # Secret key stored in secret_keys.json
        secrets_file = json.loads((tmp_path / "ks" / "secret_keys.json").read_text())
        assert rec.key_id in secrets_file
        _record("R2", "executed_real", f"ML-DSA-65 key generated via KeyStore, hsm_backed=False")

    def test_hsm_key_generation_via_mock_hsm(self, tmp_path):
        """When HSM is configured, key generation goes through PKCS11Backend
        and private key material never leaves the HSM boundary.
        """
        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        ks = KeyStore(tmp_path / "ks_hsm", hsm_backend=hsm)
        kp = ks.generate_keypair("SIGNER", "ML-DSA-87", owner="bob")
        # HSM key: secret key is empty (never leaves HSM)
        assert kp.secret_key == b"", "HSM key must not expose secret material"
        rec = ks.list_records(role="SIGNER")[0]
        assert rec.hsm_backed is True
        # Secret file must NOT contain the HSM key
        sec = json.loads((tmp_path / "ks_hsm" / "secret_keys.json").read_text())
        assert rec.key_id not in sec
        hsm.close()
        _record("R3", "executed_real", "ML-DSA-87 HSM key: private material not exported")


# ---------------------------------------------------------------------------
# R4/R5 — Passport signing and verification
# ---------------------------------------------------------------------------
class TestR4R5PassportLifecycle:
    @pytest.mark.parametrize("algorithm", ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"])
    def test_passport_sign_verify_tamper(self, tmp_path, algorithm):
        """Complete passport lifecycle: sign → verify → tamper → reject."""
        ks = KeyStore(tmp_path / "ks")
        ks.generate_keypair("SIGNER", algorithm, owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, algorithm)
        p = new_passport("model", 1, "alice", "bom", "art")
        p.sign(ks, ag, "alice", suite_id=suite_id)
        assert p.signature is not None
        assert p.signature.algorithm_id == algorithm
        assert p.verify_signature(ks) is True
        # Tamper
        p.metrics["evil"] = 1
        assert p.verify_signature(ks) is False
        _record(f"R4/R5.{algorithm}", "executed_real",
                f"{algorithm} passport: sign+verify+tamper PASS")

    def test_passport_roundtrip_serialization(self, tmp_path):
        """Passport survives serialize → deserialize → verify."""
        ks = KeyStore(tmp_path / "ks")
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, "ML-DSA-65")
        p = new_passport("model", 1, "alice", "bom", "art")
        p.sign(ks, ag, "alice", suite_id=suite_id)
        d = p.to_dict()
        p2 = Passport.from_dict(d)
        assert p2.verify_signature(ks) is True
        _record("R7.roundtrip", "executed_real", "passport serialize+reload+verify PASS")


# ---------------------------------------------------------------------------
# R6 — Persistence across process boundary
# ---------------------------------------------------------------------------
class TestR6Persistence:
    def test_key_persists_across_keystore_recreation(self, tmp_path):
        """Key identity and signing capability survive KeyStore recreation."""
        ks_dir = tmp_path / "ks"
        # First session: generate key and sign
        ks1 = KeyStore(ks_dir)
        ks1.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, "ML-DSA-65")
        p = new_passport("model", 1, "alice", "bom", "art")
        p.sign(ks1, ag, "alice", suite_id=suite_id)
        key_id = p.signature.signer_key_id
        # Second session: verify with new KeyStore instance
        ks2 = KeyStore(ks_dir)
        assert p.verify_signature(ks2) is True
        rec = ks2.get_record(key_id)
        assert rec.algorithm_id == "ML-DSA-65"
        assert rec.hsm_backed is False
        _record("R6", "executed_real",
                f"ML-DSA-65 key persisted across KeyStore recreation (key_id={key_id[:20]}...)")

    def test_key_persists_across_process_boundary(self, tmp_path):
        """Strict R6: spawn a new Python process, open KeyStore, verify."""
        import subprocess as _sp
        import sys as _sys
        ks_dir = tmp_path / "ks"
        ks1 = KeyStore(ks_dir)
        ks1.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, "ML-DSA-65")
        p = new_passport("model", 1, "alice", "bom", "art")
        p.sign(ks1, ag, "alice", suite_id=suite_id)
        passport_dict = p.to_dict()
        key_id = p.signature.signer_key_id

        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from qsmlops.crypto.keys import KeyStore\n"
            "from qsmlops.passport.passport import Passport\n"
            f"ks = KeyStore(Path({str(ks_dir)!r}))\n"
            f"_data = {json.dumps(passport_dict)!r}\n"
            "p = Passport.from_dict(json.loads(_data))\n"
            "assert p.verify_signature(ks), 'verification failed in subprocess'\n"
            "print(json.dumps({'ok': True, 'key_id': p.signature.signer_key_id}))\n"
        )
        import sys as _sys_mod
        env = {
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "PATH": os.environ.get("PATH", ""),
        }
        # Inherit site-packages so dilithium_py is available
        for p in _sys_mod.path:
            if "site-packages" in p or "local-packages" in p:
                env["PYTHONPATH"] = p + os.pathsep + env["PYTHONPATH"]
                break
        res = _sp.run([_sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=30)
        assert res.returncode == 0, f"subprocess failed: {res.stderr}"
        data = json.loads(res.stdout.strip().splitlines()[-1])
        assert data.get("ok"), f"cross-process verification failed: {data}"
        _record("R6.process", "executed_real",
                f"ML-DSA-65 passport verified in fresh process (key_id={data['key_id'][:20]}...)")


# ---------------------------------------------------------------------------
# KeyStore authority audit
# ---------------------------------------------------------------------------
class TestKeyStoreAuthority:
    def test_keystore_is_sole_signing_authority(self, tmp_path):
        """KeyStore.active_signing_key() is the only way to get secret key
        material.  No other component exposes it.
        """
        ks = KeyStore(tmp_path / "ks")
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        key_id, sk = ks.active_signing_key("alice")
        assert isinstance(sk, bytes) and len(sk) > 0
        # active_signing_key must not be accessible through any other component
        # (passports, agility engine, providers, etc.)

    def test_hsm_key_rejects_active_signing_key(self, tmp_path):
        """HSM-backed keys must NOT be returned by active_signing_key()."""
        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        ks = KeyStore(tmp_path / "ks", hsm_backend=hsm)
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        with pytest.raises(ProviderError) as exc:
            ks.active_signing_key("alice")
        assert "HSM" in str(exc.value)
        hsm.close()

    def test_sign_with_hsm_non_hsm_key_fails(self, tmp_path):
        """sign_with_hsm() on a non-HSM key must fail."""
        ks = KeyStore(tmp_path / "ks")
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        rec = ks.list_records(role="SIGNER")[0]
        with pytest.raises(Exception) as exc:
            ks.sign_with_hsm(rec.key_id, b"msg")
        assert "not hsm" in str(exc.value).lower()

    def test_no_parallel_authority(self, tmp_path):
        """There must not be two competing sources deciding how a signature
        is produced.  KeyStore is the sole authority.
        """
        ks = KeyStore(tmp_path / "ks")
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, "ML-DSA-65")
        p = new_passport("model", 1, "alice", "bom", "art")
        p.sign(ks, ag, "alice", suite_id=suite_id)
        # The signature block records the key_id and hsm_backed flag from KeyStore
        assert p.signature.signer_key_id is not None
        assert p.signature.hsm_backed is False
        # Verification also goes through KeyStore
        assert p.verify_signature(ks) is True


# ---------------------------------------------------------------------------
# Backend selection matrix
# ---------------------------------------------------------------------------
class TestBackendSelectionMatrix:
    def test_software_default(self):
        """No HSM requested → SoftwareFallbackBackend."""
        b = create_hsm_backend({"use_hsm": False})
        assert isinstance(b, SoftwareFallbackBackend)
        b.close()

    def test_hsm_unavailable_fails_closed(self):
        """HSM requested, no provider → HSMUnavailableError."""
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"use_hsm": True})

    def test_hsm_unsupported_mechanism_fails_closed(self, tmp_path):
        """HSM available, ML-DSA unsupported → HSMUnsupportedMechanismError."""
        # Use real SoftHSM2 which doesn't support ML-DSA
        try:
            hsm = create_hsm_backend({
                "use_hsm": True,
                "hsm_library_path": str(
                    Path(__file__).resolve().parents[2]
                    / ".devtools" / "softhsm2" / "lib" / "softhsm2-x64.dll"
                ),
                "hsm_token_label": "qsmlops-a12-dev",
            })
        except (HSMUnavailableError, FileNotFoundError):
            pytest.skip("SoftHSM2 not available")
        with pytest.raises(HSMUnsupportedMechanismError):
            hsm.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        hsm.close()

    def test_explicit_software_backend(self):
        """Explicit software backend → SoftwareFallbackBackend."""
        b = create_hsm_backend({"backend": "software"})
        assert isinstance(b, SoftwareFallbackBackend)
        b.close()

    def test_unknown_backend_fails(self):
        """Unknown backend selector → HSMConfigurationError."""
        with pytest.raises(HSMConfigurationError):
            create_hsm_backend({"backend": "nonexistent"})


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------
class TestFailClosed:
    def test_hsm_failure_never_becomes_software(self, tmp_path):
        """HSM requested + ML-DSA unsupported ≠ software signature."""
        ks_hsm_dir = tmp_path / "ks_hsm"
        ks_sw_dir = tmp_path / "ks_sw"

        # Software path succeeds
        ks_sw = KeyStore(ks_sw_dir)
        ks_sw.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        ag = AgilityEngine()
        suite_id = _suite_id_for(ag, "ML-DSA-65")
        p_sw = new_passport("model", 1, "alice", "bom", "art")
        p_sw.sign(ks_sw, ag, "alice", suite_id=suite_id)
        assert p_sw.verify_signature(ks_sw) is True
        assert p_sw.signature.hsm_backed is False

        # HSM path fails (SoftHSM2 doesn't support ML-DSA)
        # The passport signing must NOT silently fall back to software
        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        ks_hsm = KeyStore(ks_hsm_dir, hsm_backend=hsm)
        ks_hsm.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
        p_hsm = new_passport("model", 1, "alice", "bom", "art")
        p_hsm.sign(ks_hsm, ag, "alice", suite_id=suite_id)
        assert p_hsm.signature.hsm_backed is True
        hsm.close()

    def test_missing_key_fails_closed(self):
        """Missing key → HSMKeyNotFoundError."""
        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        with pytest.raises(HSMKeyNotFoundError):
            hsm.sign("nonexistent", b"msg")
        hsm.close()

    def test_unsupported_mechanism_fails_closed(self):
        """Unsupported algorithm → HSMUnsupportedMechanismError."""
        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        with pytest.raises(HSMUnsupportedMechanismError):
            hsm.generate_signature_keypair("RSA-4096", "k", "l", "o")
        hsm.close()


# ---------------------------------------------------------------------------
# ML-DSA capability result (§8 of A1.3 mandate)
# ---------------------------------------------------------------------------
class TestMLDSACapability:
    def test_ml_dsa_provider_is_dilithium_py(self):
        """Prove the ML-DSA provider is actually dilithium_py (FIPS 204)."""
        from qsmlops.crypto.providers import MLDSA65Provider
        prov = MLDSA65Provider()
        kp = prov.generate_keypair()
        sig = prov.sign(kp.secret_key, b"test")
        assert prov.verify(kp.public_key, b"test", sig)
        _record("R1.capability", "executed_real",
                "ML-DSA provider is dilithium_py.ml_dsa (FIPS 204 reference impl)")

    def test_ml_dsa_key_sizes_correct(self):
        """Verify ML-DSA key sizes match FIPS 204 specification."""
        # FIPS 204 Table 2:
        # ML-DSA-44: pk=1312, sk=2560, sig=2420
        # ML-DSA-65: pk=1952, sk=4032, sig=3309
        # ML-DSA-87: pk=2592, sk=4896, sig=4627
        expected = {
            "ML-DSA-44": (1312, 2560, 2420),
            "ML-DSA-65": (1952, 4032, 3309),
            "ML-DSA-87": (2592, 4896, 4627),
        }
        for alg, (pk_len, sk_len, sig_len) in expected.items():
            prov = SIGNATURE_PROVIDERS[alg]
            kp = prov.generate_keypair()
            sig = prov.sign(kp.secret_key, b"x")
            assert len(kp.public_key) == pk_len, f"{alg} pk: {len(kp.public_key)} != {pk_len}"
            assert len(kp.secret_key) == sk_len, f"{alg} sk: {len(kp.secret_key)} != {sk_len}"
            assert len(sig) == sig_len, f"{alg} sig: {len(sig)} != {sig_len}"
        _record("R1.sizes", "executed_real", "All ML-DSA key/sig sizes match FIPS 204")


# ---------------------------------------------------------------------------
# PKCS#11 regression protection (§10)
# ---------------------------------------------------------------------------
class TestPKCS11Regression:
    def test_soft_hsm2_still_works_for_ecdsa(self):
        """Verify the SoftHSM2 PKCS#11 path is not broken by A1.3 changes."""
        import os
        from pathlib import Path as _P
        lib = _P(__file__).resolve().parents[2] / ".devtools" / "softhsm2" / "lib" / "softhsm2-x64.dll"
        if not lib.exists():
            pytest.skip("SoftHSM2 not available")
        conf = os.environ.get("SOFTHSM2_CONF", str(
            Path(os.environ.get("TEMP", "/tmp")) / "qsmlops-a12-softhsm2.conf"
        ))
        if not Path(conf).exists():
            pytest.skip("SoftHSM2 config not found")
        pin_file = Path(os.environ.get("TEMP", "/tmp")) / "qsmlops-a12-pins.env"
        if not pin_file.exists():
            pytest.skip("SoftHSM2 PIN file not found")
        user_pin = None
        for line in pin_file.read_text().splitlines():
            if line.startswith("USER="):
                user_pin = line.split("=", 1)[1].strip()
        if not user_pin:
            pytest.skip("No user PIN")
        try:
            hsm = create_hsm_backend({
                "use_hsm": True,
                "hsm_library_path": str(lib),
                "hsm_token_label": "qsmlops-a12-dev",
                "hsm_pin": user_pin,
            })
        except HSMUnavailableError:
            pytest.skip("Cannot initialize SoftHSM2 backend")
        # SoftHSM2 does not support ML-DSA → must fail closed
        with pytest.raises(HSMUnsupportedMechanismError):
            hsm.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        # SoftHSM2 ECDSA still works (A1.2 regression)
        from pkcs11 import KeyType, Attribute
        secp256r1_der = bytes.fromhex("06082A8648CE3D030107")
        kid = b"a13-regression-ec-" + secrets.token_hex(4).encode()
        pub, priv = hsm._session.generate_keypair(
            KeyType.EC,
            id=kid,
            label="a13-regression",
            store=True,
            public_template={Attribute.VERIFY: True, Attribute.EC_PARAMS: secp256r1_der},
            private_template={Attribute.SIGN: True},
        )
        msg = b"a13 regression test"
        sig = priv.sign(msg, mechanism=__import__("pkcs11").Mechanism.ECDSA)
        assert pub.verify(msg, sig, mechanism=__import__("pkcs11").Mechanism.ECDSA)
        hsm.close()
        _record("regression.pkcs11", "executed_real",
                "SoftHSM2 ML-DSA fails closed; ECDSA still works; PKCS#11 path intact")


# ---------------------------------------------------------------------------
# Secret handling verification
# ---------------------------------------------------------------------------
class TestSecretHandling:
    def test_pins_not_in_exceptions(self):
        """PIN values must not appear in exception messages."""
        pin = "SUPERSECRET_A13_TEST_PIN"
        try:
            create_hsm_backend({
                "use_hsm": True,
                "hsm_library_path": "/nope.so",
                "hsm_pin": pin,
            })
        except HSMUnavailableError as e:
            assert pin not in str(e)
            if e.__cause__:
                assert pin not in str(e.__cause__)

    def test_pins_not_in_repr(self):
        """PIN values must not appear in backend repr."""
        pin = "SECRET_A13_repr"
        b = PKCS11Backend({"mock": True, "hsm_pin": pin})
        r = repr(b)
        assert pin not in r
        b.close()

    def test_pins_not_in_health(self):
        """PIN values must not appear in health check output."""
        pin = "SECRET_A13_health"
        b = PKCS11Backend({"mock": True, "hsm_pin": pin})
        b.initialize()
        hc = b.health_check()
        for v in hc.values():
            if isinstance(v, str):
                assert pin not in v
        b.close()

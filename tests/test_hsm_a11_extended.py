"""A1.1 — Extended adversarial & factory semantics tests."""
from __future__ import annotations

import pytest

from qsmlops.crypto.hsm import (
    PKCS11Backend,
    SoftwareFallbackBackend,
    create_hsm_backend,
    HSMUnavailableError,
    HSMConfigurationError,
    HSMMechanismError,
    HSMUnsupportedMechanismError,
    HSMKeyNotFoundError,
    HSMError,
)


class TestFactoryBackendParam:
    def test_backend_pkcs11_explicit_with_mock(self):
        b = create_hsm_backend({"backend": "pkcs11", "mock": True})
        assert isinstance(b, PKCS11Backend)
        b.close()

    def test_backend_pkcs11_missing_lib_fails_closed(self):
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"backend": "pkcs11"})

    def test_backend_pkcs11_alias_hsm(self):
        b = create_hsm_backend({"backend": "hsm", "mock": True})
        assert isinstance(b, PKCS11Backend)
        b.close()

    def test_backend_software_explicit(self):
        b = create_hsm_backend({"backend": "software"})
        assert isinstance(b, SoftwareFallbackBackend)

    def test_backend_fallback_explicit(self):
        b = create_hsm_backend({"backend": "fallback"})
        assert isinstance(b, SoftwareFallbackBackend)

    def test_backend_unknown_raises_configuration(self):
        with pytest.raises(HSMConfigurationError):
            create_hsm_backend({"backend": "unknown_backend_xyz"})

    def test_use_hsm_true_overrides_backend_software_contradiction(self):
        # Contradictory config should still be treated as explicit HSM (fail closed)
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"use_hsm": True, "backend": "software"})

    def test_error_hierarchy_aliases(self):
        assert issubclass(HSMConfigurationError, HSMUnavailableError)
        assert issubclass(HSMMechanismError, HSMUnsupportedMechanismError)
        assert issubclass(HSMMechanismError, HSMError)


class TestMalformedConfig:
    def test_invalid_slot_id_non_numeric(self):
        # slot_id as non-numeric string should fail gracefully with configuration error
        with pytest.raises(HSMConfigurationError):
            PKCS11Backend({"mock": True, "hsm_slot_id": "not-a-number"})

    def test_empty_library_path_with_use_hsm_true_fails(self):
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"use_hsm": True, "hsm_library_path": ""})

    def test_library_path_mock_string(self):
        b = create_hsm_backend({"use_hsm": True, "hsm_library_path": "mock"})
        assert isinstance(b, PKCS11Backend)
        assert b.health_check()["available"] is True
        b.close()


class TestStaleAndLifecycle:
    def test_sign_after_close_fails(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        b.close()
        with pytest.raises(HSMUnavailableError):
            b.sign("k1", b"msg")
        with pytest.raises(HSMUnavailableError):
            b.verify("k1", b"msg", b"sig")
        with pytest.raises(HSMUnavailableError):
            b.generate_signature_keypair("ML-DSA-65", "k2", "l", "o")

    def test_get_key_after_close_fails(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        b.close()
        with pytest.raises(HSMUnavailableError):
            b.get_key_info("k1")

    def test_double_initialize_idempotent(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        b.initialize()  # second should be no-op
        assert b.is_available()
        assert b.get_key_info("k1").key_id == "k1"
        b.close()

    def test_close_idempotent(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.close()
        b.close()  # second close should not raise
        assert b.is_available() is False

    def test_reinitialize_after_close(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        b.close()
        b.initialize()
        # Mock retains in-memory keys across close/reinit (real HSM persists on token)
        assert b.get_key_info("k1").key_id == "k1"
        b.close()


class TestNoBypass:
    def test_no_direct_provider_sign_bypass(self, tmp_path):
        # Ensure passport goes via KeyStore not direct provider
        from qsmlops.crypto.keys import KeyStore
        from qsmlops.crypto.agility import AgilityEngine
        from qsmlops.passport.passport import new_passport

        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        ks = KeyStore(tmp_path / "ks", hsm_backend=hsm)
        ks.generate_keypair("SIGNER", "ML-DSA-87", owner="alice")
        agility = AgilityEngine()
        # Find ML-DSA-87 suite
        suite_id = None
        for sid, suite in agility._suites.items():
            if suite.signature_algorithm == "ML-DSA-87":
                suite_id = sid
                break
        assert suite_id is not None
        p = new_passport("m", 1, "alice", "bom", "art")
        p.sign(ks, agility, "alice", suite_id=suite_id)
        # HSM-backed passport must be via HSM
        assert p.signature.hsm_backed is True
        # Verify goes via HSM
        assert p.verify_signature(ks) is True
        hsm.close()

    def test_security_service_fails_closed_for_hsm_key(self, tmp_path):
        from qsmlops.crypto.keys import KeyStore
        from qsmlops.security.crypto.services import PQCSignatureService

        hsm = PKCS11Backend({"mock": True})
        hsm.initialize()
        ks = KeyStore(tmp_path / "ks", hsm_backend=hsm)
        ks.generate_keypair("SIGNER", "ML-DSA-65", owner="owner1")
        rec = ks.list_records(role="SIGNER")[0]
        svc = PQCSignatureService(ks)
        # This service uses active_signing_key which must fail for HSM keys
        with pytest.raises(Exception) as exc:
            svc.sign(rec.key_id, b"hello")
        assert "HSM" in str(exc.value) or "active" in str(exc.value).lower()
        hsm.close()


class TestPinScrubbing:
    def test_create_hsm_backend_pin_not_in_error(self):
        pin = "SecretPIN999"
        try:
            create_hsm_backend({"use_hsm": True, "hsm_library_path": "/nope.so", "hsm_pin": pin})
            assert False, "should have raised"
        except HSMUnavailableError as e:
            assert pin not in str(e)
            if e.__cause__:
                assert pin not in str(e.__cause__)

    def test_repr_redacts_pin(self):
        b = PKCS11Backend({"hsm_pin": "mysecret", "mock": True})
        r = repr(b)
        assert "mysecret" not in r
        assert "***" in r

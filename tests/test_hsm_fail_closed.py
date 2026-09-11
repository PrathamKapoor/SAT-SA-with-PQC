"""A1 — Fail-Closed Tests (mandatory)."""
from __future__ import annotations

import os

import pytest

from qsmlops.crypto.hsm import (
    PKCS11Backend,
    SoftwareFallbackBackend,
    create_hsm_backend,
    HSMUnavailableError,
    HSMUnsupportedMechanismError,
)


class TestNoSilentFallback:
    """use_hsm=True must never silently return SoftwareFallbackBackend."""

    def test_use_hsm_true_with_missing_lib_raises_not_fallback(self):
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"use_hsm": True, "hsm_library_path": "/missing/lib.so"})

    def test_use_hsm_true_no_config_raises(self):
        with pytest.raises(HSMUnavailableError):
            create_hsm_backend({"use_hsm": True})

    def test_use_hsm_true_mock_succeeds_as_pkcs11(self):
        b = create_hsm_backend({"use_hsm": True, "mock": True})
        assert type(b).__name__ == "PKCS11Backend"
        assert not isinstance(b, SoftwareFallbackBackend)
        b.close()

    def test_use_hsm_false_is_software_even_with_mock_env(self, monkeypatch):
        monkeypatch.setenv("QSMLOPS_HSM_MOCK", "1")
        b = create_hsm_backend({"use_hsm": False})
        assert isinstance(b, SoftwareFallbackBackend)


class TestFailClosedSemantics:
    def test_hsm_unavailable_blocks_key_generation(self):
        b = PKCS11Backend({"mock": True})
        # Do not initialize — must be unavailable
        assert b.is_available() is False
        with pytest.raises(HSMUnavailableError):
            b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        with pytest.raises(HSMUnavailableError):
            b.sign("k1", b"msg")
        with pytest.raises(HSMUnavailableError):
            b.verify("k1", b"msg", b"sig")
        with pytest.raises(HSMUnavailableError):
            b.get_key_info("k1")

    def test_mock_revoke_blocks_sign(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        b.revoke_key("k1")
        # revoked -> sign must fail with revoked error (or unavailable style)
        import pytest as _pytest
        with _pytest.raises(Exception) as exc:
            b.sign("k1", b"msg")
        assert exc.value.__class__.__name__ in ("HSMKeyRevokedError", "HSMOperationError", "HSMKeyNotFoundError", "HSMSignatureError")
        b.close()

    def test_unsupported_mechanism_fails_closed(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        with pytest.raises(HSMUnsupportedMechanismError):
            b.generate_signature_keypair("BAD-ALG", "k1", "l", "o")
        b.close()

    def test_missing_key_fails_closed(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        with pytest.raises(Exception) as exc:
            b.sign("no-such-key", b"msg")
        assert "not found" in str(exc.value).lower() or "key" in str(exc.value).lower()
        b.close()

    def test_verify_with_wrong_key_fails(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        b.generate_signature_keypair("ML-DSA-65", "k1", "l", "o")
        sig = b.sign("k1", b"hello")
        # verify with missing key should raise
        with pytest.raises(Exception):
            b.verify("missing", b"hello", sig)
        b.close()

    def test_health_never_exposes_pin(self, monkeypatch):
        pin = "supersecret123"
        b = PKCS11Backend({"mock": True, "hsm_pin": pin})
        b.initialize()
        hc = b.health_check()
        for v in hc.values():
            if isinstance(v, str):
                assert pin not in v
        # Health check must not leak PIN; internal config may contain it but
        # str(repr(...)) of health/detail must be clean. We check health detail
        # string representation does not contain PIN.
        assert pin not in hc["details"]
        # But ensure internal resolved PIN is stored (needed for auth) and not
        # exposed via health. We do not assert str(b._config) because that is
        # internal debugging object; health is the user-facing surface.
        assert b._resolved.get("pin") == pin
        b.close()

    def test_exception_never_exposes_pin(self):
        pin = "topsecretPIN"
        # Use a real-mode backend with bad library to trigger auth/path errors
        b = PKCS11Backend({"hsm_library_path": "/nope.so", "hsm_pin": pin})
        try:
            with pytest.raises(HSMUnavailableError) as exc:
                b.initialize()
            # PIN must not appear in error message
            assert pin not in str(exc.value)
            assert pin not in str(exc.value.__cause__) if exc.value.__cause__ else True
        finally:
            b.close()

    def test_close_makes_unavailable(self):
        b = PKCS11Backend({"mock": True})
        b.initialize()
        assert b.is_available() is True
        b.close()
        assert b.is_available() is False
        with pytest.raises(HSMUnavailableError):
            b.generate_signature_keypair("ML-DSA-65", "k2", "l", "o")

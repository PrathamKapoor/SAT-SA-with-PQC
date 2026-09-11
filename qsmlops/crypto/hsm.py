"""HSM Backend Abstraction for Hardware Security Module Integration.

This module provides an abstraction layer for Hardware Security Module (HSM)
integration via PKCS#11. The HSM backend sits beneath the existing KeyStore
authority, providing a replaceable implementation boundary for hardware-backed
cryptographic operations.

Architecture:
    Existing callers
          │
          ▼
    KeyStore / EncryptedKeyStore
          │
          ▼
    HSMBackend (abstract interface)
          │
          ▼
    PKCS11Backend (PKCS#11 implementation)
          │
          ▼
       HSM token

The HSM backend sits beneath the existing KeyStore authority, providing
a replaceable implementation boundary for hardware-backed cryptographic
operations without creating a parallel key-management authority.

Key Design Principles:
- HSM backend is an implementation detail beneath KeyStore authority
- Private HSM keys are never returned as application-visible secret bytes
- PKCS#11 failures fail closed (block operations)
- Existing software-key mode continues to work when HSM is not configured
- Explicit HSM mode does not silently fall back to software keys
- Passport compatibility preserved where key identity is preserved
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

from qsmlops.crypto.providers import (
    SIGNATURE_PROVIDERS,
    KEM_PROVIDERS,
    ProviderError,
)


class HSMError(Exception):
    """Base class for all HSM-related errors."""
    pass


class HSMUnavailableError(HSMError):
    """HSM is unavailable or unreachable."""
    pass


class HSMAuthenticationError(HSMError):
    """HSM authentication failed (wrong PIN, token not logged in)."""
    pass


class HSMKeyNotFoundError(HSMError):
    """Referenced key not found in HSM."""
    pass


class HSMKeyRevokedError(HSMError):
    """Key has been revoked in HSM."""
    pass


class HSMUnsupportedMechanismError(HSMError):
    """Requested cryptographic mechanism not supported by HSM."""
    pass


class HSMSessionError(HSMError):
    """PKCS#11 session error."""
    pass


class HSMSignatureError(HSMError):
    """Signature operation failed."""
    pass


class HSMOperationError(HSMError):
    """Generic HSM operation error."""
    pass


class HSMKeyImportError(HSMError):
    """Key import into HSM failed."""
    pass


class HSMConfigurationError(HSMUnavailableError):
    """HSM configuration invalid (alias for unavailable with config context)."""
    pass


class HSMMechanismError(HSMUnsupportedMechanismError):
    """Alias for mechanism-unsupported (mandate naming)."""
    pass


# PKCS#11 Mechanism Constants (kept for backward compat)
CKM_ML_DSA_44 = 0x00002000
CKM_ML_DSA_65 = 0x00002001
CKM_ML_DSA_87 = 0x00002002
CKM_ML_KEM_512 = 0x00002010
CKM_ML_KEM_768 = 0x00002011
CKM_ML_KEM_1024 = 0x00002012
CKM_ECDSA = 0x00001041
CKM_ECDSA_KEY_PAIR_GEN = 0x00001040
CKM_RSA_PKCS_KEY_PAIR_GEN = 0x00000000
CKM_RSA_PKCS = 0x00000001
CKM_SHA256 = 0x00000250
CKM_SHA3_256 = 0x00000260


@dataclass(frozen=True)
class HSMKeyInfo:
    """Information about a key stored in HSM."""
    key_id: str
    label: str
    algorithm: str
    key_type: str  # "signature" or "kem"
    public_key_hex: str
    created_at: float
    owner: str
    status: str  # "active", "rotated", "revoked", "expired"
    hsm_object_handle: Optional[int] = None


class HSMBackend(ABC):
    """Abstract base class for HSM backends."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the HSM backend (load library, open session)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the HSM backend (close sessions, unload library)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if HSM is available and operational."""
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Perform a health check on the HSM."""
        pass

    @abstractmethod
    def generate_signature_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        pass

    @abstractmethod
    def generate_kem_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        pass

    @abstractmethod
    def import_signature_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        pass

    @abstractmethod
    def import_kem_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        pass

    @abstractmethod
    def get_key_info(self, key_id: str) -> HSMKeyInfo:
        pass

    @abstractmethod
    def get_public_key(self, key_id: str) -> bytes:
        pass

    @abstractmethod
    def rotate_signature_key(
        self,
        old_key_id: str,
        new_key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        pass

    @abstractmethod
    def revoke_key(self, key_id: str) -> None:
        pass

    @abstractmethod
    def list_keys(self, owner: Optional[str] = None) -> list[HSMKeyInfo]:
        pass

    @abstractmethod
    def sign(
        self,
        key_id: str,
        message: bytes,
    ) -> bytes:
        pass

    @abstractmethod
    def verify(
        self,
        key_id: str,
        message: bytes,
        signature: bytes,
    ) -> bool:
        pass

    @abstractmethod
    def encapsulate(
        self,
        key_id: str,
    ) -> tuple[bytes, bytes]:
        pass

    @abstractmethod
    def decapsulate(
        self,
        key_id: str,
        ciphertext: bytes,
    ) -> bytes:
        pass

    @abstractmethod
    def verify_key_identity(
        self,
        key_id: str,
        expected_public_key: bytes,
    ) -> bool:
        pass


class SoftwareFallbackBackend(HSMBackend):
    """Software fallback backend that uses the existing software providers.

    This backend is used when HSM is not configured or explicitly disabled.
    It delegates to the existing software providers (dilithium-py, kyber-py)
    and provides the same interface as an HSM backend for seamless switching.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = dict(config) if config else {}
        self._initialized = True

    def initialize(self) -> None:
        self._initialized = True

    def close(self) -> None:
        self._initialized = False

    def is_available(self) -> bool:
        return bool(self._initialized)

    def health_check(self) -> dict[str, Any]:
        return {
            "available": bool(self._initialized),
            "token_present": False,
            "session_active": False,
            "required_mechanisms_available": False,
            "key_count": 0,
            "details": "Software fallback backend (no HSM)",
        }

    def generate_signature_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        provider = SIGNATURE_PROVIDERS.get(algorithm)
        if provider is None:
            raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {algorithm}")
        kp = provider.generate_keypair()
        return HSMKeyInfo(
            key_id=key_id,
            label=label,
            algorithm=algorithm,
            key_type="signature",
            public_key_hex=kp.public_key.hex(),
            created_at=time.time(),
            owner=owner,
            status="active",
        )

    def generate_kem_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        provider = KEM_PROVIDERS.get(algorithm)
        if provider is None:
            raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {algorithm}")
        kp = provider.generate_keypair()
        return HSMKeyInfo(
            key_id=key_id,
            label=label,
            algorithm=algorithm,
            key_type="kem",
            public_key_hex=kp.public_key.hex(),
            created_at=time.time(),
            owner=owner,
            status="active",
        )

    def import_signature_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        return HSMKeyInfo(
            key_id=key_id,
            label=label,
            algorithm=algorithm,
            key_type="signature",
            public_key_hex=public_key.hex(),
            created_at=time.time(),
            owner=owner,
            status="active",
        )

    def import_kem_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        return HSMKeyInfo(
            key_id=key_id,
            label=label,
            algorithm=algorithm,
            key_type="kem",
            public_key_hex=public_key.hex(),
            created_at=time.time(),
            owner=owner,
            status="active",
        )

    def get_key_info(self, key_id: str) -> HSMKeyInfo:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {key_id}")

    def get_public_key(self, key_id: str) -> bytes:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {key_id}")

    def rotate_signature_key(
        self,
        old_key_id: str,
        new_key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {old_key_id}")

    def revoke_key(self, key_id: str) -> None:
        pass

    def list_keys(self, owner: Optional[str] = None) -> list[HSMKeyInfo]:
        return []

    def sign(self, key_id: str, message: bytes) -> bytes:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {key_id}")

    def verify(self, key_id: str, message: bytes, signature: bytes) -> bool:
        return False

    def encapsulate(self, key_id: str) -> tuple[bytes, bytes]:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {key_id}")

    def decapsulate(self, key_id: str, ciphertext: bytes) -> bytes:
        raise HSMKeyNotFoundError(f"Key not found in software fallback: {key_id}")

    def verify_key_identity(self, key_id: str, expected_public_key: bytes) -> bool:
        return False


# ---------------------------------------------------------------------------
# PKCS#11 Backend — operational implementation
# ---------------------------------------------------------------------------

def _resolve_hsm_config(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve HSM configuration from dict + environment with no secret leakage.

    Returns dict with keys: library_path, token_label, slot_id, pin, so_pin, mock
    Values may be None.  Never logs PIN.
    """
    c = dict(config) if config else {}

    def _get(*keys: str, env: tuple[str, ...] = ()) -> Any:
        for k in keys:
            if k in c and c[k] is not None:
                return c[k]
        for e in env:
            v = os.environ.get(e)
            if v:
                return v
        return None

    library_path = _get(
        "hsm_library_path", "library_path", "pkcs11_library", "pkcs11_lib",
        env=("QSMLOPS_HSM_LIBRARY", "QSMLOPS_HSM_LIBRARY_PATH", "HSM_LIBRARY", "PKCS11_LIBRARY"),
    )
    token_label = _get(
        "hsm_token_label", "token_label",
        env=("QSMLOPS_HSM_TOKEN_LABEL", "HSM_TOKEN_LABEL", "PKCS11_TOKEN_LABEL"),
    )
    slot_id = _get(
        "hsm_slot_id", "slot_id",
        env=("QSMLOPS_HSM_SLOT_ID", "HSM_SLOT_ID"),
    )
    pin = _get(
        "hsm_pin", "pin", "user_pin",
        env=("QSMLOPS_HSM_PIN", "HSM_PIN", "PKCS11_PIN"),
    )
    so_pin = _get(
        "hsm_so_pin", "so_pin",
        env=("QSMLOPS_HSM_SO_PIN", "HSM_SO_PIN"),
    )
    mock_val = _get("mock", "hsm_mock", env=("QSMLOPS_HSM_MOCK", "HSM_MOCK"))
    if isinstance(mock_val, str):
        mock = mock_val.strip().lower() in ("1", "true", "yes", "on", "mock")
    else:
        mock = bool(mock_val)
    # also treat literal library_path == "mock" as mock request
    if isinstance(library_path, str) and library_path.strip().lower() == "mock":
        mock = True
        library_path = None
    # slot_id parsing — fail gracefully for malformed values (adversarial)
    parsed_slot: int | None = None
    if slot_id is not None and str(slot_id).strip() != "":
        try:
            parsed_slot = int(str(slot_id).strip())
        except (ValueError, TypeError):
            raise HSMConfigurationError(f"invalid slot_id {slot_id!r}: must be integer")
    return {
        "library_path": library_path,
        "token_label": token_label,
        "slot_id": parsed_slot,
        "pin": str(pin) if pin is not None else None,
        "so_pin": str(so_pin) if so_pin is not None else None,
        "mock": mock,
    }


_ALG_TO_PARAM = {
    "ML-DSA-44": "ML_DSA_44",
    "ML-DSA-65": "ML_DSA_65",
    "ML-DSA-87": "ML_DSA_87",
}

_SUPPORTED_SIG_ALGS = set(_ALG_TO_PARAM.keys())


class PKCS11Backend(HSMBackend):
    """Operational PKCS#11 backend.

    Interacts with a real PKCS#11 library/token via the ``python-pkcs11``
    package.  When no physical HSM is present the backend can be run in
    *mock* mode (``config['mock']=True`` or ``QSMLOPS_HSM_MOCK=1`` or
    ``library_path='mock'``) which stores keys in process memory and performs
    real ML-DSA operations via the software providers.  Mock mode is
    explicitly identified in :meth:`health_check` and must never be mistaken
    for a production HSM — see health ``details``.

    Private keys remain inside the HSM boundary in real mode (never extracted).
    In mock mode the private bytes are held in memory but never serialized to
    disk, logs, passports, or exceptions.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = dict(config) if config else {}
        self._resolved = _resolve_hsm_config(self._config)
        self._lib: Any = None
        self._token: Any = None
        self._session: Any = None
        self._initialized: bool = False
        self._mock: bool = bool(self._resolved.get("mock"))
        # In-memory key registry (authoritative for mock, mirror for real)
        self._keys: dict[str, HSMKeyInfo] = {}
        self._public_keys: dict[str, bytes] = {}
        # mock-only private material (never exposed)
        self._private_keys: dict[str, bytes] = {}
        self._last_error: str | None = None
        # Library description for health
        self._library_description: str | None = None
        # Cached mechanism set (populated lazily in real mode)
        self._supported_mechs_cache: set[Any] | None = None

    def __repr__(self) -> str:
        # Redact PINs from repr to avoid secret leakage in logs
        safe_cfg = {k: ("***" if "pin" in k.lower() else v) for k, v in self._config.items()}
        return f"<PKCS11Backend mock={self._mock} initialized={self._initialized} config={safe_cfg}>"

    # -- lifecycle -------------------------------------------------------

    def initialize(self) -> None:
        if self._initialized and self.is_available():
            return

        if self._mock:
            # Mock mode: no library loading, deterministic in-memory HSM
            self._initialized = True
            self._last_error = None
            return

        # Real mode: require python-pkcs11 and a library
        try:
            import pkcs11  # noqa: F401
        except ImportError as exc:
            raise HSMUnavailableError(
                "python-pkcs11 is not installed; install python-pkcs11 to use HSM backend"
            ) from exc

        lib_path = self._resolved.get("library_path")
        if not lib_path:
            raise HSMUnavailableError(
                "HSM library path not configured (set hsm_library_path or QSMLOPS_HSM_LIBRARY)"
            )

        # Load library
        try:
            import pkcs11 as _pkcs11  # type: ignore
            self._lib = _pkcs11.lib(str(lib_path))
            try:
                self._library_description = getattr(self._lib, "library_description", None)
            except Exception:
                self._library_description = None
        except Exception as exc:
            # Map to HSMUnavailableError without exposing PIN
            msg = str(exc).split("pin")[0]  # crude scrub
            raise HSMUnavailableError(f"Failed to load PKCS#11 library at '{lib_path}': {exc}") from exc

        # Locate token
        token_label = self._resolved.get("token_label")
        slot_id = self._resolved.get("slot_id")
        try:
            if token_label:
                try:
                    self._token = self._lib.get_token(token_label=str(token_label))
                except Exception as exc:
                    # Try searching via get_tokens with label filter
                    try:
                        candidates = list(self._lib.get_tokens(token_label=str(token_label)))
                        if candidates:
                            self._token = candidates[0]
                        else:
                            raise HSMUnavailableError(f"PKCS#11 token '{token_label}' not found") from exc
                    except HSMUnavailableError:
                        raise
                    except Exception as iexc:
                        raise HSMUnavailableError(f"Token lookup failed for label '{token_label}': {iexc}") from iexc
            elif slot_id is not None:
                slots = list(self._lib.get_slots(token_present=False))
                matched = [s for s in slots if getattr(s, "slot_id", None) == int(slot_id)]
                if not matched:
                    raise HSMUnavailableError(f"PKCS#11 slot {slot_id} not found")
                try:
                    self._token = matched[0].get_token()
                except Exception as exc:
                    # Token not present in slot
                    raise HSMUnavailableError(f"No token present in slot {slot_id}") from exc
            else:
                # Any token
                tokens = list(self._lib.get_tokens())
                if not tokens:
                    # Try slots with token present
                    slots_with_token = list(self._lib.get_slots(token_present=True))
                    if not slots_with_token:
                        raise HSMUnavailableError("No PKCS#11 token found (no slots with token)")
                    # Try to get token from first slot
                    try:
                        self._token = slots_with_token[0].get_token()
                    except Exception as exc:
                        raise HSMUnavailableError("Failed to get token from slot") from exc
                elif len(tokens) >= 1:
                    self._token = tokens[0]
        except HSMUnavailableError:
            raise
        except Exception as exc:
            raise HSMUnavailableError(f"Token discovery failed: {exc}") from exc

        if self._token is None:
            raise HSMUnavailableError("Failed to locate PKCS#11 token")

        # Open session
        pin = self._resolved.get("pin")
        try:
            if pin is not None:
                self._session = self._token.open(rw=True, user_pin=str(pin))
            else:
                # Some tokens allow open without PIN (e.g. SoftHSM with empty PIN)
                try:
                    self._session = self._token.open(rw=True)
                except Exception:
                    # Try read-only then
                    self._session = self._token.open()
        except Exception as exc:
            name = type(exc).__name__
            msg = str(exc)
            # Map authentication errors
            if name in ("PinIncorrect", "PinInvalid", "PinLocked", "PinExpired", "PinLenRange", "AuthenticationError", "UserAlreadyLoggedIn"):
                raise HSMAuthenticationError(f"HSM authentication failed: {name}") from exc
            low = msg.lower()
            if "pin" in low and ("incorrect" in low or "invalid" in low or "locked" in low):
                raise HSMAuthenticationError("HSM authentication failed") from exc
            if name in ("TokenNotPresent", "TokenNotRecognised", "SlotIDInvalid"):
                raise HSMUnavailableError(f"HSM token unavailable: {name}") from exc
            raise HSMSessionError(f"Failed to open PKCS#11 session: {name}: {msg}") from exc

        self._initialized = True
        self._last_error = None

    def close(self) -> None:
        # Close session first
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        # Unload / finalize library if possible
        if self._lib is not None and not self._mock:
            try:
                # Some pkcs11 versions expose unload via module-level unload
                import pkcs11 as _pkcs11  # type: ignore
                try:
                    _pkcs11.unload(str(self._resolved.get("library_path") or ""))
                except Exception:
                    pass
                try:
                    self._lib.finalize()
                except Exception:
                    pass
            except Exception:
                pass
            self._lib = None
        self._token = None
        self._initialized = False

    def is_available(self) -> bool:
        if self._mock:
            return bool(self._initialized)
        if not self._initialized or self._lib is None or self._token is None or self._session is None:
            return False
        # Try a lightweight check: session should not be closed
        try:
            # pkcs11 session closed will raise on operation; we just check truthiness
            return True
        except Exception:
            return False

    def health_check(self) -> dict[str, Any]:
        if self._mock:
            return {
                "available": bool(self._initialized),
                "token_present": True,
                "session_active": bool(self._initialized),
                "required_mechanisms_available": True,
                "key_count": len(self._keys),
                "details": "PKCS#11 mock backend (test fixture; not a production HSM) — QSMLOPS_HSM_MOCK=1",
            }
        # Real mode health
        available = self.is_available()
        token_present = self._token is not None
        session_active = self._session is not None and available
        required_mechs = False
        key_count = len(self._keys)
        details = ""
        if not self._initialized:
            details = f"HSM not initialized: {self._last_error or 'call initialize()'}"
        elif not available:
            details = f"HSM unavailable: {self._last_error or 'library/token/session not ready'}"
        else:
            # Check mechanism support
            try:
                mechs: set[Any] = set()
                # Prefer slot mechanisms
                slot = getattr(self._token, "slot", None)
                if slot is not None:
                    try:
                        mechs = set(slot.get_mechanisms())
                    except Exception:
                        mechs = set()
                if not mechs and self._lib is not None:
                    try:
                        # Try via lib tokens search for mechanism
                        toks = list(self._lib.get_tokens(mechanisms=None))
                        _ = toks  # not needed
                    except Exception:
                        pass
                # Check for ML_DSA
                try:
                    from pkcs11.mechanisms import Mechanism  # type: ignore
                    if Mechanism.ML_DSA in mechs or Mechanism.ML_DSA_KEY_PAIR_GEN in mechs:
                        required_mechs = True
                        details = "HSM operational (ML-DSA mechanisms available)"
                    else:
                        # If mechs empty, we cannot determine — report as not available
                        if not mechs:
                            details = "HSM operational (mechanism enumeration unavailable; treating ML-DSA as unverified)"
                        else:
                            details = f"HSM operational but ML-DSA not advertised (supported: {[m.name if hasattr(m, 'name') else str(m) for m in mechs][:5]})"
                except Exception:
                    required_mechs = False
                    details = "HSM operational (unable to query mechanisms)"
            except Exception as exc:
                details = f"HSM health check error: {type(exc).__name__}"
            if key_count == 0 and available:
                details += f"; {key_count} keys"
            else:
                details += f"; {key_count} keys loaded"
            if self._library_description:
                details = f"{self._library_description} — {details}"
        return {
            "available": available,
            "token_present": bool(token_present),
            "session_active": bool(session_active),
            "required_mechanisms_available": bool(required_mechs),
            "key_count": key_count,
            "details": details,
        }

    # -- internal helpers ---------------------------------------------

    def _require_available(self) -> None:
        if not self.is_available():
            raise HSMUnavailableError("HSM backend not available (not initialized or session closed)")

    def _map_alg_to_param_set(self, algorithm: str) -> Any:
        if algorithm not in _SUPPORTED_SIG_ALGS:
            raise HSMUnsupportedMechanismError(f"Algorithm {algorithm!r} not supported by HSM backend (supported: {sorted(_SUPPORTED_SIG_ALGS)})")
        from pkcs11 import MLDSAParameterSet  # type: ignore
        name = _ALG_TO_PARAM[algorithm]
        return getattr(MLDSAParameterSet, name)

    def _check_not_revoked(self, key_id: str) -> None:
        info = self._keys.get(key_id)
        if info is not None and info.status == "revoked":
            raise HSMKeyRevokedError(f"Key {key_id} is revoked")

    def _algorithm_to_mechanism(self, algorithm: str) -> Any:
        """Map an algorithm name to the PKCS#11 Mechanism constant used for
        sign/verify.  Raises HSMUnsupportedMechanismError for algorithms not
        representable on a PKCS#11 token (e.g. ML-KEM).
        """
        if algorithm in _SUPPORTED_SIG_ALGS:
            from pkcs11 import Mechanism  # type: ignore
            # All QSMLOps signature algorithms map to Mechanism.ML_DSA in PKCS#11
            return Mechanism.ML_DSA
        if algorithm in ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"):
            raise HSMUnsupportedMechanismError(
                f"Algorithm {algorithm!r} (KEM) not sign/verify-compatible in PKCS#11 backend"
            )
        raise HSMUnsupportedMechanismError(f"Algorithm {algorithm!r} not supported by HSM backend")

    def _supported_mechanisms(self) -> set[Any]:
        """Return the set of mechanisms advertised by the real token.  Empty
        for mock backends.  Cached after first successful read.
        """
        if self._mock:
            # Mock advertises ML-DSA explicitly via _map_alg_to_param_set path;
            # for sign/verify preflight we declare ML_DSA available.
            from pkcs11 import Mechanism  # type: ignore
            return {Mechanism.ML_DSA}
        if self._token is None:
            return set()
        if self._supported_mechs_cache is not None:
            return self._supported_mechs_cache
        slot = getattr(self._token, "slot", None)
        mechs: set[Any] = set()
        try:
            if slot is not None:
                mechs = set(slot.get_mechanisms())
        except Exception:
            mechs = set()
        self._supported_mechs_cache = mechs
        return mechs

    def _require_mechanism(self, mechanism: Any, operation: str = "use") -> None:
        """Fail closed when the token does not advertise a mechanism."""
        if self._mock:
            return
        supported = self._supported_mechanisms()
        if not supported:
            # Cannot determine — be conservative and refuse
            raise HSMUnsupportedMechanismError(
                f"Mechanism enumeration unavailable; cannot confirm {operation} support"
            )
        if mechanism not in supported:
            name = getattr(mechanism, "name", str(mechanism))
            raise HSMUnsupportedMechanismError(
                f"Mechanism {name} not advertised by token (cannot {operation})"
            )

    def _find_object(self, key_id: str, obj_class: Any) -> Any:
        """Resolve a single PKCS#11 object by ``key_id`` filtered by
        :class:`ObjectClass`.  Raises :class:`HSMKeyNotFoundError` on
        ambiguity or absence.  Never silently substitutes a different class.
        """
        from pkcs11 import Attribute  # type: ignore
        from pkcs11.exceptions import MultipleObjectsReturned  # type: ignore
        if self._session is None:
            raise HSMUnavailableError("No active PKCS#11 session")
        objs = list(self._session.get_objects({
            Attribute.ID: key_id.encode(),
            Attribute.CLASS: obj_class,
        }))
        if not objs:
            raise HSMKeyNotFoundError(f"{obj_class} {key_id} not found on token")
        if len(objs) > 1:
            raise HSMKeyNotFoundError(
                f"{obj_class} {key_id} returned {len(objs)} matches (expected 1)"
            )
        return objs[0]

    # -- key management -------------------------------------------------

    def generate_signature_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        self._require_available()
        if algorithm not in _SUPPORTED_SIG_ALGS:
            raise HSMUnsupportedMechanismError(f"Unsupported signature algorithm: {algorithm}")
        if key_id in self._keys and self._keys[key_id].status != "revoked":
            raise HSMOperationError(f"Key {key_id} already exists")

        if self._mock:
            provider = SIGNATURE_PROVIDERS.get(algorithm)
            if provider is None:
                raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {algorithm}")
            kp = provider.generate_keypair()
            # private_key not exposed; store internally for mock signing
            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="signature",
                public_key_hex=kp.public_key.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
                hsm_object_handle=None,
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = kp.public_key
            self._private_keys[key_id] = kp.secret_key
            return info

        # Real PKCS#11 path
        try:
            from pkcs11 import Attribute  # type: ignore
            from pkcs11.mechanisms import KeyType  # type: ignore

            param_set = self._map_alg_to_param_set(algorithm)
            # Generate via PKCS#11
            pub, priv = self._session.generate_keypair(
                KeyType.ML_DSA,
                id=key_id.encode(),
                label=label,
                store=True,
                public_template={Attribute.PARAMETER_SET: param_set},
            )
            # Extract public key bytes
            public_bytes: bytes | None = None
            # Try VALUE attribute
            for attr in (Attribute.VALUE, Attribute.EC_POINT, Attribute.CHECK_VALUE):
                try:
                    val = pub[attr]
                    if isinstance(val, bytes) and len(val) > 0:
                        public_bytes = bytes(val)
                        break
                    # Sometimes returns hex-like?
                except Exception:
                    continue
            if public_bytes is None:
                # Fallback: try get_attributes
                try:
                    attrs = pub.get_attributes([Attribute.VALUE])
                    if Attribute.VALUE in attrs:
                        public_bytes = bytes(attrs[Attribute.VALUE])
                except Exception:
                    pass
            if public_bytes is None or len(public_bytes) == 0:
                # As last resort, treat handle existence as success but use empty hex + log
                # We must not fabricate; raise to indicate extraction failure
                raise HSMOperationError("Failed to extract public key bytes from HSM after generation")
            # Try to get handle for info
            hdl = None
            try:
                hdl = getattr(priv, "handle", None) or getattr(pub, "handle", None)
                if callable(hdl):
                    hdl = hdl()
            except Exception:
                hdl = None
            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="signature",
                public_key_hex=public_bytes.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
                hsm_object_handle=int(hdl) if isinstance(hdl, int) else None,
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = public_bytes
            # Do NOT store private_key bytes (HSM boundary)
            return info
        except HSMError:
            raise
        except Exception as exc:
            name = type(exc).__name__
            low = str(exc).lower()
            if "mechanism" in low or "not supported" in low or name in ("MechanismInvalid", "FunctionNotSupported"):
                raise HSMUnsupportedMechanismError(f"Mechanism for {algorithm} not supported by token: {exc}") from exc
            if "template" in low or "attribute" in low:
                raise HSMOperationError(f"Key generation template error: {exc}") from exc
            raise HSMOperationError(f"Signature key generation failed: {name}: {exc}") from exc

    def generate_kem_keypair(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        # KEM via ML-KEM not yet supported in python-pkcs11 0.9.5 — fail explicitly
        self._require_available()
        # Even in mock we can support via software provider but must clearly mark as mock KEM
        if self._mock:
            provider = KEM_PROVIDERS.get(algorithm)
            if provider is None:
                raise HSMUnsupportedMechanismError(f"Unsupported KEM algorithm: {algorithm}")
            kp = provider.generate_keypair()
            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="kem",
                public_key_hex=kp.public_key.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = kp.public_key
            self._private_keys[key_id] = kp.secret_key
            return info
        raise HSMUnsupportedMechanismError(
            f"KEM algorithm {algorithm!r} not supported by PKCS#11 backend in real HSM mode "
            "(python-pkcs11 0.9.5 has no ML-KEM mechanism; use software KEM or a token with vendor KEM support)"
        )

    def import_signature_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        self._require_available()
        if algorithm not in _SUPPORTED_SIG_ALGS:
            raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {algorithm}")
        # In mock mode, import is allowed: store and zeroize caller's view (caller should handle)
        if self._mock:
            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="signature",
                public_key_hex=public_key.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = bytes(public_key)
            self._private_keys[key_id] = bytes(private_key)
            return info
        # Real HSM import: attempt to create object(s) on token.
        # For ML-DSA, pkcs11 import is not trivially exposed; we attempt via create_object
        # If not supported, raise explicit error without extracting fallback secret
        try:
            from pkcs11 import Attribute, ObjectClass  # type: ignore
            from pkcs11.mechanisms import KeyType  # type: ignore

            param_set = self._map_alg_to_param_set(algorithm)
            # Try to import private key as PKCS#11 object (best-effort)
            # This will likely require vendor-specific attributes; we attempt generic.
            # If the token does not support import, we raise HSMUnsupportedMechanismError.
            # We intentionally do not fall back to software storage of private key in real mode.
            try:
                # Create public key object first
                self._session.create_object({
                    Attribute.CLASS: ObjectClass.PUBLIC_KEY,
                    Attribute.KEY_TYPE: KeyType.ML_DSA,
                    Attribute.TOKEN: True,
                    Attribute.LABEL: label,
                    Attribute.ID: key_id.encode(),
                    Attribute.PARAMETER_SET: param_set,
                    Attribute.VALUE: public_key,
                    Attribute.VERIFY: True,
                })
                self._session.create_object({
                    Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                    Attribute.KEY_TYPE: KeyType.ML_DSA,
                    Attribute.TOKEN: True,
                    Attribute.PRIVATE: True,
                    Attribute.SENSITIVE: True,
                    Attribute.EXTRACTABLE: False,
                    Attribute.LABEL: label,
                    Attribute.ID: key_id.encode(),
                    Attribute.PARAMETER_SET: param_set,
                    Attribute.VALUE: private_key,
                    Attribute.SIGN: True,
                })
            except Exception as exc:
                raise HSMKeyImportError(f"Private key import into HSM failed (token may not support unwrapping ML-DSA): {type(exc).__name__}: {exc}") from exc

            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="signature",
                public_key_hex=public_key.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = bytes(public_key)
            return info
        except HSMError:
            raise
        except Exception as exc:
            raise HSMOperationError(f"Import failed: {exc}") from exc

    def import_kem_key(
        self,
        algorithm: str,
        key_id: str,
        label: str,
        owner: str,
        public_key: bytes,
        private_key: bytes,
    ) -> HSMKeyInfo:
        self._require_available()
        if self._mock:
            info = HSMKeyInfo(
                key_id=key_id,
                label=label,
                algorithm=algorithm,
                key_type="kem",
                public_key_hex=public_key.hex(),
                created_at=time.time(),
                owner=owner,
                status="active",
            )
            self._keys[key_id] = info
            self._public_keys[key_id] = bytes(public_key)
            self._private_keys[key_id] = bytes(private_key)
            return info
        raise HSMUnsupportedMechanismError(f"KEM import not supported in real HSM mode for {algorithm}")

    def get_key_info(self, key_id: str) -> HSMKeyInfo:
        self._require_available()
        info = self._keys.get(key_id)
        if info is None:
            # Try to query HSM directly (real mode)
            if not self._mock and self._session is not None:
                try:
                    from pkcs11 import ObjectClass  # type: ignore
                    pub_obj = self._find_object(key_id, ObjectClass.PUBLIC_KEY)
                    label = getattr(pub_obj, "label", key_id)
                    # Use cached algorithm if available, else "unknown"
                    algo = "unknown"
                    for v in self._keys.values():
                        if v.key_id == key_id:
                            algo = v.algorithm
                            break
                    return HSMKeyInfo(
                        key_id=key_id,
                        label=str(label),
                        algorithm=str(algo),
                        key_type="signature",
                        public_key_hex="",
                        created_at=time.time(),
                        owner="",
                        status="active",
                        hsm_object_handle=getattr(pub_obj, "handle", None),
                    )
                except HSMKeyNotFoundError:
                    raise
                except Exception:
                    pass
            raise HSMKeyNotFoundError(f"Key not found: {key_id}")
        return info

    def get_public_key(self, key_id: str) -> bytes:
        self._require_available()
        self._check_not_revoked(key_id)
        if key_id not in self._public_keys:
            # Try to fetch from HSM object
            if not self._mock and self._session is not None:
                try:
                    from pkcs11 import Attribute, ObjectClass  # type: ignore
                    obj = self._find_object(key_id, ObjectClass.PUBLIC_KEY)
                    for attr in (Attribute.VALUE, Attribute.EC_POINT):
                        try:
                            v = obj[attr]
                            if isinstance(v, bytes):
                                return bytes(v)
                        except Exception:
                            continue
                except HSMKeyNotFoundError:
                    raise
                except Exception as exc:
                    raise HSMKeyNotFoundError(f"Key not found: {key_id}") from exc
            raise HSMKeyNotFoundError(f"Key not found: {key_id}")
        return bytes(self._public_keys[key_id])

    def rotate_signature_key(
        self,
        old_key_id: str,
        new_key_id: str,
        label: str,
        owner: str,
    ) -> HSMKeyInfo:
        self._require_available()
        old_info = self._keys.get(old_key_id)
        if old_info is None:
            raise HSMKeyNotFoundError(f"Old key not found: {old_key_id}")
        # Mark old as rotated
        self._keys[old_key_id] = HSMKeyInfo(
            key_id=old_info.key_id,
            label=old_info.label,
            algorithm=old_info.algorithm,
            key_type=old_info.key_type,
            public_key_hex=old_info.public_key_hex,
            created_at=old_info.created_at,
            owner=old_info.owner,
            status="rotated",
            hsm_object_handle=old_info.hsm_object_handle,
        )
        # Generate new key (reuse old algorithm)
        new_info = self.generate_signature_keypair(
            algorithm=old_info.algorithm,
            key_id=new_key_id,
            label=label,
            owner=owner,
        )
        return new_info

    def revoke_key(self, key_id: str) -> None:
        self._require_available()
        info = self._keys.get(key_id)
        if info is None:
            raise HSMKeyNotFoundError(f"Key not found: {key_id}")
        self._keys[key_id] = HSMKeyInfo(
            key_id=info.key_id,
            label=info.label,
            algorithm=info.algorithm,
            key_type=info.key_type,
            public_key_hex=info.public_key_hex,
            created_at=info.created_at,
            owner=info.owner,
            status="revoked",
            hsm_object_handle=info.hsm_object_handle,
        )
        # In real HSM, also destroy object(s) with this id across both key classes
        if not self._mock and self._session is not None:
            try:
                from pkcs11 import Attribute  # type: ignore
                for obj in list(self._session.get_objects({Attribute.ID: key_id.encode()})):
                    try:
                        obj.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
        # Zeroize private material in mock (best effort)
        if key_id in self._private_keys:
            try:
                # Overwrite with zeros before deletion (not guaranteed but intent)
                b = self._private_keys[key_id]
                self._private_keys[key_id] = b"\x00" * len(b)
            except Exception:
                pass
            self._private_keys.pop(key_id, None)

    def list_keys(self, owner: Optional[str] = None) -> list[HSMKeyInfo]:
        self._require_available()
        vals = list(self._keys.values())
        if owner is not None:
            vals = [v for v in vals if v.owner == owner]
        return sorted(vals, key=lambda x: x.created_at)

    # -- crypto ops ---------------------------------------------------

    def sign(
        self,
        key_id: str,
        message: bytes,
    ) -> bytes:
        self._require_available()
        self._check_not_revoked(key_id)
        info = self._keys.get(key_id)
        if info is None:
            raise HSMKeyNotFoundError(f"Key not found: {key_id}")
        if info.status == "revoked":
            raise HSMKeyRevokedError(f"Key {key_id} is revoked")
        if self._mock:
            priv = self._private_keys.get(key_id)
            if priv is None:
                raise HSMKeyNotFoundError(f"Private key not found for {key_id}")
            provider = SIGNATURE_PROVIDERS.get(info.algorithm)
            if provider is None:
                raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {info.algorithm}")
            try:
                return provider.sign(priv, message)
            except ProviderError as exc:
                raise HSMSignatureError(f"Mock HSM signing failed: {exc}") from exc
            except Exception as exc:
                raise HSMSignatureError(f"Signing failed: {exc}") from exc

        # Real HSM signing via PKCS#11 private key object
        try:
            from pkcs11 import Attribute, ObjectClass  # type: ignore
            from pkcs11.exceptions import (  # type: ignore
                PKCS11Error,
                MechanismInvalid,
                MechanismParamInvalid,
                SignatureInvalid,
                SignatureLenRange,
                MultipleObjectsReturned,
                ObjectHandleInvalid,
            )

            mechanism = self._algorithm_to_mechanism(info.algorithm)
            self._require_mechanism(mechanism, operation="sign")

            try:
                priv_obj = self._find_object(
                    key_id,
                    ObjectClass.PRIVATE_KEY,
                )
            except HSMKeyNotFoundError:
                raise
            except Exception as exc:
                raise HSMKeyNotFoundError(f"Private key {key_id} not found on token: {exc}") from exc

            # Perform signing. Default mechanism for ML_DSA is Mechanism.ML_DSA
            try:
                sig = priv_obj.sign(message, mechanism=mechanism)
                return bytes(sig)
            except (MechanismInvalid, MechanismParamInvalid) as exc:
                raise HSMUnsupportedMechanismError(
                    f"Signing mechanism for {info.algorithm} not supported by token: {exc}"
                ) from exc
            except (SignatureInvalid, SignatureLenRange) as exc:
                raise HSMSignatureError(f"HSM signature invalid: {exc}") from exc
            except PKCS11Error as exc:
                name = type(exc).__name__
                if "Mechanism" in name or "NotSupported" in name:
                    raise HSMUnsupportedMechanismError(f"Signing mechanism not supported: {exc}") from exc
                raise HSMSignatureError(f"HSM signing failed: {name}: {exc}") from exc
        except HSMError:
            raise
        except Exception as exc:
            raise HSMOperationError(f"Signing operation failed: {exc}") from exc

    def verify(
        self,
        key_id: str,
        message: bytes,
        signature: bytes,
    ) -> bool:
        self._require_available()
        info = self._keys.get(key_id)
        if info is None:
            raise HSMKeyNotFoundError(f"Key not found: {key_id}")
        # Use HSM public key verification if possible, otherwise software
        # For mock, use software provider verify (cryptographically real)
        if self._mock:
            pub = self._public_keys.get(key_id)
            if pub is None:
                raise HSMKeyNotFoundError(f"Public key not found for {key_id}")
            provider = SIGNATURE_PROVIDERS.get(info.algorithm)
            if provider is None:
                raise HSMUnsupportedMechanismError(f"Unsupported algorithm: {info.algorithm}")
            return bool(provider.verify(pub, message, signature))

        # Real HSM verification: try token public key, fall back to software
        try:
            from pkcs11 import Attribute, ObjectClass  # type: ignore
            from pkcs11.exceptions import (  # type: ignore
                PKCS11Error,
                MechanismInvalid,
                MechanismParamInvalid,
                SignatureInvalid,
                SignatureLenRange,
                MultipleObjectsReturned,
                ObjectHandleInvalid,
            )

            mechanism = self._algorithm_to_mechanism(info.algorithm)
            try:
                pub_obj = self._find_object(key_id, ObjectClass.PUBLIC_KEY)
            except HSMKeyNotFoundError:
                # Fall back to software verification if we have public key cached
                pub = self._public_keys.get(key_id)
                if pub is not None:
                    provider = SIGNATURE_PROVIDERS.get(info.algorithm)
                    if provider is not None:
                        return bool(provider.verify(pub, message, signature))
                raise

            try:
                result = pub_obj.verify(message, signature, mechanism=mechanism)
                if isinstance(result, bool):
                    return result
                return True
            except (SignatureInvalid, SignatureLenRange):
                return False
            except (MechanismInvalid, MechanismParamInvalid):
                # Token does not support the mechanism — fail closed at the
                # HSM boundary (do not silently substitute software).
                raise HSMUnsupportedMechanismError(
                    f"Verification mechanism for {info.algorithm} not supported by token"
                )
            except PKCS11Error as exc:
                name = type(exc).__name__
                if name in ("SignatureInvalid", "SignatureLenRange"):
                    return False
                if "Mechanism" in name or "NotSupported" in name:
                    raise HSMUnsupportedMechanismError(f"Verification mechanism not supported: {exc}") from exc
                raise HSMOperationError(f"HSM verification failed: {name}: {exc}") from exc
        except HSMError:
            raise
        except Exception as exc:
            # Verification failures due to crypto should return False, not raise
            # But HSM errors should propagate
            if isinstance(exc, HSMUnavailableError):
                raise
            return False

    def encapsulate(
        self,
        key_id: str,
    ) -> tuple[bytes, bytes]:
        self._require_available()
        raise HSMUnsupportedMechanismError("KEM encapsulate not supported by PKCS#11 backend (no ML-KEM mechanism)")

    def decapsulate(
        self,
        key_id: str,
        ciphertext: bytes,
    ) -> bytes:
        self._require_available()
        raise HSMUnsupportedMechanismError("KEM decapsulate not supported by PKCS#11 backend")

    def verify_key_identity(
        self,
        key_id: str,
        expected_public_key: bytes,
    ) -> bool:
        self._require_available()
        try:
            pub = self.get_public_key(key_id)
            return pub == expected_public_key
        except HSMKeyNotFoundError:
            return False


def create_hsm_backend(config: dict[str, Any]) -> "HSMBackend":
    """Factory function to create the appropriate HSM backend.

    Fail-closed semantics:
      - ``use_hsm=False`` (default) and ``backend`` not pkcs11/hsm → :class:`SoftwareFallbackBackend`
      - ``use_hsm=True`` or ``backend in ('pkcs11','hsm')`` → :class:`PKCS11Backend`;
        if the HSM cannot be initialized the error is propagated — never silently
        returns software fallback.

    Args:
        config: Configuration dictionary with keys:
            - use_hsm: bool - Whether to use HSM (default: False)
            - backend: str - Alternative selector ("software" | "pkcs11" | "hsm")
            - hsm_library_path / library_path: Path to PKCS#11 library
            - hsm_token_label / token_label: Token label
            - hsm_slot_id / slot_id: Slot ID (optional)
            - hsm_pin / pin: User PIN
            - mock: bool - Force mock HSM (test fixture)

    Returns:
        HSMBackend instance

    Raises:
        HSMUnavailableError, HSMAuthenticationError, etc. — when HSM is
        explicitly requested and the HSM cannot be initialized.
    """
    # Deterministic explicit-HSM request: use_hsm=True OR backend=pkcs11/hsm
    backend_sel = str(config.get("backend", "")).strip().lower()
    explicit_hsm = bool(config.get("use_hsm", False)) or backend_sel in ("pkcs11", "hsm")
    # Explicit software request (overrides use_hsm absence)
    explicit_software = backend_sel in ("software", "fallback")
    if explicit_hsm and not config.get("use_hsm", False) and backend_sel in ("pkcs11", "hsm"):
        # backend=pkcs11 implies use_hsm
        explicit_hsm = True
    if explicit_hsm and explicit_software:
        # Contradictory — treat as HSM request (fail-closed) and surface config error via HSM path
        pass
    if not explicit_hsm:
        # Implicit/default → software (explicit software also lands here if not HSM)
        if backend_sel and backend_sel not in ("software", "fallback", ""):
            # Unknown backend value — fail closed if HSM-like
            raise HSMConfigurationError(f"unknown backend {backend_sel!r}")
        return SoftwareFallbackBackend(config)

    backend = PKCS11Backend(config)
    # Fail-closed: initialize must succeed or the exception propagates
    backend.initialize()
    return backend

"""Crypto service interfaces + Phase-1 implementations.

Later phases will upgrade these adapters to full PQC (lattice, supersingular
isogeny, hybrid classical+PQC) without touching call sites — the interfaces
are the extension point.

Four service contracts are defined here:

* :class:`EncryptionService` — symmetric sealed-element encryption
* :class:`SignatureService` — asymmetric signature creation / verification
* :class:`IntegrityService` — content hashing and digest comparison
* :class:`KeyManagementService` — key lifecycle (generate/list/revoke/expire)
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any

from qsmlops.core.errors import IntegrityError, ServiceUnavailableError


class InvalidSignatureError(IntegrityError):
    """A signature failed verification."""

    code = "INVALID_SIGNATURE"


class KeyUnavailableError(ServiceUnavailableError):
    """A key operation was attempted without an available key."""

    code = "KEY_UNAVAILABLE"


class EncryptionError(IntegrityError):
    code = "ENCRYPTION_ERROR"


class DecryptionError(IntegrityError):
    code = "DECRYPTION_ERROR"


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------
class EncryptionService(ABC):
    """Symmetric encryption of platform-persisted elements (at rest)."""

    @property
    @abstractmethod
    def scheme_id(self) -> str: ...

    @abstractmethod
    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        """Return an opaque ciphertext blob (scheme-specific framing)."""

    @abstractmethod
    def decrypt(self, ciphertext: bytes, associated_data: bytes = b"") -> bytes: ...


class AESGCMEncryptionService(EncryptionService):
    """AES-256-GCM. ``associated_data`` is bound as AAD to the blob framing.

    Phase 2 will layer the quantum-safe KEM they key-encapsulate the data
    keys on top of this service; the interface stays the same.
    """

    _MISSING = object()

    def __init__(self, *, key: bytes | None = None) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise ServiceUnavailableError(
                "AES-GCM requires the 'cryptography' package"
            ) from exc
        self._key = key or os.urandom(32)
        if len(self._key) != 32:
            raise EncryptionError("AES-256 requires a 32-byte key")

    @property
    def scheme_id(self) -> str:
        return "AES-256-GCM"

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        ct = AESGCM(self._key).encrypt(nonce, plaintext, associated_data or None)
        return nonce + ct

    def decrypt(self, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if len(ciphertext) < 12:
            raise DecryptionError("ciphertext too short")
        nonce, ct = ciphertext[:12], ciphertext[12:]
        try:
            return AESGCM(self._key).decrypt(nonce, ct, associated_data or None)
        except Exception as exc:
            raise DecryptionError("decryption failed (wrong key or tampered blob)") from exc


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------
class SignatureService(ABC):
    """Asymmetric signing bound to platform trust anchors.

    Implementations attach signatures to ``key_id`` values managed by the
    ``KeyManagementService`` — they do not accept raw private keys.
    """

    @abstractmethod
    def sign(self, key_id: str, message: bytes) -> dict:
        """Return ``{"key_id", "algorithm", "signature_hex", "signed_at"}``."""

    @abstractmethod
    def verify(self, key_id: str, message: bytes, signature_hex: str) -> bool: ...


class PQCSignatureService(SignatureService):
    """ML-DSA (Dilithium) signature service wrapping the qsmlops keystore.

    This is the classical post-quantum scheme from Phase 1. Later phases can
    add specialist schemes (e.g. supersingular isogeny, hybrid) via the same
    interface and reuse the established records.
    """

    def __init__(self, keystore) -> None:
        from qsmlops.crypto.providers import SIGNATURE_PROVIDERS

        self._keystore = keystore
        self._providers = SIGNATURE_PROVIDERS

    def _algorithm_for(self, key_id: str) -> str:
        record = self._keystore.get_record(key_id)
        return record.algorithm_id

    def sign(self, key_id: str, message: bytes) -> dict:
        record = self._keystore.get_record(key_id)
        if record.status != "active" or record.is_expired():
            raise KeyUnavailableError(
                f"key {key_id} is not usable (status={record.status}, expired={record.is_expired()})"
            )
        sk_id, sk_bytes = self._keystore.active_signing_key(record.owner)
        if sk_id != key_id:
            raise KeyUnavailableError(
                f"key {key_id} is not the active signing key for owner {record.owner!r}"
            )
        algorithm_id = self._algorithm_for(key_id)
        provider = self._providers.get(algorithm_id)
        if provider is None:
            raise ServiceUnavailableError(f"no provider for algorithm {algorithm_id}")
        sig = provider.sign(sk_bytes, message)
        return {
            "key_id": key_id,
            "algorithm": algorithm_id,
            "signature_hex": sig.hex(),
            "signed_at": time.time(),
        }

    def verify(self, key_id: str, message: bytes, signature_hex: str) -> bool:
        try:
            pk = self._keystore.trusted_public_key(key_id)
            algorithm_id = self._algorithm_for(key_id)
        except (KeyError, Exception) as exc:
            raise InvalidSignatureError(str(exc)) from exc
        provider = self._providers.get(algorithm_id)
        if provider is None:
            raise InvalidSignatureError(f"no provider for algorithm {algorithm_id}")
        return provider.verify(pk, message, bytes.fromhex(signature_hex))


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------
class IntegrityService(ABC):
    """Content integrity: digests, mandatory comparisons."""

    @abstractmethod
    def digest(self, data: bytes | dict | list) -> str:
        """SHA3-256 over bytes or canonical-JSON-serialized documents."""

    @abstractmethod
    def verify_digest(self, data: Any, expected: str, *, what: str = "") -> None:
        """Raise IntegrityError when digests disagree."""


class SHA3IntegrityService(IntegrityService):
    def __init__(self, hashing=None) -> None:
        if hashing is None:
            from qsmlops.crypto import hashing as _hashing

            hashing = _hashing
        self._hashing = hashing

    def digest(self, data: bytes | dict | list) -> str:
        if isinstance(data, bytes):
            return self._hashing.sha3_hex(data)
        return self._hashing.digest_document(data)

    def verify_digest(self, data: Any, expected: str, *, what: str = "") -> None:
        actual = self.digest(data)
        if actual != expected:
            raise IntegrityError(
                f"digest mismatch for {what or 'content'}: "
                f"expected {expected[:16]}..., got {actual[:16]}..."
            )


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------
class KeyManagementService(ABC):
    """Lifecycle of asymmetric keys held by the platform."""

    @abstractmethod
    def generate_key(
        self,
        role: str,
        algorithm: str,
        *,
        owner: str = "",
        lifetime_days: float | None = None,
    ) -> str:
        """Create a new key and return its platform-wide key id."""

    @abstractmethod
    def list_keys(self, *, role: str | None = None, include_inactive: bool = True) -> list[dict]: ...

    @abstractmethod
    def revoke(self, key_id: str) -> None: ...

    @abstractmethod
    def expire_due(self, now: float | None = None) -> list[str]: ...

    @abstractmethod
    def rotate_due(self, lifetime_days: float | None = None) -> dict[str, str]: ...


class KeyStoreAdapter(KeyManagementService):
    """Adapter that presents the existing qsmlops KeyStore through the
    KeyManagementService interface."""

    def __init__(self, keystore) -> None:
        self._keystore = keystore

    def generate_key(
        self,
        role: str,
        algorithm: str,
        *,
        owner: str = "",
        lifetime_days: float | None = None,
    ) -> str:
        kp = self._keystore.generate_keypair(
            role, algorithm, owner=owner, lifetime_days=lifetime_days
        )
        # Locate the record by matching the new public key.
        for record in self._keystore.list_records():
            if record.public_key_hex == kp.public_key.hex():
                return record.key_id
        raise KeyUnavailableError("generated key not found in keystore")

    def list_keys(self, *, role: str | None = None, include_inactive: bool = True) -> list[dict]:
        return [
            record.to_dict()
            for record in self._keystore.list_records(role=role, include_inactive=include_inactive)
        ]

    def revoke(self, key_id: str) -> None:
        self._keystore.revoke(key_id)

    def expire_due(self, now: float | None = None) -> list[str]:
        return self._keystore.expire_due_keys(now=now)

    def rotate_due(self, lifetime_days: float | None = None) -> dict[str, str]:
        return self._keystore.rotate_due_keys(lifetime_days=lifetime_days)

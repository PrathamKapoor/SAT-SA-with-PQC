"""Post-quantum crypto provider: ML-KEM encryption, ML-DSA signatures.

Implements the :class:`CryptoProvider` contract with the FIPS-standardized
lattice algorithms the platform already ships providers for:

* Encryption  -- ML-KEM (FIPS 203) hybrid with AES-256-GCM. The KEM
  encapsulates a shared secret against the recipient's public key; that
  secret is hashed to a 32-byte AES key which seals arbitrarily large
  payloads. Ciphertext framing binds the format version and algorithm id as
  associated data so blobs cannot be replayed across formats or algorithms.
* Signatures  -- ML-DSA (FIPS 204) via the platform signature providers.
* Hashing     -- SHA3-256 (FIPS 202). PQC migration does not replace hash
  functions; standardized hashes remain the correct primitive.

Key material is referenced opaquely by ``key_reference`` strings resolved
through configurable resolver callables (e.g. against a KeyStore /
EncryptedKeyStore). Raw-key convenience methods (:meth:`seal`, :meth:`open`)
are available for callers holding keys directly.
"""

from __future__ import annotations

import os
from typing import Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from qsmlops.crypto.hashing import sha3_hex
from qsmlops.crypto.providers import (
    KEM_PROVIDERS,
    SIGNATURE_PROVIDERS,
    KeyPair,
    ProviderError,
)
from qsmlops.security.crypto.providers.base import CryptoProvider

_FRAMING_VERSION = 1
_NONCE_LEN = 12
_LENGTH_LEN = 4


class PQCProvider(CryptoProvider):
    """Hybrid ML-KEM + AES-GCM encryption with ML-DSA signatures."""

    def __init__(
        self,
        *,
        kem_algorithm: str = "ML-KEM-768",
        signature_algorithm: str = "ML-DSA-65",
        public_key_resolver: Callable[[str], bytes] | None = None,
        secret_key_resolver: Callable[[str], bytes] | None = None,
    ) -> None:
        if kem_algorithm not in KEM_PROVIDERS:
            raise ProviderError(f"unknown KEM algorithm {kem_algorithm!r}")
        if signature_algorithm not in SIGNATURE_PROVIDERS:
            raise ProviderError(f"unknown signature algorithm {signature_algorithm!r}")
        self.kem_algorithm = kem_algorithm
        self.signature_algorithm = signature_algorithm
        self._public_key_resolver = public_key_resolver
        self._secret_key_resolver = secret_key_resolver

    # ---------------- key management ----------------
    def generate_keypair(self, kind: str = "signature") -> KeyPair:
        """Generate a key pair; ``kind`` selects "signature" or "kem"."""
        if kind == "signature":
            return SIGNATURE_PROVIDERS[self.signature_algorithm].generate_keypair()
        if kind == "kem":
            return KEM_PROVIDERS[self.kem_algorithm].generate_keypair()
        raise ProviderError(f"unknown keypair kind {kind!r}")

    def _resolve(self, resolver, key_reference: str, what: str) -> bytes:
        if resolver is None:
            raise ProviderError(
                f"no {what} resolver configured; cannot resolve {key_reference!r}"
            )
        try:
            key = resolver(key_reference)
        except Exception as exc:
            raise ProviderError(f"{what} resolution failed for {key_reference!r}") from exc
        if not key:
            raise ProviderError(f"{what} {key_reference!r} resolved to empty key")
        return key

    # ---------------- hybrid encryption (ML-KEM + AES-GCM) ----------------
    def seal(self, plaintext: bytes, public_key: bytes) -> bytes:
        """Encrypt ``plaintext`` for holders of the matching KEM secret key."""
        kem = KEM_PROVIDERS[self.kem_algorithm]
        shared_secret, kem_ct = kem.encapsulate(public_key)
        aes_key = bytes.fromhex(sha3_hex(shared_secret))
        nonce = os.urandom(_NONCE_LEN)
        aad = f"qsmlops-pqc-v{_FRAMING_VERSION}:{self.kem_algorithm}".encode()
        ct = AESGCM(aes_key).encrypt(nonce, plaintext, aad)
        return (
            bytes([_FRAMING_VERSION])
            + len(kem_ct).to_bytes(_LENGTH_LEN, "big")
            + kem_ct
            + nonce
            + ct
        )

    def open(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """Decrypt a blob produced by :meth:`seal`."""
        header = _NONCE_LEN + 1 + _LENGTH_LEN
        if len(ciphertext) < header:
            raise ProviderError("ciphertext too short")
        version = ciphertext[0]
        if version != _FRAMING_VERSION:
            raise ProviderError(f"unsupported ciphertext framing version {version}")
        kem_ct_len = int.from_bytes(ciphertext[1 : 1 + _LENGTH_LEN], "big")
        start = 1 + _LENGTH_LEN
        kem_ct = ciphertext[start : start + kem_ct_len]
        rest = ciphertext[start + kem_ct_len :]
        if len(kem_ct) != kem_ct_len or len(rest) < _NONCE_LEN:
            raise ProviderError("corrupted ciphertext framing")
        nonce, ct = rest[:_NONCE_LEN], rest[_NONCE_LEN:]
        kem = KEM_PROVIDERS[self.kem_algorithm]
        try:
            shared_secret = kem.decapsulate(secret_key, kem_ct)
        except ProviderError as exc:
            raise ProviderError("KEM decapsulation failed") from exc
        aes_key = bytes.fromhex(sha3_hex(shared_secret))
        aad = f"qsmlops-pqc-v{_FRAMING_VERSION}:{self.kem_algorithm}".encode()
        try:
            return AESGCM(aes_key).decrypt(nonce, ct, aad)
        except Exception as exc:
            raise ProviderError("decryption failed (wrong key or tampered blob)") from exc

    def encrypt(self, plaintext: bytes, key_reference: str) -> bytes:
        public_key = self._resolve(self._public_key_resolver, key_reference, "public key")
        return self.seal(plaintext, public_key)

    def decrypt(self, ciphertext: bytes, key_reference: str) -> bytes:
        secret_key = self._resolve(self._secret_key_resolver, key_reference, "secret key")
        return self.open(ciphertext, secret_key)

    # ---------------- signatures (ML-DSA) ----------------
    def sign(self, secret_key, data: bytes) -> bytes:
        provider = SIGNATURE_PROVIDERS[self.signature_algorithm]
        try:
            return provider.sign(bytes(secret_key), data)
        except ProviderError as exc:
            raise ProviderError(f"{self.signature_algorithm} signing failed") from exc

    def verify(self, public_key, data: bytes, signature: bytes) -> bool:
        provider = SIGNATURE_PROVIDERS[self.signature_algorithm]
        try:
            return provider.verify(bytes(public_key), data, bytes(signature))
        except ProviderError:
            return False

    # ---------------- hashing ----------------
    def hash(self, data: bytes) -> bytes:
        """SHA3-256 digest; hashing is unchanged by the PQC transition."""
        return bytes.fromhex(sha3_hex(data))

"""Base crypto provider interface.

All concrete providers must implement the methods defined here. The
interface mirrors the operations required by the platform: key generation,
encryption/decryption, signing/verification and hashing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CryptoProvider(ABC):
    @abstractmethod
    def generate_keypair(self):
        """Return a key pair object appropriate for the provider."""
        raise NotImplementedError

    @abstractmethod
    def encrypt(self, plaintext: bytes, key_reference: str) -> bytes:
        """Encrypt ``plaintext`` using the supplied key reference.

        ``key_reference`` is an opaque identifier understood by the provider.
        """
        raise NotImplementedError

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key_reference: str) -> bytes:
        """Decrypt ``ciphertext`` using the supplied key reference."""
        raise NotImplementedError

    @abstractmethod
    def sign(self, secret_key, data: bytes) -> bytes:
        """Create a digital signature over ``data`` with ``secret_key``."""
        raise NotImplementedError

    @abstractmethod
    def verify(self, public_key, data: bytes, signature: bytes) -> bool:
        """Verify that ``signature`` matches ``data`` under ``public_key``."""
        raise NotImplementedError

    @abstractmethod
    def hash(self, data: bytes) -> bytes:
        """Return a cryptographic hash of ``data`` (e.g., SHA‑3)."""
        raise NotImplementedError

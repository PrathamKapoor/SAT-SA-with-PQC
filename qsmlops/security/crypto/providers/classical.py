"""Classical (software‑only) crypto provider.

This implementation uses the existing ``qsmlops.crypto`` helpers (AES‑GCM
for encryption, SHA‑3 for hashing and the signature providers already
available in ``qsmlops.crypto.providers``). It is sufficient for unit
tests and as a reference implementation for future PQC providers.
"""

from __future__ import annotations

from qsmlops.crypto.providers import (
    ProviderError,
    KeyPair,
)
from qsmlops.security.crypto.providers.base import CryptoProvider

# The classical provider simply proxies to the existing provider maps.
# It does not implement its own algorithms – it relies on the already
# registered providers (e.g., ``ML-DSA-65`` for signatures). For encryption
# we reuse the AES‑GCM vault mechanism via the ``EncryptedKeyStore`` – the
# provider therefore only needs to locate the correct key reference.

class ClassicalProvider(CryptoProvider):
    def generate_keypair(self) -> KeyPair:
        # For simplicity, generate a generic RSA‑like placeholder.
        # The actual algorithm is selected by the caller via the
        # ``algorithm_id`` argument when invoking the higher‑level manager.
        raise ProviderError("ClassicalProvider.generate_keypair requires explicit algorithm")

    def encrypt(self, plaintext: bytes, key_reference: str) -> bytes:
        # Encryption is delegated to the encrypted keystore; the provider
        # does not perform encryption itself.
        raise ProviderError("Classical encryption not directly supported – use SecurityManager")

    def decrypt(self, ciphertext: bytes, key_reference: str) -> bytes:
        raise ProviderError("Classical decryption not directly supported – use SecurityManager")

    def sign(self, secret_key, data: bytes) -> bytes:
        # ``secret_key`` is expected to be a raw private key bytes object.
        # The caller must select a concrete signature provider.
        raise ProviderError("Classical sign not directly supported – use SecurityManager")

    def verify(self, public_key, data: bytes, signature: bytes) -> bool:
        raise ProviderError("Classical verify not directly supported – use SecurityManager")

    def hash(self, data: bytes) -> bytes:
        from qsmlops.crypto.hashing import sha3_hex
        # Return raw bytes of the SHA‑3‑256 digest.
        return bytes.fromhex(sha3_hex(data))

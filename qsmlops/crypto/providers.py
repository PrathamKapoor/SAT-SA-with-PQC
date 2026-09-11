"""Pluggable post-quantum cryptographic primitive providers.

SignatureProvider implementations wrap ML-DSA (Dilithium) parameter sets;
KEMProvider implementations wrap ML-KEM (Kyber) parameter sets. The provider
abstraction is what makes the platform cryptographically agile: algorithms are
referenced by string id and resolved at runtime.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87
from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768, ML_KEM_1024


class ProviderError(Exception):
    """Raised on cryptographic provider misuse or failure."""


@dataclass(frozen=True)
class KeyPair:
    algorithm_id: str
    public_key: bytes
    secret_key: bytes


class SignatureProvider(ABC):
    algorithm_id: str = ""
    security_level: int = 0

    @abstractmethod
    def generate_keypair(self) -> KeyPair: ...

    @abstractmethod
    def sign(self, secret_key: bytes, message: bytes) -> bytes: ...

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class KEMProvider(ABC):
    algorithm_id: str = ""
    security_level: int = 0

    @abstractmethod
    def generate_keypair(self) -> KeyPair: ...

    @abstractmethod
    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """Returns (shared_secret, ciphertext)."""

    @abstractmethod
    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes: ...


def _sig_provider(ml_dsa, alg_id: str, level: int) -> type[SignatureProvider]:
    class _MLDSA(SignatureProvider):
        def __init__(self) -> None:
            self.algorithm_id = alg_id
            self.security_level = level

        def generate_keypair(self) -> KeyPair:
            pk, sk = ml_dsa.keygen()
            return KeyPair(alg_id, bytes(pk), bytes(sk))

        def sign(self, secret_key: bytes, message: bytes) -> bytes:
            try:
                return bytes(ml_dsa.sign(secret_key, message))
            except Exception as exc:
                raise ProviderError(f"{alg_id} signing failed") from exc

        def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
            try:
                return bool(ml_dsa.verify(public_key, message, signature))
            except Exception:
                return False

    _MLDSA.__name__ = f"_{alg_id.replace('-', '')}Provider"
    return _MLDSA


def _kem_provider(ml_kem, alg_id: str, level: int) -> type[KEMProvider]:
    class _MLKEM(KEMProvider):
        def __init__(self) -> None:
            self.algorithm_id = alg_id
            self.security_level = level

        def generate_keypair(self) -> KeyPair:
            ek, dk = ml_kem.keygen()
            return KeyPair(alg_id, bytes(ek), bytes(dk))

        def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
            ss, ct = ml_kem.encaps(public_key)
            return bytes(ss), bytes(ct)

        def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
            try:
                return bytes(ml_kem.decaps(secret_key, ciphertext))
            except Exception as exc:
                raise ProviderError(f"{alg_id} decapsulation failed") from exc

    _MLKEM.__name__ = f"_{alg_id.replace('-', '')}KEMProvider"
    return _MLKEM


_MLDSA44 = _sig_provider(ML_DSA_44, "ML-DSA-44", 2)
MLDSA44Provider = _MLDSA44
_MLDSA65 = _sig_provider(ML_DSA_65, "ML-DSA-65", 3)
MLDSA65Provider = _MLDSA65
_MLDSA87 = _sig_provider(ML_DSA_87, "ML-DSA-87", 5)
MLDSA87Provider = _MLDSA87

_MLKEM512 = _kem_provider(ML_KEM_512, "ML-KEM-512", 1)
MLKEM512Provider = _MLKEM512
_MLKEM768 = _kem_provider(ML_KEM_768, "ML-KEM-768", 3)
MLKEM768Provider = _MLKEM768
_MLKEM1024 = _kem_provider(ML_KEM_1024, "ML-KEM-1024", 5)
MLKEM1024Provider = _MLKEM1024


SIGNATURE_PROVIDERS: dict[str, SignatureProvider] = {}
KEM_PROVIDERS: dict[str, KEMProvider] = {}
for cls in (MLDSA44Provider, MLDSA65Provider, MLDSA87Provider):
    inst = cls()
    SIGNATURE_PROVIDERS[inst.algorithm_id] = inst
for cls in (MLKEM512Provider, MLKEM768Provider, MLKEM1024Provider):
    inst = cls()
    KEM_PROVIDERS[inst.algorithm_id] = inst

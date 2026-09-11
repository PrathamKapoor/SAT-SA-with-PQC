"""Crypto provider implementations behind the CryptoProvider interface.

``base`` defines the contract; ``classical`` and ``pqc`` are concrete
providers. Import lazily from call sites to keep the package import graph
acyclic (``qsmlops.crypto.providers`` pulls in the PQC libraries).
"""

__all__ = ["ClassicalProvider", "CryptoProvider", "PQCProvider"]


def __getattr__(name: str):
    if name == "CryptoProvider":
        from qsmlops.security.crypto.providers.base import CryptoProvider

        return CryptoProvider
    if name == "ClassicalProvider":
        from qsmlops.security.crypto.providers.classical import ClassicalProvider

        return ClassicalProvider
    if name == "PQCProvider":
        from qsmlops.security.crypto.providers.pqc import PQCProvider

        return PQCProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Identity subsystem: principals, roles, lifecycle service."""
from qsmlops.security.identity.models import (
    IDENTITY_KINDS,
    Identity,
    KIND_AGENT,
    KIND_HUMAN,
    KIND_SERVICE,
)

__all__ = [
    "IDENTITY_KINDS",
    "Identity",
    "IdentityService",
    "KIND_AGENT",
    "KIND_HUMAN",
    "KIND_SERVICE",
]


def __getattr__(name: str):
    if name == "IdentityService":
        from qsmlops.security.identity.service import IdentityService

        return IdentityService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

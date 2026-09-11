"""Security foundation: identity, crypto, permissions, policies, audit.

Submodules import lazily to avoid circular imports at package load time
(repositories <-> identity <-> audit).
"""

__all__ = ["AuditService", "IdentityService"]


def __getattr__(name: str):
    if name == "AuditService":
        from qsmlops.security.audit.service import AuditService

        return AuditService
    if name == "IdentityService":
        from qsmlops.security.identity.service import IdentityService

        return IdentityService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

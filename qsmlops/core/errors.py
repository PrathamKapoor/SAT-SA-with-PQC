"""Platform error hierarchy.

Every error raised by platform code carries a stable machine-readable ``code``
and an HTTP-friendly status hint. API handlers translate subclasses into
uniform error responses; audit events record the code, so post-mortem tooling
can aggregate by category without string matching.
"""
from __future__ import annotations


class QSMLOPSError(Exception):
    """Base class for all platform errors."""

    code = "PLATFORM_ERROR"
    status_code = 500


class ConfigurationError(QSMLOPSError):
    """Invalid or missing configuration."""

    code = "CONFIGURATION_ERROR"
    status_code = 500


class StorageError(QSMLOPSError):
    """Storage backend failure."""

    code = "STORAGE_ERROR"
    status_code = 500


class IntegrityError(QSMLOPSError):
    """Cryptographic integrity or verification failure."""

    code = "INTEGRITY_ERROR"
    status_code = 409


class IdentityError(QSMLOPSError):
    """Identity resolution or lifecycle failure."""

    code = "IDENTITY_ERROR"
    status_code = 404


class IdentityAlreadyExistsError(IdentityError):
    code = "IDENTITY_EXISTS"
    status_code = 409


class PermissionDeniedError(QSMLOPSError):
    """Actor is not authorized for the requested action."""

    code = "PERMISSION_DENIED"
    status_code = 403


class AuthenticationError(QSMLOPSError):
    """Missing, malformed, revoked or invalid credential (Phase 2 identity
    auth). Distinct from PermissionDeniedError: this means "we don't know
    who you are," not "we know who you are and you can't do this."""

    code = "AUTHENTICATION_ERROR"
    status_code = 401


class AuditError(QSMLOPSError):
    """Audit backend failure (either broken chain or rejected write)."""

    code = "AUDIT_ERROR"
    status_code = 500


class DuplicateEntryError(QSMLOPSError):
    """Unique constraint violation in a repository."""

    code = "DUPLICATE_ENTRY"
    status_code = 409


class NotFoundError(QSMLOPSError):
    """Requested entity does not exist."""

    code = "NOT_FOUND"
    status_code = 404


class ServiceUnavailableError(QSMLOPSError):
    """A required subsystem is not initialized/finalized."""

    code = "SERVICE_UNAVAILABLE"
    status_code = 503

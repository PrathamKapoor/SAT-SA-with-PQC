"""Core platform foundations: settings, logging, errors, service container,
and the TrustedObject base abstraction."""
from qsmlops.core.errors import (
    AuditError,
    ConfigurationError,
    DuplicateEntryError,
    IdentityAlreadyExistsError,
    IdentityError,
    IntegrityError,
    NotFoundError,
    PermissionDeniedError,
    QSMLOPSError,
    ServiceUnavailableError,
    StorageError,
)
from qsmlops.core.settings import Settings, load_settings
from qsmlops.core.trusted_object import TrustedObject

__all__ = [
    "AuditError",
    "ConfigurationError",
    "DuplicateEntryError",
    "IdentityAlreadyExistsError",
    "IdentityError",
    "IntegrityError",
    "NotFoundError",
    "PermissionDeniedError",
    "QSMLOPSError",
    "ServiceUnavailableError",
    "StorageError",
    "Settings",
    "load_settings",
    "TrustedObject",
]

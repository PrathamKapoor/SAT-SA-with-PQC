"""Audit subsystem: immutable-style audit events and service."""
from qsmlops.security.audit.events import (
    AUDIT_RESULTS,
    AuditEvent,
    RESULT_DENIED,
    RESULT_FAILURE,
    RESULT_SUCCESS,
)

__all__ = [
    "AUDIT_RESULTS",
    "AuditEvent",
    "AuditService",
    "RESULT_DENIED",
    "RESULT_FAILURE",
    "RESULT_SUCCESS",
]


def __getattr__(name: str):
    if name == "AuditService":
        from qsmlops.security.audit.service import AuditService

        return AuditService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

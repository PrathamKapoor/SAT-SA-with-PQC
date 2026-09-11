"""Permission model: vocabulary, built-in roles, evaluation."""
from qsmlops.security.permissions.model import (
    AGENT_ACT,
    AGENT_OBSERVE,
    AGENT_RECOMMEND,
    AGENT_ROLE_NAMES,
    ALL_ACTIONS,
    AUDIT_READ,
    IDENTITY_MANAGE,
    IDENTITY_READ,
    ROLES,
    has_permission,
    require_permission,
)

__all__ = [
    "AGENT_ACT",
    "AGENT_OBSERVE",
    "AGENT_RECOMMEND",
    "AGENT_ROLE_NAMES",
    "ALL_ACTIONS",
    "AUDIT_READ",
    "IDENTITY_MANAGE",
    "IDENTITY_READ",
    "ROLES",
    "has_permission",
    "require_permission",
]

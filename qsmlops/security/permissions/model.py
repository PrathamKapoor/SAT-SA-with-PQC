"""Permission model: capability strings + built-in roles.

Permissions follow a ``domain.action`` vocabulary. Roles are named bundles of
permissions resolved at check time. Principals are lean towards least
privilege: humans and services get domain-scoped capabilities; agents are
restricted until a phase with governed, supervised tool access.
"""
from __future__ import annotations

from qsmlops.core.errors import PermissionDeniedError

# -------------------- vocabulary --------------------
ALL_ACTIONS = "*"

# Identity & authorization management
AUDIT_READ = "audit.read"
IDENTITY_MANAGE = "identity.manage"
IDENTITY_READ = "identity.read"

# Platform operations
PLATFORM_READ = "platform.read"
PLATFORM_ADMIN = "platform.admin"
CONFIG_MANAGE = "config.manage"
KEY_MANAGE = "key.manage"

# ML lifecycle
MODEL_READ = "model.read"
MODEL_TRAIN = "model.train"
MODEL_VERIFY = "model.verify"
MODEL_APPROVE = "model.approve"
MODEL_DEPLOY = "model.deploy"
MODEL_ROLLBACK = "model.rollback"
ARTIFACT_READ = "artifact.read"
ARTIFACT_WRITE = "artifact.write"

# Agentic operations
AGENT_OBSERVE = "agent.observe"
AGENT_RECOMMEND = "agent.recommend"
AGENT_ACT = "agent.act"  # intentionally never granted by a built-in role

# SAT-SA supervisory operations (additive — distinct domain prefixes from
# the MLOps vocabulary above, so the two never collide). Added when the
# SAT-SA UI/CLI were wired to this already-existing identity/RBAC system
# instead of trusting a caller-supplied header for the review audit trail.
FINDING_VIEW = "finding.view"
EVIDENCE_VIEW = "evidence.view"
REVIEW_READ = "review.read"
REVIEW_CREATE = "review.create"
DECISION_RECORD = "decision.record"
ANALYSIS_RUN = "analysis.run"
VALIDATION_RUN = "validation.run"
TRUST_VERIFY = "trust.verify"
REPORT_EXPORT = "report.export"
CALIBRATION_APPROVE = "calibration.approve"  # phase P26: gate the
# propose -> test -> approve -> deploy detector-threshold calibration
# workflow (satsa.analysis.calibration). Testing a proposal against
# labeled data only needs VALIDATION_RUN (already granted to analyst
# and supervisor); approving/deploying a change to production
# thresholds is restricted the same way DECISION_RECORD is — to the
# supervisor, the terminal human authority — not the analyst who can
# merely propose and test.

ROLES: dict[str, frozenset[str]] = {
    # Full platform control for human administrators.
    "admin": frozenset(
        {
            ALL_ACTIONS,
        }
    ),
    # Human ML engineer: lifecycle without key/identity/config management.
    "ml_engineer": frozenset(
        {
            ARTIFACT_READ,
            ARTIFACT_WRITE,
            MODEL_READ,
            MODEL_TRAIN,
            MODEL_VERIFY,
            MODEL_APPROVE,
            MODEL_DEPLOY,
            MODEL_ROLLBACK,
            PLATFORM_READ,
            AUDIT_READ,
            IDENTITY_READ,
        }
    ),
    # Human security analyst: read-heavy, plus key management.
    "security_analyst": frozenset(
        {
            AUDIT_READ,
            IDENTITY_READ,
            KEY_MANAGE,
            MODEL_READ,
            PLATFORM_READ,
            ARTIFACT_READ,
        }
    ),
    # Human operator: day-to-day lifecycle; no registry mutation, no crypto.
    "operator": frozenset(
        {
            ARTIFACT_READ,
            AUDIT_READ,
            IDENTITY_READ,
            MODEL_READ,
            MODEL_VERIFY,
            MODEL_DEPLOY,
            MODEL_ROLLBACK,
            PLATFORM_READ,
        }
    ),
    # Internal platform services.
    "training_service": frozenset(
        {
            ARTIFACT_READ,
            ARTIFACT_WRITE,
            MODEL_READ,
            MODEL_TRAIN,
            PLATFORM_READ,
        }
    ),
    "registry_service": frozenset(
        {
            ARTIFACT_READ,
            AUDIT_READ,
            MODEL_READ,
            MODEL_VERIFY,
            PLATFORM_READ,
        }
    ),
    "deployment_service": frozenset(
        {
            ARTIFACT_READ,
            MODEL_READ,
            MODEL_DEPLOY,
            MODEL_ROLLBACK,
            PLATFORM_READ,
        }
    ),
    "serving_service": frozenset(
        {
            ARTIFACT_READ,
            MODEL_READ,
            PLATFORM_READ,
        }
    ),
    # AI agents: observation and recommendation only. No mutation.
    "security_agent": frozenset({AGENT_OBSERVE, AGENT_RECOMMEND, ARTIFACT_READ}),
    "performance_agent": frozenset({AGENT_OBSERVE, AGENT_RECOMMEND, MODEL_READ}),
    "monitoring_agent": frozenset({AGENT_OBSERVE, AGENT_RECOMMEND, PLATFORM_READ, AUDIT_READ}),
    "data_agent": frozenset({AGENT_OBSERVE, AGENT_RECOMMEND, MODEL_READ}),
    "quantum_agent": frozenset({AGENT_OBSERVE, AGENT_RECOMMEND, AUDIT_READ}),
    "redteam_agent": frozenset({AGENT_OBSERVE, ARTIFACT_READ}),

    # SAT-SA supervisory roles. Named distinctly from the MLOps roles
    # above (satsa_* prefix) so the two domains coexist without collision.
    # Read-only access to findings/evidence/review history/trust status.
    "satsa_viewer": frozenset(
        {FINDING_VIEW, EVIDENCE_VIEW, REVIEW_READ, TRUST_VERIFY}
    ),
    # Runs analytics/validation and reads everything a viewer can.
    "satsa_analyst": frozenset(
        {
            FINDING_VIEW, EVIDENCE_VIEW, REVIEW_READ,
            ANALYSIS_RUN, VALIDATION_RUN, TRUST_VERIFY, REPORT_EXPORT,
        }
    ),
    # The human supervisor: the only role that may record a review
    # decision — the terminal authority the architecture requires.
    "satsa_supervisor": frozenset(
        {
            FINDING_VIEW, EVIDENCE_VIEW, REVIEW_READ, REVIEW_CREATE,
            DECISION_RECORD, ANALYSIS_RUN, VALIDATION_RUN,
            TRUST_VERIFY, REPORT_EXPORT, CALIBRATION_APPROVE,
        }
    ),
    # Read-heavy oversight role: everything a supervisor can see, plus
    # the platform audit log, but cannot itself record decisions.
    "satsa_auditor": frozenset(
        {
            FINDING_VIEW, EVIDENCE_VIEW, REVIEW_READ,
            TRUST_VERIFY, REPORT_EXPORT, AUDIT_READ,
        }
    ),
    # Full SAT-SA control, including identity/config management via the
    # existing MLOps identity.manage / config.manage permissions.
    "satsa_admin": frozenset({ALL_ACTIONS}),
}

SATSA_ROLE_NAMES = frozenset(
    {"satsa_viewer", "satsa_analyst", "satsa_supervisor", "satsa_auditor", "satsa_admin"}
)

AGENT_ROLE_NAMES = frozenset(
    {
        "security_agent",
        "performance_agent",
        "monitoring_agent",
        "data_agent",
        "quantum_agent",
        "redteam_agent",
    }
)


def has_permission(
    grants: set[str], permission: str, *, roles: dict[str, frozenset[str]] | None = None
) -> bool:
    """Evaluate whether a set of permission strings grants ``permission``.

    Custom role definitions may be supplied (production deployments will add
    organization-specific roles); unknown roles raise.
    """
    role_defs = roles if roles is not None else ROLES
    effective: set[str] = set()
    for grant in grants:
        if grant in role_defs:
            effective |= role_defs[grant]
        else:
            if not _is_valid_permission(grant):
                raise PermissionDeniedError(f"unknown role or permission {grant!r}")
            effective.add(grant)
    if ALL_ACTIONS in effective:
        return True
    if permission in effective:
        return True
    domain = permission.split(".")[0]
    return f"{domain}.{ALL_ACTIONS}" in effective


def require_permission(grants: set[str], permission: str, *, actor: str = "") -> None:
    if not has_permission(grants, permission):
        raise PermissionDeniedError(
            f"actor {actor or '<unknown>'} lacks permission {permission!r}"
        )


def _is_valid_permission(candidate: str) -> bool:
    if candidate == ALL_ACTIONS:
        return True
    if "." not in candidate:
        return False
    domain, action = candidate.split(".", 1)
    return bool(domain) and bool(action) and " " not in candidate

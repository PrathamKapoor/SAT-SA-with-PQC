"""SAT-SA domain error hierarchy.

Deliberately separate from ``qsmlops.core.errors`` (Part L: "keep
domain-specific semantics separate" from the reused MLOps foundation) —
SAT-SA's domain validation is a different concern from platform-level
configuration/storage/crypto errors, even though both packages reuse the
same structured-logging foundation (``qsmlops.core.logging``).
"""
from __future__ import annotations


class SatsaError(Exception):
    """Base class for every SAT-SA domain error."""


class DomainValidationError(SatsaError):
    """A domain record failed validation (missing required field, invalid
    enum value, inconsistent period/relationship).

    ``validate()`` itself never raises — it returns a list of problems and
    the caller decides what to do with them. This error exists for callers
    whose correct response to a non-empty problem list is to reject the
    record outright (e.g. a future ingestion boundary or persistence layer
    that must not admit an invalid record), raising with the problem list
    attached — never silently corrected."""


class UnknownRecordError(SatsaError):
    """A referenced record ID does not resolve within the given scope."""


class ScopeViolationError(SatsaError):
    """A relationship or reference crosses an entity/assessment boundary it
    must not cross (e.g. a Case referencing an Alert from a different
    entity) — see docs/phase1/data-architecture.md's isolation rule:
    "Relations must match entity scope.\""""

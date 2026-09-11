"""Shared helpers for SAT-SA domain records.

Every record in this package follows the same convention (per
docs/phase1/data-architecture.md's canonical model): a stable opaque ``id``,
a ``validate() -> list[str]`` method returning human-readable problems
(empty list means valid — callers decide whether to raise, log, or queue
for operator review; ``validate()`` itself never raises), and ``to_dict()``/
``from_dict()`` for serialization, matching the pattern already established
by ``qsmlops.agents.base.Observation``/``Finding`` and
``qsmlops.security.identity.models.Identity``.

No shared dataclass base is used deliberately: mixing dataclass inheritance
with required-then-optional fields across many unrelated record shapes
produces exactly the fragile field-ordering coupling Rule 5 warns against
("no unnecessary abstraction layers" — Part E2). Each record is a plain,
independent ``@dataclass``; this module only holds the few pure functions
they all call.
"""
from __future__ import annotations

import uuid

CURRENT_SCHEMA_VERSION = 1


def new_id(prefix: str) -> str:
    """A namespaced opaque ID, e.g. ``entity_3f9c...``. The prefix makes IDs
    self-describing in logs/exports without needing a lookup — this is a
    debugging aid, not a security boundary (do not parse it to authorize
    anything, per docs/phase1/data-architecture.md: "All primary IDs are
    opaque strings")."""
    return f"{prefix}_{uuid.uuid4().hex}"


def require(condition: bool, message: str, errors: list[str]) -> None:
    """Append ``message`` to ``errors`` iff ``condition`` is False. A tiny
    helper so every record's validate() reads as a flat list of checks
    rather than a pyramid of nested ifs."""
    if not condition:
        errors.append(message)

"""Human review workflow: an authenticated examiner's confirm /
dismiss / escalate / annotate / request_review action on a
finding, with a full audit trail.

What this module does
---------------------

* Persists each decision in ``satsa_review_decisions`` (append-only
  by convention: a correction creates a new decision referencing
  ``previous_revision_id``).
* Records the *current* finding content_digest alongside the
  decision so the audit trail can show exactly which version of
  the finding the reviewer acted on.
* Exposes a query for a finding's full decision history
  (chronological; corrections included; a single per-finding
  chain).

What this module does NOT do
----------------------------

* It does not invent an enterprise authentication system. The
  ``principal_identity_id`` is whatever the platform's identity
  layer hands in (Phase 2's API-key auth, or whatever the
  operator integrates). The audit row records the id
  faithfully — it does not verify the caller is who they claim.
* It does not edit the original finding. A decision never
  re-classifies a finding's state; it records the reviewer's
  judgement over it. (A future "reviewer's verdict wins" mode
  is a separate, deliberate design choice, not a default.)
* It does not call the trust layer itself; the caller may
  ``verify_run`` separately if a tamper-evident audit is
  required. The decision row carries the finding's content
  digest as captured at the moment of decision — if the
  finding is later tampered with, the digest in the decision
  no longer matches the live digest and the verifier will
  notice.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from qsmlops.crypto.hashing import digest_document
from satsa.domain.evidence import ReviewDecision
from satsa.domain.base import new_id


@dataclass
class ReviewAuditEntry:
    id: str
    finding_id: str
    principal_identity_id: str
    action: str
    reason: str
    occurred_at: float
    previous_revision_id: Optional[str]
    finding_content_digest: str
    created_at: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "principal_identity_id": self.principal_identity_id,
            "action": self.action,
            "reason": self.reason,
            "occurred_at": self.occurred_at,
            "previous_revision_id": self.previous_revision_id,
            "finding_content_digest": self.finding_content_digest,
            "created_at": self.created_at,
        }


class ReviewService:
    """Persist human review decisions and query the audit log."""

    def __init__(self, database) -> None:
        if hasattr(database, "ensure_ready"):
            database.ensure_ready()
            self._db = database.engine
        else:
            self._db = database

    def record(self, *, finding_id: str, principal_identity_id: str,
               action: str, reason: str = "",
               finding_content_digest: str,
               occurred_at: Optional[float] = None,
               previous_revision_id: Optional[str] = None) -> ReviewAuditEntry:
        """Record a single review decision. The caller supplies the
        finding's current content_digest (so the audit row is
        bound to the exact version of the finding being acted on)."""
        occurred = occurred_at if occurred_at is not None else time.time()
        d = ReviewDecision(
            finding_id=finding_id,
            principal_identity_id=principal_identity_id,
            action=action, reason=reason,
            occurred_at=occurred,
            previous_revision_id=previous_revision_id,
        )
        errors = d.validate()
        if errors:
            raise ValueError("invalid review decision: " + "; ".join(errors))
        rid = new_id("reviewdec")
        digest = digest_document(d.to_dict())
        self._db.execute(
            "INSERT INTO satsa_review_decisions (id, finding_id,"
            " principal_identity_id, action, reason, occurred_at,"
            " previous_revision_id, finding_content_digest, content_digest,"
            " created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rid, finding_id, principal_identity_id, action, reason,
             occurred, previous_revision_id,
             finding_content_digest, digest, occurred))
        return ReviewAuditEntry(
            id=rid, finding_id=finding_id,
            principal_identity_id=principal_identity_id, action=action,
            reason=reason, occurred_at=occurred,
            previous_revision_id=previous_revision_id,
            finding_content_digest=finding_content_digest,
            created_at=occurred,
        )

    def history(self, finding_id: str) -> list[ReviewAuditEntry]:
        rows = self._db.query_all(
            "SELECT * FROM satsa_review_decisions"
            " WHERE finding_id=? ORDER BY occurred_at", (finding_id,))
        return [ReviewAuditEntry(
            id=r["id"], finding_id=r["finding_id"],
            principal_identity_id=r["principal_identity_id"],
            action=r["action"], reason=r["reason"],
            occurred_at=r["occurred_at"],
            previous_revision_id=r["previous_revision_id"],
            finding_content_digest=r["finding_content_digest"],
            created_at=r["created_at"],
        ) for r in rows]

    def verify_binding(self, finding_id: str, current_finding_row: dict) -> list[dict]:
        """Check every recorded decision on ``finding_id`` against the
        finding's *current* live content digest.

        This closes a gap this module's own docstring long claimed but
        nothing ever actually checked: "if the finding is later
        tampered with, the digest in the decision no longer matches
        the live digest and the verifier will notice" — there was no
        verifier. Findings are append-only after creation (a run's
        observations/findings are not legitimately mutated once
        persisted), so every decision ever recorded against a finding
        should carry the *same* content digest as the finding's
        current live state; any decision whose stored digest diverges
        signals either the finding was tampered with after that
        decision, or the decision row itself was tampered with.

        Returns one dict per decision:
        ``{"review_id", "action", "occurred_at", "ok", "reason"}``.
        """
        from satsa.analysis.run import RunService
        live_digest = RunService._live_digest_for_finding(current_finding_row)
        out = []
        for entry in self.history(finding_id):
            ok = entry.finding_content_digest == live_digest
            reason = "ok" if ok else (
                "finding_content_digest recorded at decision time no "
                "longer matches the finding's live digest — the finding "
                "changed (or this decision row was tampered with) after "
                f"the decision was made (decision digest "
                f"{entry.finding_content_digest[:16]}…, live "
                f"{live_digest[:16]}…)")
            out.append({
                "review_id": entry.id, "action": entry.action,
                "occurred_at": entry.occurred_at, "ok": ok, "reason": reason,
            })
        return out

    def aggregate_stats(self) -> dict:
        """Aggregate review statistics across the entire database.
        Returns a dict suitable for direct rendering in the UI.
        Does NOT call these "model accuracy" — they are review
        semantics, not classifier semantics."""
        rows = self._db.query_all(
            "SELECT action, COUNT(*) AS c FROM satsa_review_decisions"
            " GROUP BY action")
        by_action = {r["action"]: r["c"] for r in rows}
        total = sum(by_action.values())
        by_actor = self._db.query_all(
            "SELECT principal_identity_id, COUNT(*) AS c"
            " FROM satsa_review_decisions"
            " GROUP BY principal_identity_id")
        distinct_findings = self._db.query_one(
            "SELECT COUNT(DISTINCT finding_id) AS c"
            " FROM satsa_review_decisions")
        return {
            "total": total,
            "by_action": by_action,
            "by_actor": {r["principal_identity_id"]: r["c"] for r in by_actor},
            "distinct_findings_reviewed": distinct_findings["c"],
        }

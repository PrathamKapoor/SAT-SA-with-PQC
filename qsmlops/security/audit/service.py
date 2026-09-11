"""Audit service: structured AuditEvent emission + tamper-evident storage.

Storage model: the evidence ledger is the authoritative, immutable store (a
hash chain — any retroactive edit breaks verification). The platform database
keeps an *indexed mirror copy* of audit events so the API can query cheaply;
mirrors are never trusted over the ledger and are rebuilt from it when they
diverge.

Every recorded event also gets its ledger entry hash (`ledger_entry_hash`)
so an event read back through the mirror can be proven to exist on-chain.
"""
from __future__ import annotations

from qsmlops.core.logging import get_logger
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.events import AuditEvent

log = get_logger(__name__)

AUDIT_ACTION_PREFIX = "audit"


class AuditService:
    """Writes AuditEvents to the ledger and mirrors them to the DB index."""

    def __init__(self, ledger: EvidenceLedger, database=None) -> None:
        self._ledger = ledger
        self._database = database  # optional mirror; ledger is authoritative

    # -------------------- write path --------------------
    def record(self, event: AuditEvent) -> AuditEvent:
        """Append the event to the ledger and mirror it (if a DB is present)."""
        doc = event.to_dict()
        doc["audit_type"] = AUDIT_ACTION_PREFIX
        entry = self._ledger.append(doc)
        self._mirror(event, entry["entry_hash"])
        return event

    def _mirror(self, event: AuditEvent, entry_hash: str) -> None:
        if self._database is None:
            return
        try:
            from qsmlops.database.repositories import AuditEventRepository

            AuditEventRepository(self._database).insert_mirror(event, entry_hash)
        except Exception as exc:  # pragma: no cover - mirror is best-effort
            log.warning("audit mirror write failed: %s", exc)

    # -------------------- query path --------------------
    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        """Return audit events from the ledger, newest first."""
        matches: list[AuditEvent] = []
        for entry in self._ledger.iter_entries():
            record = entry.get("record", {})
            if record.get("audit_type") != AUDIT_ACTION_PREFIX:
                continue
            event = AuditEvent.from_dict(record)
            if actor and event.actor != actor:
                continue
            if action and event.action != action:
                continue
            if resource and event.resource != resource:
                continue
            if since is not None and event.timestamp < since:
                continue
            matches.append(event)
        matches.sort(key=lambda e: e.timestamp, reverse=True)
        if limit is not None:
            matches = matches[:limit]
        return matches

    def verify(self) -> tuple[bool, str]:
        return self._ledger.verify_chain()

    def head(self) -> str:
        return self._ledger.head()

    def recent(self, limit: int = 20) -> list[AuditEvent]:
        return self.query(limit=limit)

    def counts_by_action(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.query():
            counts[event.action] = counts.get(event.action, 0) + 1
        return counts

    def details(self) -> dict:
        ok, message = self.verify()
        return {
            "ledger_chain_ok": ok,
            "ledger_message": message,
            "ledger_head": self._ledger.head(),
            "event_count": len(self.query()),
            "by_action": self.counts_by_action(),
        }

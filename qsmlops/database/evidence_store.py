"""EvidenceStore: durable persistence for agent Observations, Findings,
supervisor DecisionReports and the provenance edges linking them.

Phase 2 (SAT-SA foundation hardening) closes a gap found in Phase 1's audit
and re-confirmed here: ``observations``, ``findings``, ``supervisor_decisions``
and ``provenance_edges`` were migrated tables with no repository/insert path
anywhere in the codebase. This module is that path.

Scope, deliberately (Rule 3 — this is not the analytics phase): this stores
whatever Observation/DecisionReport objects the *existing* nine-agent MLOps
pipeline already produces, unchanged. It does not add new analytical content,
does not compute new risk models, and is not wired into every pipeline call
site automatically — a caller (pipeline code, a future SAT-SA analytics
worker, a test) opts in by calling ``persist_observation``/``persist_decision``
explicitly. See docs/phase2/evidence-persistence.md for what "integrity"
means here and what it deliberately does not yet claim (content-digest
checkable rows, not signed/ledger-committed provenance — that remains later
work per docs/phase1/quantum-trust-audit.md's proposed lifecycle).
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from qsmlops.crypto.hashing import digest_document
from qsmlops.database.repositories import (
    FindingRepository,
    ObservationRepository,
    ProvenanceEdgeRepository,
    SupervisorDecisionRepository,
)

PREDICATE_DERIVED_FROM = "derived_from"
PREDICATE_BASED_ON = "based_on"


class EvidenceStore:
    """Durable write/read path for the Evidence -> Observation -> Finding ->
    Decision provenance chain. One instance per DatabaseService/engine,
    following the same construction pattern as AuditService/IdentityService."""

    def __init__(self, database) -> None:
        if hasattr(database, "ensure_ready"):
            database.ensure_ready()
            engine = database.engine
        else:
            engine = database
        self._engine = engine
        self._observations = ObservationRepository(engine)
        self._findings = FindingRepository(engine)
        self._decisions = SupervisorDecisionRepository(engine)
        self._provenance = ProvenanceEdgeRepository(engine)

    # -------------------- write path --------------------
    def persist_observation(self, observation) -> str:
        """Persist an Observation and every Finding it contains, plus a
        provenance edge from each finding back to its observation. Returns
        the observation_id. Digests are computed over each object's own
        to_dict() so a later read can detect an in-place row edit."""
        obs_digest = digest_document(observation.to_dict())
        with self._engine.transaction():
            self._observations.insert(observation, content_digest=obs_digest)
            for finding in observation.findings:
                finding_digest = digest_document(finding.to_dict())
                self._findings.insert(
                    finding,
                    observation_id=observation.observation_id,
                    agent=observation.agent,
                    subject_id=observation.subject_id,
                    content_digest=finding_digest,
                )
                self._provenance.insert(
                    "finding",
                    finding.finding_id,
                    PREDICATE_DERIVED_FROM,
                    "observation",
                    observation.observation_id,
                    content_digest=digest_document(
                        {"subject": finding.finding_id, "object": observation.observation_id,
                         "predicate": PREDICATE_DERIVED_FROM}
                    ),
                )
        return observation.observation_id

    def persist_decision(
        self,
        report,
        *,
        model_name: str = "",
        packet_id: str = "",
        action_success: Optional[bool] = None,
        verified: Optional[bool] = None,
        detail: str = "",
        based_on_observation_ids: Optional[list[str]] = None,
    ) -> str:
        """Persist a supervisor DecisionReport and link it (via provenance
        edges) to the observations it was based on. Returns the generated
        decision_id — DecisionReport itself carries no stable ID, so one is
        minted at persistence time, same pattern as Observation/Finding."""
        decision_id = uuid.uuid4().hex
        digest = digest_document(report.to_dict())
        with self._engine.transaction():
            self._decisions.insert(
                decision_id,
                report,
                model_name=model_name,
                packet_id=packet_id,
                action_success=action_success,
                verified=verified,
                detail=detail,
                content_digest=digest,
            )
            for obs_id in based_on_observation_ids or []:
                self._provenance.insert(
                    "decision",
                    decision_id,
                    PREDICATE_BASED_ON,
                    "observation",
                    obs_id,
                    content_digest=digest_document(
                        {"subject": decision_id, "object": obs_id, "predicate": PREDICATE_BASED_ON}
                    ),
                )
        return decision_id

    # -------------------- read / verification path --------------------
    def get_observation(self, observation_id: str) -> dict | None:
        return self._observations.get(observation_id)

    def get_findings_for_observation(self, observation_id: str) -> list[dict]:
        return self._findings.list_for_observation(observation_id)

    def get_decision(self, decision_id: str) -> dict | None:
        return self._decisions.get(decision_id)

    def get_provenance_for(self, subject_type: str, subject_id: str) -> list[dict]:
        return self._provenance.list_for_subject(subject_type, subject_id)

    def verify_observation_integrity(self, observation_id: str) -> tuple[bool, str]:
        """Recompute the stored observation's digest from its own fields and
        compare against content_digest. This detects a row edited outside
        this module; it does NOT prove the row was never edited by someone
        with direct database access before this check runs, and it is not a
        cryptographic signature — see docs/phase2/evidence-persistence.md."""
        row = self._observations.get(observation_id)
        if row is None:
            return False, f"observation {observation_id} not found"
        recomputed = digest_document(
            {
                "observation_id": row["observation_id"],
                "agent": row["agent"],
                "subject_id": row["subject_id"],
                "recommendation": row["recommendation"],
                "created_at": row["created_at"],
                "notes": row["notes"],
                "max_severity": row["max_severity"],
                "mean_confidence": round(row["mean_confidence"], 4),
                "findings": [
                    {
                        "finding_id": f["finding_id"],
                        "name": f["name"],
                        "passed": bool(f["passed"]),
                        "severity": f["severity"],
                        "risk": f["risk"],
                        "detail": f["detail"],
                        "observation": f["observation_text"],
                        "confidence": round(f["confidence"], 4),
                        "recommendation": f["recommendation"],
                        "evidence": json.loads(f["evidence_json"]),
                    }
                    for f in self._findings.list_for_observation(observation_id)
                ],
            }
        )
        if recomputed != row["content_digest"]:
            return False, "content_digest mismatch: row was modified after persistence"
        return True, "content_digest matches recomputed observation body"

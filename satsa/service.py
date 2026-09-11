"""SatsaService: the application facade for SAT-SA — entity/assessment
management plus ingestion. One place API routes, the CLI and the demo all
use, constructed over a DatabaseService (or bare engine in tests).

Governance this phase: entities and assessments are operator-managed
records; submission ingestion is the only bulk write.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from qsmlops.core.logging import get_logger
from satsa.domain.entities import Assessment, Entity
from satsa.errors import DomainValidationError
from satsa.store.dataset import CanonicalDataset, load_dataset
from satsa.store.repositories import AssessmentStore, EntityStore, SubmissionStore

log = get_logger(__name__)


class SatsaService:
    def __init__(self, database) -> None:
        # accept either a qsmlops DatabaseService (has .ensure_ready/.engine)
        # or a bare engine (tests)
        if hasattr(database, "ensure_ready"):
            database.ensure_ready()
            self._db = database.engine
        else:
            self._db = database
        self.entities = EntityStore(self._db)
        self.assessments = AssessmentStore(self._db)
        self.submissions = SubmissionStore(self._db)

    # -------------------- entities --------------------
    def register_entity(self, display_name: str, *, sector: str = "",
                        environment_class: str = "", access_scope: str = "",
                        cohort_attributes: Optional[dict] = None) -> Entity:
        display_name = (display_name or "").strip()
        entity = Entity(display_name=display_name, sector=sector,
                        environment_class=environment_class, access_scope=access_scope,
                        cohort_attributes=dict(cohort_attributes or {}))
        errors = entity.validate()
        if errors:
            raise DomainValidationError("; ".join(errors))
        existing = self.entities.get_by_name(display_name)
        if existing is not None:
            # idempotent by name: re-registering the same entity returns it
            return Entity.from_dict({
                "id": existing["id"], "display_name": existing["display_name"],
                "sector": existing["sector"],
                "environment_class": existing["environment_class"],
                "cohort_attributes": _json(existing["cohort_attributes_json"], {}),
                "access_scope": existing["access_scope"],
                "schema_version": existing["schema_version"]})
        self.entities.insert(entity, created_at=time.time())
        log.info("registered entity %r (%s)", display_name, entity.id,
                 extra={"event": "satsa.entity.registered", "entity_id": entity.id})
        return entity

    def get_entity(self, entity_id: str) -> Optional[dict]:
        return self.entities.get(entity_id)

    def list_entities(self) -> list:
        return self.entities.list()

    # -------------------- assessments --------------------
    def open_assessment(self, entity_id: str, period_start: float, period_end: float, *,
                        policy_version: str = "1.0",
                        submission_cutoff: Optional[float] = None) -> Assessment:
        if self.entities.get(entity_id) is None:
            raise DomainValidationError(f"entity {entity_id!r} not found")
        assessment = Assessment(
            entity_id=entity_id, period_start=float(period_start),
            period_end=float(period_end), policy_version=policy_version,
            submission_cutoff=submission_cutoff, status="open")
        errors = assessment.validate()
        if errors:
            raise DomainValidationError("; ".join(errors))
        self.assessments.insert(assessment, created_at=time.time())
        log.info("opened assessment %s for entity %s", assessment.id, entity_id,
                 extra={"event": "satsa.assessment.opened",
                        "assessment_id": assessment.id, "entity_id": entity_id})
        return assessment

    def close_assessment(self, assessment_id: str) -> None:
        if self.assessments.get(assessment_id) is None:
            raise DomainValidationError(f"assessment {assessment_id!r} not found")
        self.assessments.set_status(assessment_id, "closed")

    def get_assessment(self, assessment_id: str) -> Optional[dict]:
        return self.assessments.get(assessment_id)

    def list_assessments(self, entity_id: str) -> list:
        return self.assessments.list_for_entity(entity_id)

    # -------------------- submissions --------------------
    def submit(self, assessment_id: str, source, *,
               source_system: str = "",
               received_at: Optional[float] = None):
        """Ingest a submission. ``source`` is a directory path or a
        {category: path} mapping. Returns IngestionResult."""
        from satsa.ingest.service import IngestionService

        ingester = IngestionService(self._db)
        if isinstance(source, (str, Path)):
            return ingester.submit_directory(
                assessment_id, source, source_system=source_system,
                received_at=received_at)
        if isinstance(source, dict):
            return ingester.submit_files(
                assessment_id, source, source_system=source_system,
                received_at=received_at)
        raise DomainValidationError(
            f"unsupported submission source type {type(source).__name__!r}")

    # -------------------- frozen snapshot --------------------
    def load_scope(self, entity_id: str, assessment_id: str) -> CanonicalDataset:
        return load_dataset(self._db, entity_id, assessment_id)

    # -------------------- analysis run --------------------
    def run_analysis(self, entity_id: str, assessment_id: str, **kwargs):
        """Run the registered analytical workers over the scope and
        persist the resulting AnalysisRun / Observations / Findings /
        Jobs in a single transaction. See
        ``satsa.analysis.run.RunService.run`` for the kwargs accepted."""
        from satsa.analysis.run import RunService
        return RunService(self._db).run(entity_id, assessment_id, **kwargs)

    def compute_risk(self, entity_id: str, *, run_id: str | None = None):
        """Aggregate the latest (or specified) run's findings into a
        decomposable EntityRiskProfile. See
        ``satsa.analysis.risk.compute_entity_risk``."""
        from satsa.analysis.risk import compute_entity_risk
        return compute_entity_risk(self._db, entity_id, run_id=run_id)

    def prioritize_entities(self):
        """Rank every entity with a recent run for human review
        attention. Returns a list of EntityPriority, highest first."""
        from satsa.analysis.prioritize import prioritize_entities
        return prioritize_entities(self._db)

    def prioritize_findings(self, run_id: str):
        """Rank the signal findings of a single run, highest first,
        with evidence-backed per-finding rationale."""
        from satsa.analysis.prioritize import prioritize_findings
        return prioritize_findings(self._db, run_id)

    # -------------------- trust / provenance --------------------
    def verify_run(self, run_id: str, trust_key_dir):
        """Verify the run + every persisted finding against its PQC
        trust receipt. Returns a per-subject status dict
        (see ``satsa.analysis.run.RunService.verify_run``)."""
        from satsa.analysis.run import RunService
        return RunService(self._db).verify_run(run_id, trust_key_dir)

    # -------------------- human review --------------------
    def record_review(self, *, trust_key_dir=None, **kwargs):
        """Record a human review decision on a finding. See
        ``satsa.analysis.review.ReviewService.record`` for the
        accepted kwargs.

        When ``trust_key_dir`` is given, the decision is also
        mirrored into the independent, hash-chained decision ledger
        (``satsa.analysis.review.build_review_decision_ledger``) so
        later deletion/reordering is detectable via
        ``verify_review_ledger_integrity`` — see that module's
        docstring. Omitting ``trust_key_dir`` (e.g. an in-memory-DB
        smoke test with no key directory) records the decision
        exactly as before, without the ledger mirror.
        """
        from satsa.analysis.review import ReviewService, build_review_decision_ledger
        ledger = build_review_decision_ledger(trust_key_dir) if trust_key_dir else None
        return ReviewService(self._db, decision_ledger=ledger).record(**kwargs)

    def review_history(self, finding_id: str):
        """The full chronological decision history for a finding."""
        from satsa.analysis.review import ReviewService
        return ReviewService(self._db).history(finding_id)

    def verify_review_binding(self, finding_id: str) -> list[dict]:
        """Check every recorded review decision on a finding against
        the finding's current live content digest — see
        ``ReviewService.verify_binding`` for what this actually
        proves (and what it would catch)."""
        from satsa.analysis.review import ReviewService
        finding_row = self._db.query_one(
            "SELECT * FROM satsa_findings WHERE id=?", (finding_id,))
        if finding_row is None:
            return []
        return ReviewService(self._db).verify_binding(finding_id, dict(finding_row))

    def verify_review_ledger_integrity(self, trust_key_dir) -> dict:
        """Cross-check the entire ``satsa_review_decisions`` table
        against the independent decision ledger — detects deletion or
        out-of-band insertion, not just in-place content tampering
        (which ``verify_review_binding`` already covers). See
        ``ReviewService.verify_ledger_integrity``."""
        from satsa.analysis.review import ReviewService, build_review_decision_ledger
        ledger = build_review_decision_ledger(trust_key_dir)
        return ReviewService(self._db, decision_ledger=ledger).verify_ledger_integrity()


def _json(text, default):
    import json
    try:
        return json.loads(text) if text else default
    except (TypeError, json.JSONDecodeError):
        return default

"""A cutover is rejected if ownership or evidence history changes."""
from __future__ import annotations

import shutil

import pytest

from qsmlops.database.engine import SQLiteDatabaseEngine, create_engine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.evidence.ledger import EvidenceLedger
from satsa.migration_validation import MigrationValidationError, validate_migration
from test_postgres_engine import postgres_dsn


def test_sqlite_to_postgres_requires_mapping_and_preserves_history(tmp_path, postgres_dsn):
    source = SQLiteDatabaseEngine(tmp_path / "source.db")
    target = create_engine(postgres_dsn)
    try:
        MigrationRunner(source).migrate()
        MigrationRunner(target).migrate()
        target.execute(
            "INSERT INTO satsa_organizations (id, name, created_at) VALUES (?,?,?)",
            ("org-a", "CSE A", 1.0),
        )
        rows = [
            ("satsa_entities", "id,display_name,content_digest,created_at",
             ("entity-a", "Entity A", "digest-entity", 1.0)),
            ("satsa_assessments", "id,entity_id,period_start,period_end,content_digest,created_at",
             ("assessment-a", "entity-a", 1.0, 2.0, "digest-assessment", 1.0)),
            ("satsa_submissions", "id,assessment_id,entity_id,content_digest,created_at",
             ("submission-a", "assessment-a", "entity-a", "digest-submission", 1.0)),
            ("satsa_runs", "id,entity_id,assessment_id,snapshot_digest,content_digest,created_at",
             ("run-a", "entity-a", "assessment-a", "snapshot", "digest-run", 1.0)),
            ("satsa_observations", "id,run_id,worker_name,entity_id,assessment_id,content_digest,created_at",
             ("observation-a", "run-a", "worker", "entity-a", "assessment-a", "digest-observation", 1.0)),
            ("satsa_findings", "id,observation_id,rule_or_category,state,content_digest,created_at",
             ("finding-a", "observation-a", "rule", "signal", "digest-finding", 1.0)),
            ("satsa_review_decisions", "id,finding_id,principal_identity_id,action,occurred_at,content_digest,created_at",
             ("review-a", "finding-a", "examiner", "confirm", 1.0, "digest-review", 1.0)),
            ("satsa_trust_receipts", "id,subject_type,subject_id,algorithm_id,public_key,content_digest,signature,created_at",
             (1, "run", "run-a", "ML-DSA-65", b"public", "digest-run", b"signature", 1.0)),
        ]
        for table, columns, values in rows:
            placeholders = ",".join("?" for _ in values)
            source.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            if table in {"satsa_entities", "satsa_assessments", "satsa_submissions", "satsa_runs"}:
                columns += ",organization_id"
                values += ("org-a",)
                placeholders += ",?"
            target.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)

        source_ledger = tmp_path / "source_ledger.jsonl"
        target_ledger = tmp_path / "target_ledger.jsonl"
        EvidenceLedger(source_ledger).append({"type": "review_decision", "id": "review-a"})
        shutil.copyfile(source_ledger, target_ledger)
        with pytest.raises(MigrationValidationError, match="explicit owner"):
            validate_migration(source, target, {})
        counts = validate_migration(
            source, target, {"entity-a": "org-a"},
            source_ledgers=(source_ledger,), target_ledgers=(target_ledger,),
        )
        assert counts["satsa_review_decisions"] == 1
        assert counts["satsa_trust_receipts"] == 1

        target.execute("UPDATE satsa_review_decisions SET action='reject' WHERE id='review-a'")
        with pytest.raises(MigrationValidationError, match="review"):
            validate_migration(source, target, {"entity-a": "org-a"})
        target.execute("UPDATE satsa_review_decisions SET action='confirm' WHERE id='review-a'")
        target.execute(
            "INSERT INTO satsa_entities (id, organization_id, display_name, created_at)"
            " VALUES (?,?,?,?)", ("extra-entity", "org-a", "Extra", 1.0),
        )
        with pytest.raises(MigrationValidationError, match="row count"):
            validate_migration(source, target, {"entity-a": "org-a"})
    finally:
        source.close()
        target.close()

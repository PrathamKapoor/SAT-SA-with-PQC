"""PostgreSQL parity for the existing SAT-SA schema history."""
from __future__ import annotations

import pytest

from qsmlops.core.errors import StorageError
from qsmlops.database.engine import create_engine
from qsmlops.database import migrations
from qsmlops.database.migrations import MIGRATIONS, Migration, MigrationRunner
from test_postgres_engine import postgres_dsn


def test_postgres_migrates_every_existing_version_and_is_idempotent(postgres_dsn):
    engine = create_engine(postgres_dsn)
    try:
        runner = MigrationRunner(engine)
        first = runner.migrate()
        assert len(first) == len(MIGRATIONS)
        assert runner.migrate() == []
        assert runner.applied_versions() == [migration.version for migration in MIGRATIONS]
        expected = {
            "identities", "identity_credentials", "audit_events",
            "satsa_entities", "satsa_assessments", "satsa_submissions",
            "satsa_source_records", "satsa_runs", "satsa_observations",
            "satsa_findings", "satsa_jobs", "satsa_trust_receipts",
            "satsa_review_decisions",
        }
        actual = {row["tablename"] for row in engine.query_all(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=current_schema()"
        )}
        assert expected <= actual
        column = engine.query_one(
            "SELECT data_type FROM information_schema.columns"
            " WHERE table_schema=current_schema() AND table_name='satsa_runs'"
            " AND column_name='created_at'"
        )
        assert column == {"data_type": "double precision"}
    finally:
        engine.close()


def test_postgres_failed_migration_does_not_mark_version(postgres_dsn, monkeypatch):
    engine = create_engine(postgres_dsn)
    try:
        MigrationRunner(engine).migrate()
        bad = Migration(max(m.version for m in MIGRATIONS) + 1, "deliberately_invalid", (
            "CREATE TABLE phase1_rollback_probe (id INTEGER PRIMARY KEY)",
            "INVALID SQL",
        ))
        monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS + (bad,))
        with pytest.raises(StorageError):
            MigrationRunner(engine).migrate()
        assert MigrationRunner(engine).applied_versions() == [m.version for m in MIGRATIONS]
        assert engine.query_one(
            "SELECT to_regclass('phase1_rollback_probe') AS name"
        ) == {"name": None}
    finally:
        engine.close()

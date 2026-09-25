"""Phase 1 tenant schema is available in both database modes."""
from __future__ import annotations

import pytest

from qsmlops.database.engine import SQLiteDatabaseEngine, create_engine
from qsmlops.database.migrations import MigrationRunner
from test_postgres_engine import postgres_dsn


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    if request.param == "sqlite":
        db = SQLiteDatabaseEngine(tmp_path / "tenancy.db")
    else:
        db = create_engine(request.getfixturevalue("postgres_dsn"))
    MigrationRunner(db).migrate()
    try:
        yield db
    finally:
        db.close()


def test_tenant_foundation_tables_and_ownership_column(engine):
    for table in (
        "satsa_organizations", "satsa_users", "satsa_memberships",
        "satsa_sessions", "satsa_submission_versions", "satsa_artifacts",
    ):
        assert engine.query_one(f"SELECT COUNT(*) AS count FROM {table}") == {"count": 0}
    assert engine.query_one("SELECT organization_id FROM satsa_entities LIMIT 1") is None

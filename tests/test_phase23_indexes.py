"""Phase 23: tenant-scoped reads use an index instead of scanning every tenant."""

from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.database.postgres_migrations import postgres_statement


def _plan(db, sql, params):
    return " ".join(str(r["detail"]) for r in db.query_all("EXPLAIN QUERY PLAN " + sql, params))


def test_audit_trail_is_read_through_the_organization_index(tmp_path):
    db = SQLiteDatabaseEngine(tmp_path / "plan.db")
    try:
        MigrationRunner(db).migrate()
        # The organization filter of satsa.api.repository.ApiRepository.audit_events.
        plan = _plan(
            db,
            "SELECT event_id FROM audit_events a WHERE json_extract(metadata,'$.organization_id')=?"
            " ORDER BY timestamp DESC LIMIT 50",
            ("org_x",),
        )
        assert "idx_audit_org_time" in plan
        plan = _plan(
            db,
            "SELECT * FROM satsa_ml_drift_reports WHERE organization_id=? AND model_id=?"
            " ORDER BY created_at DESC LIMIT 3",
            ("org_x", "m"),
        )
        assert "idx_satsa_ml_drift_reports_org" in plan
        plan = _plan(
            db,
            "SELECT * FROM satsa_ml_training_runs WHERE organization_id=? ORDER BY started_at DESC",
            ("org_x",),
        )
        assert "idx_satsa_ml_training_runs_org" in plan
    finally:
        db.close()


def test_postgres_index_uses_the_audit_query_expression():
    statement = postgres_statement(
        "CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_events"
        " (json_extract(metadata,'$.organization_id'), timestamp)"
    )
    # The same expression satsa.api.repository uses on PostgreSQL.
    assert "(metadata::jsonb->>'organization_id')" in statement
    assert "json_extract" not in statement

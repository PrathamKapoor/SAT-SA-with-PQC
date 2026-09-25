"""Read-only checks required before an offline SAT-SA data cutover.

An import must supply an explicit entity-to-organization mapping. This
validator never assigns ownership or repairs rows. It compares persisted
relationships, canonical digests, review state, trust receipts, and optional
hash-chained ledger files before a hosted database may be used.
"""
from __future__ import annotations

from pathlib import Path

from qsmlops.evidence.ledger import EvidenceLedger


TABLE_KEYS = {
    "satsa_entities": "id",
    "satsa_assessments": "id",
    "satsa_submissions": "id",
    "satsa_source_records": "id",
    "satsa_alerts": "id",
    "satsa_cases": "id",
    "satsa_investigation_steps": "id",
    "satsa_escalations": "id",
    "satsa_dispositions": "id",
    "satsa_assets": "id",
    "satsa_runs": "id",
    "satsa_observations": "id",
    "satsa_findings": "id",
    "satsa_jobs": "id",
    "satsa_review_decisions": "id",
    "satsa_trust_receipts": "id",
    "satsa_submission_versions": "id",
    "satsa_artifacts": "id",
}
DIRECT_OWNER_TABLES = (
    "satsa_entities", "satsa_assessments", "satsa_submissions", "satsa_runs",
)


def _owned_ids(target, table: str, organization_id: str) -> set:
    if table in DIRECT_OWNER_TABLES or table in {"satsa_submission_versions", "satsa_artifacts"}:
        sql = f"SELECT id FROM {table} WHERE organization_id=?"
    elif table in {"satsa_source_records", "satsa_alerts", "satsa_cases",
                   "satsa_investigation_steps", "satsa_escalations",
                   "satsa_dispositions", "satsa_assets"}:
        sql = (f"SELECT t.id FROM {table} t JOIN satsa_submissions s"
               " ON s.id=t.submission_id WHERE s.organization_id=?")
    elif table in {"satsa_observations", "satsa_jobs"}:
        sql = (f"SELECT t.id FROM {table} t JOIN satsa_runs r"
               " ON r.id=t.run_id WHERE r.organization_id=?")
    elif table == "satsa_findings":
        sql = ("SELECT f.id FROM satsa_findings f"
               " JOIN satsa_observations o ON o.id=f.observation_id"
               " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=?")
    elif table == "satsa_review_decisions":
        sql = ("SELECT d.id FROM satsa_review_decisions d"
               " JOIN satsa_findings f ON f.id=d.finding_id"
               " JOIN satsa_observations o ON o.id=f.observation_id"
               " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=?")
    elif table == "satsa_trust_receipts":
        sql = ("SELECT t.id FROM satsa_trust_receipts t"
               " LEFT JOIN satsa_runs r ON t.subject_type='run' AND r.id=t.subject_id"
               " LEFT JOIN satsa_findings f ON t.subject_type='finding' AND f.id=t.subject_id"
               " LEFT JOIN satsa_observations o ON o.id=f.observation_id"
               " LEFT JOIN satsa_runs fr ON fr.id=o.run_id"
               " WHERE r.organization_id=? OR fr.organization_id=?")
        return {row["id"] for row in target.query_all(sql, (organization_id, organization_id))}
    else:
        raise MigrationValidationError(f"no owner path for {table}")
    return {row["id"] for row in target.query_all(sql, (organization_id,))}


class MigrationValidationError(ValueError):
    pass


def _normalize(row: dict) -> dict:
    return {key: bytes(value) if isinstance(value, memoryview) else value
            for key, value in row.items() if key != "organization_id"}


def validate_migration(source, target, ownership: dict[str, str], *,
                       source_ledgers: tuple[Path, ...] = (),
                       target_ledgers: tuple[Path, ...] = ()) -> dict[str, int]:
    """Raise on any mismatch; return source row counts only after all checks.

    The source is a complete offline SAT-SA store. The target may include
    unrelated organizations. Rows with source IDs must match exactly, and
    direct owner rows must have the organization from ``ownership``.
    """
    source_entities = source.query_all("SELECT id FROM satsa_entities")
    entity_ids = {row["id"] for row in source_entities}
    if set(ownership) != entity_ids or any(not org for org in ownership.values()):
        raise MigrationValidationError("every source entity needs exactly one explicit owner")
    for org_id in set(ownership.values()):
        if target.query_one("SELECT id FROM satsa_organizations WHERE id=?", (org_id,)) is None:
            raise MigrationValidationError(f"target organization {org_id} is missing")
    if len(source_ledgers) != len(target_ledgers):
        raise MigrationValidationError("source and target ledger lists differ")

    expected_owner: dict[str, dict[str, str]] = {}
    for table in DIRECT_OWNER_TABLES:
        if table == "satsa_entities":
            expected_owner[table] = dict(ownership)
        else:
            expected_owner[table] = {
                row["id"]: ownership[row["entity_id"]]
                for row in source.query_all(f"SELECT id, entity_id FROM {table}")
            }

    counts: dict[str, int] = {}
    for table, key in TABLE_KEYS.items():
        source_rows = {row[key]: _normalize(row) for row in source.query_all(f"SELECT * FROM {table}")}
        counts[table] = len(source_rows)
        scoped_target_ids = set().union(*(
            _owned_ids(target, table, org_id) for org_id in set(ownership.values())
        )) if ownership else set()
        if scoped_target_ids != set(source_rows):
            raise MigrationValidationError(f"{table} row count or ownership differs")
        if not source_rows:
            continue
        # Select only source IDs: unrelated hosted tenant rows are allowed.
        target_rows = {}
        for row_id in source_rows:
            row = target.query_one(f"SELECT * FROM {table} WHERE {key}=?", (row_id,))
            if row is None:
                raise MigrationValidationError(f"{table} missing source row {row_id}")
            target_rows[row_id] = row
        for row_id, source_row in source_rows.items():
            target_row = target_rows[row_id]
            if source_row != _normalize(target_row):
                raise MigrationValidationError(f"{table} row {row_id} differs")
            if table in expected_owner and target_row["organization_id"] != expected_owner[table][row_id]:
                raise MigrationValidationError(f"{table} row {row_id} has wrong organization")

    for source_path, target_path in zip(source_ledgers, target_ledgers):
        if not source_path.exists() or not target_path.exists():
            raise MigrationValidationError("ledger file missing")
        for path in (source_path, target_path):
            valid, detail = EvidenceLedger(path).verify_chain()
            if not valid:
                raise MigrationValidationError(f"ledger chain invalid: {detail}")
        if source_path.read_bytes() != target_path.read_bytes():
            raise MigrationValidationError("ledger history differs")
    return counts

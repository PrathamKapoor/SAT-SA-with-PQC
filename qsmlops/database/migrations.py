"""Migration framework: ordered, idempotent schema migrations.

Migrations are plain versioned statement bundles tracked in ``schema_migrations``.
They run in version order; each applies at most once. The registry DB used by
the model registry keeps its own bootstrap schema (created by ModelRegistry),
so platform database migrations only manage the *platform* store.

The production database requirements (encrypted at rest, quantum-safe
transport, immutable audit) will be met by swapping the engine/dialect —
migration versioning is dialect-neutral SQL applied through the engine.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from qsmlops.database.engine import DatabaseEngine

MIGRATION_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "create_core_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS identities (
                identity_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                permissions TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                hash TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(kind, name)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_identities_kind ON identities (kind)",
            "CREATE INDEX IF NOT EXISTS idx_identities_status ON identities (status)",
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                timestamp REAL NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                result TEXT NOT NULL,
                evidence_reference TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                ledger_entry_hash TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events (actor)",
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events (action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_events (resource)",
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events (timestamp)",
            """
            CREATE TABLE IF NOT EXISTS object_registry (
                object_id TEXT PRIMARY KEY,
                object_type TEXT NOT NULL,
                owner TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                hash TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_objects_type ON object_registry (object_type)",
        ),
    ),
    Migration(
        2,
        "ml_lifecycle_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                owner TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                version_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
                version INTEGER NOT NULL,
                digest TEXT NOT NULL,
                schema_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'committed',
                security_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                provenance_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                UNIQUE(dataset_id, version)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_dsv_dataset ON dataset_versions (dataset_id, version)",
            "CREATE INDEX IF NOT EXISTS idx_dsv_digest ON dataset_versions (digest)",
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(version_id),
                config_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'created',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                completed_at REAL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_exp_dataset ON experiments (dataset_version_id)",
            """
            CREATE TABLE IF NOT EXISTS training_runs (
                run_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(version_id),
                model_name TEXT NOT NULL,
                framework TEXT NOT NULL DEFAULT '',
                hyperparameters_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                environment_json TEXT NOT NULL DEFAULT '{}',
                artifact_digest TEXT NOT NULL DEFAULT '',
                model_version_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'started',
                error TEXT NOT NULL DEFAULT '',
                started_at REAL NOT NULL,
                completed_at REAL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_run_experiment ON training_runs (experiment_id)",
            "CREATE INDEX IF NOT EXISTS idx_run_model ON training_runs (model_name)",
            """
            CREATE TABLE IF NOT EXISTS model_lineage (
                version_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                experiment_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                dataset_version_id TEXT NOT NULL DEFAULT '',
                artifact_digest TEXT NOT NULL DEFAULT '',
                passport_digest TEXT NOT NULL DEFAULT '',
                bom_digest TEXT NOT NULL DEFAULT '',
                registered_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_lineage_dataset ON model_lineage (dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_lineage_artifact ON model_lineage (artifact_digest)",
            """
            CREATE TABLE IF NOT EXISTS deployment_events (
                event_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT NOT NULL DEFAULT '',
                version_id TEXT NOT NULL,
                model_name TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT '',
                packet_id TEXT NOT NULL DEFAULT '',
                previous_version_id TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT 'SUCCESS',
                reason TEXT NOT NULL DEFAULT '',
                at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_depl_model ON deployment_events (model_name, at)",
            "CREATE INDEX IF NOT EXISTS idx_depl_version ON deployment_events (version_id)",
            """
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                agent TEXT NOT NULL,
                subject_id TEXT NOT NULL DEFAULT '',
                recommendation TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                max_severity TEXT NOT NULL DEFAULT 'LOW',
                mean_confidence REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_obs_subject ON observations (subject_id, created_at)",
            """
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                subject_id TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                severity TEXT NOT NULL,
                risk TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                observation_text TEXT NOT NULL DEFAULT '',
                evidence_json TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.8,
                recommendation TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_findings_subject ON findings (subject_id, name, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_findings_name ON findings (name)",
            """
            CREATE TABLE IF NOT EXISTS supervisor_decisions (
                decision_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL DEFAULT '',
                model_name TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL,
                risk_score REAL NOT NULL DEFAULT 0,
                rationale TEXT NOT NULL DEFAULT '',
                facts_json TEXT NOT NULL DEFAULT '{}',
                policy_decisions_json TEXT NOT NULL DEFAULT '[]',
                category_scores_json TEXT NOT NULL DEFAULT '{}',
                scores_json TEXT NOT NULL DEFAULT '{}',
                packet_id TEXT NOT NULL DEFAULT '',
                action_success INTEGER,
                verified INTEGER,
                detail TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_decision_subject ON supervisor_decisions (subject_id, created_at)",
            """
            CREATE TABLE IF NOT EXISTS recovery_actions (
                action_id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                target_version_id TEXT NOT NULL DEFAULT '',
                model_name TEXT NOT NULL DEFAULT '',
                trigger_summary TEXT NOT NULL DEFAULT '',
                policy_result TEXT NOT NULL DEFAULT '',
                previous_state TEXT NOT NULL DEFAULT '',
                resulting_state TEXT NOT NULL DEFAULT '',
                execution_result TEXT NOT NULL DEFAULT '',
                verification_result TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                started_at REAL NOT NULL,
                finished_at REAL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_recovery_model ON recovery_actions (model_name, started_at)",
            """
            CREATE TABLE IF NOT EXISTS security_evidence (
                evidence_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT '',
                resource_id TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                evidence_reference TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_secev_resource ON security_evidence (resource_type, resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_secev_kind ON security_evidence (kind)",
            """
            CREATE TABLE IF NOT EXISTS provenance_edges (
                edge_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                UNIQUE(subject_type, subject_id, predicate, object_type, object_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_prov_subject ON provenance_edges (subject_type, subject_id)",
            "CREATE INDEX IF NOT EXISTS idx_prov_object ON provenance_edges (object_type, object_id)",
        ),
    ),
)


MIGRATIONS = MIGRATIONS + (
    Migration(
        3,
        "identity_credentials",
        (
            # Phase 2 (SAT-SA foundation hardening): local API-key credentials
            # binding an inbound request to a real Identity record, closing the
            # gap where actor/approver/owner fields were accepted as arbitrary
            # unauthenticated strings (docs/phase2/identity-security.md).
            # Only a salted hash of the credential secret is ever stored;
            # key_id is a non-secret lookup prefix, never the secret itself.
            """
            CREATE TABLE IF NOT EXISTS identity_credentials (
                identity_id TEXT PRIMARY KEY REFERENCES identities(identity_id),
                key_id TEXT NOT NULL UNIQUE,
                key_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at REAL NOT NULL,
                revoked_at REAL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_identity_credentials_key_id ON identity_credentials (key_id)",
        ),
    ),
)


MIGRATIONS = MIGRATIONS + (
    Migration(
        4,
        "evidence_provenance_digests",
        (
            # Phase 2 (SAT-SA foundation hardening): a content digest so a
            # persisted observation/finding/decision/provenance-edge row can be
            # compared against the digest an application-layer caller
            # recomputes from its fields — this detects an in-place row edit
            # that bypassed the repository layer. It is NOT yet a signed,
            # ledger-committed record (that is the "provenance writer" work
            # scoped for a later phase; docs/phase2/evidence-persistence.md
            # states this distinction explicitly, per Rule 7).
            "ALTER TABLE observations ADD COLUMN content_digest TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE findings ADD COLUMN content_digest TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE supervisor_decisions ADD COLUMN content_digest TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE provenance_edges ADD COLUMN content_digest TEXT NOT NULL DEFAULT ''",
        ),
    ),
)


# ---------------------------------------------------------------------------
# SAT-SA canonical store (Phase 3) — the six SIH input categories plus the
# scoping records (entity/assessment/submission) and per-row source-record
# pointers used by the explainability chain. One shared schema_migrations
# chain, deliberately: a single storage engine, a single version history.
MIGRATIONS = MIGRATIONS + (
    Migration(
        5,
        "satsa_core_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS satsa_entities (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                sector TEXT NOT NULL DEFAULT '',
                environment_class TEXT NOT NULL DEFAULT '',
                cohort_attributes_json TEXT NOT NULL DEFAULT '{}',
                access_scope TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS satsa_assessments (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL REFERENCES satsa_entities(id),
                period_start REAL NOT NULL,
                period_end REAL NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                submission_cutoff REAL,
                policy_version TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                supersedes_id TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_assessments_entity ON satsa_assessments (entity_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_submissions (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL REFERENCES satsa_assessments(id),
                entity_id TEXT NOT NULL REFERENCES satsa_entities(id),
                source_system TEXT NOT NULL DEFAULT '',
                declared_period_start REAL,
                declared_period_end REAL,
                file_digests_json TEXT NOT NULL DEFAULT '{}',
                declared_counts_json TEXT NOT NULL DEFAULT '{}',
                schema_name TEXT NOT NULL DEFAULT '',
                received_at REAL,
                signature_status TEXT NOT NULL DEFAULT 'unsigned',
                ingest_status TEXT NOT NULL DEFAULT '',
                ingest_report_json TEXT NOT NULL DEFAULT '{}',
                snapshot_digest TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_submissions_assessment ON satsa_submissions (assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_source_records (
                id TEXT PRIMARY KEY,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                file_digest TEXT NOT NULL,
                format TEXT NOT NULL,
                locator TEXT NOT NULL,
                original_record_digest TEXT NOT NULL,
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_source_records_submission ON satsa_source_records (submission_id)",
        ),
    ),
    Migration(
        6,
        "satsa_workflow_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS satsa_alerts (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                native_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                native_severity TEXT NOT NULL DEFAULT '',
                mapped_severity TEXT NOT NULL DEFAULT 'unknown',
                native_category TEXT NOT NULL DEFAULT '',
                mapped_category TEXT NOT NULL DEFAULT 'unknown',
                asset_refs_json TEXT NOT NULL DEFAULT '[]',
                case_refs_json TEXT NOT NULL DEFAULT '[]',
                detector_refs_json TEXT NOT NULL DEFAULT '[]',
                acknowledged_at REAL,
                closed_at REAL,
                disposition_id TEXT,
                source_record_ref TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL DEFAULT '',
                UNIQUE (entity_id, assessment_id, native_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_alerts_scope ON satsa_alerts (entity_id, assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_cases (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                native_id TEXT NOT NULL,
                opened_at REAL NOT NULL,
                alert_refs_json TEXT NOT NULL DEFAULT '[]',
                owner_pseudonym TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                closed_at REAL,
                closure_reason TEXT NOT NULL DEFAULT '',
                investigation_refs_json TEXT NOT NULL DEFAULT '[]',
                remediation_refs_json TEXT NOT NULL DEFAULT '[]',
                source_record_ref TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                content_digest TEXT NOT NULL DEFAULT '',
                UNIQUE (entity_id, assessment_id, native_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_cases_scope ON satsa_cases (entity_id, assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_investigation_steps (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                action_type TEXT NOT NULL DEFAULT '',
                performed_at REAL NOT NULL,
                sequence INTEGER NOT NULL DEFAULT 0,
                analyst_pseudonym TEXT NOT NULL DEFAULT '',
                evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                result_refs_json TEXT NOT NULL DEFAULT '[]',
                note_text TEXT NOT NULL DEFAULT '',
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_steps_case ON satsa_investigation_steps (case_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_escalations (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                occurred_at REAL NOT NULL,
                alert_id TEXT,
                case_id TEXT,
                destination_role TEXT NOT NULL DEFAULT '',
                trigger TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                policy_exception_ref TEXT,
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_escalations_scope ON satsa_escalations (entity_id, assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_dispositions (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                occurred_at REAL NOT NULL,
                alert_id TEXT,
                case_id TEXT,
                mapped_category TEXT NOT NULL DEFAULT 'unknown',
                reason TEXT NOT NULL DEFAULT '',
                approver_role TEXT NOT NULL DEFAULT '',
                exception_ref TEXT,
                supporting_refs_json TEXT NOT NULL DEFAULT '[]',
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_dispositions_scope ON satsa_dispositions (entity_id, assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_assets (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                submission_id TEXT NOT NULL REFERENCES satsa_submissions(id),
                native_id TEXT NOT NULL,
                criticality TEXT NOT NULL DEFAULT 'unknown',
                environment TEXT NOT NULL DEFAULT '',
                active_intervals_json TEXT NOT NULL DEFAULT '[]',
                control_applicability_json TEXT NOT NULL DEFAULT '[]',
                content_digest TEXT NOT NULL DEFAULT '',
                UNIQUE (entity_id, assessment_id, native_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_assets_scope ON satsa_assets (entity_id, assessment_id)",
        ),
    ),
    # -----------------------------------------------------------------
    # SAT-SA analysis-run persistence (Phase 4). One analysis run, many
    # observations (one per worker), many findings (per observation),
    # many jobs (per worker invocation). All digests are SHA3-256 over
    # the canonical to_dict() of the domain record (matches Phase 2's
    # qsmlops evidence-tables convention).
    Migration(
        7,
        "satsa_analysis_tables",
        (
            """
            CREATE TABLE IF NOT EXISTS satsa_runs (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                snapshot_digest TEXT NOT NULL,
                baseline_digests_json TEXT NOT NULL DEFAULT '{}',
                code_version TEXT NOT NULL DEFAULT '',
                analytics_version TEXT NOT NULL DEFAULT '',
                model_version TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at REAL,
                finished_at REAL,
                observation_ids_json TEXT NOT NULL DEFAULT '[]',
                finding_ids_json TEXT NOT NULL DEFAULT '[]',
                error TEXT NOT NULL DEFAULT '',
                summary_json TEXT NOT NULL DEFAULT '{}',
                content_digest TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_runs_scope ON satsa_runs (entity_id, assessment_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_observations (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES satsa_runs(id),
                worker_name TEXT NOT NULL,
                detector_version TEXT NOT NULL DEFAULT '',
                entity_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                scope_json TEXT NOT NULL DEFAULT '{}',
                state TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_observations_run ON satsa_observations (run_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_findings (
                id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL REFERENCES satsa_observations(id),
                rule_or_category TEXT NOT NULL,
                state TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '',
                scoped_subjects_json TEXT NOT NULL DEFAULT '[]',
                statistic REAL,
                effect REAL,
                threshold REAL,
                confidence_json TEXT NOT NULL DEFAULT '{}',
                evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                limitations TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_findings_observation ON satsa_findings (observation_id)",
            """
            CREATE TABLE IF NOT EXISTS satsa_jobs (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES satsa_runs(id),
                worker_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at REAL,
                finished_at REAL,
                error TEXT NOT NULL DEFAULT '',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                content_digest TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_jobs_run ON satsa_jobs (run_id)",
        ),
    ),
    # -----------------------------------------------------------------
    # SAT-SA trust / provenance (Phase 11). One PQC signature
    # per signed subject (run, finding, ...). A re-sign of the
    # same subject with a different digest replaces the previous
    # row; verification recomputes the digest from the live
    # record and compares.
    Migration(
        8,
        "satsa_trust_receipts",
        (
            """
            CREATE TABLE IF NOT EXISTS satsa_trust_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                algorithm_id TEXT NOT NULL,
                public_key BLOB NOT NULL,
                content_digest TEXT NOT NULL,
                signature BLOB NOT NULL,
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_receipts_subject"
            " ON satsa_trust_receipts (subject_type, subject_id)",
        ),
    ),
    # -----------------------------------------------------------------
    # SAT-SA human review decisions (Phase 12). One row per
    # authenticated examiner action; append-only by convention (a
    # correction creates a new row referencing previous_revision_id,
    # it never edits history).
    Migration(
        9,
        "satsa_review_decisions",
        (
            """
            CREATE TABLE IF NOT EXISTS satsa_review_decisions (
                id TEXT PRIMARY KEY,
                finding_id TEXT NOT NULL,
                principal_identity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                occurred_at REAL NOT NULL,
                previous_revision_id TEXT,
                finding_content_digest TEXT NOT NULL DEFAULT '',
                content_digest TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_satsa_review_decisions_finding"
            " ON satsa_review_decisions (finding_id)",
            "CREATE INDEX IF NOT EXISTS idx_satsa_review_decisions_actor"
            " ON satsa_review_decisions (principal_identity_id, occurred_at)",
        ),
    ),
)


class MigrationRunner:
    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    def _ensure_table(self) -> None:
        self.engine.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )

    def applied_versions(self) -> list[int]:
        self._ensure_table()
        rows = self.engine.query_all(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version"
        )
        return [row["version"] for row in rows]

    def migrate(self) -> list[str]:
        """Apply all pending migrations; returns names applied this call."""
        self.engine.connect()
        self._ensure_table()
        applied = set(self.applied_versions())
        result: list[str] = []
        for migration in sorted(MIGRATIONS, key=lambda m: m.version):
            if migration.version in applied:
                continue
            for statement in migration.statements:
                self.engine.execute(statement)
            self.engine.execute(
                f"INSERT INTO {MIGRATION_TABLE} (version, name, applied_at) VALUES (?,?,?)",
                (migration.version, migration.name, time.time()),
            )
            result.append(f"{migration.version:03d}_{migration.name}")
        return result

# SAT-SA database foundation (Phase 1)

SAT-SA now has two storage modes behind `qsmlops.database.engine.DatabaseEngine`:

| Mode | Configuration | Intended use |
|---|---|---|
| SQLite | `sqlite:///<path>` | Existing offline CLI, FastAPI/Jinja UI, analytical workers, and TRUST-SAT flows |
| PostgreSQL | `postgresql://...` via `QSMLOPS_DB_URL` or `DatabaseService(url)` | Hosted tenant foundation; API and worker integration remain later phases |

Install PostgreSQL support with `pip install -e '.[postgres]'`. `PostgresDatabaseEngine` uses a bounded psycopg connection pool, thread-local transaction pinning, bound values, and dict rows. The current repository qmark placeholders are converted to psycopg placeholders without changing quoted SQL literals. A connection error fails closed; it never selects SQLite as fallback. Set `SATSA_TEST_POSTGRES_DSN` to an isolated test database URL to run PostgreSQL tests. Tests create and drop their own random schema within that database. The local SQLite tests do not need PostgreSQL.

`MigrationRunner` applies the same ordered versions in both modes. PostgreSQL maps SQLite's `AUTOINCREMENT` to identity columns, `BLOB` to `BYTEA`, and `REAL` to double precision, preserving timestamp and measurement precision. PostgreSQL migrations run in a locked transaction, so a failed migration does not mark a version applied. Version 10 adds the tenant foundation without assigning any preexisting row to an organization.

## Ownership model

`satsa_users` links one existing QSMLOps human `identity` to a hosted user profile. `satsa_memberships` grants one existing `satsa_*` role per user and organization. This reuses the current identity and permission vocabulary. `TenantRepository(engine, organization_id, user_id)` checks active identity, user, organization, membership, and role on **every** operation, then includes organization ownership in the SQL lookup or follows the parent relationship. IDs are opaque but never serve as authorization. A foreign resource ID returns no row or raises `PermissionDeniedError` on mutation.

`satsa_entities`, `satsa_assessments`, `satsa_submissions`, and `satsa_runs` have direct `organization_id` columns. Findings, evidence, reviews, jobs, and trust receipts inherit ownership through their existing run or submission relationship. Submission versions and artifact metadata have direct organization keys and composite foreign keys that reject a child/parent organization mismatch. Phase 1 stores artifact metadata only; no file body is placed in PostgreSQL. The stored artifact digest is SHA3-256 of its bytes, which a later upload layer must verify before committing metadata. The older unscoped SAT-SA stores reject PostgreSQL so hosted code cannot silently query a shared population. They remain available on SQLite for the existing offline workflows.

`PeerAccessPolicy.ORGANIZATION_ONLY` is the hosted default. It yields peer IDs only from the same organization. `AUTHORIZED_AGGREGATE` is a reserved policy value that currently fails closed; a later governed aggregate service must enforce consent, cohort thresholds, and raw-record exclusion before it is enabled. The offline peer worker remains unchanged and is not used on hosted PostgreSQL in Phase 1.

## Sessions and provisioning

`TenantAdministration` is an internal provisioning interface, not an exposed API. Its caller must authorize the administrator before creating organizations, linking existing active human identities to users, or assigning memberships. `SessionRepository` stores random-token SHA3-256 digests, user association, creation/expiry/last-activity timestamps, and revocation. Token plaintext is returned once and never stored. This is a persistence primitive; the current offline cookie still carries the existing QSMLOps credential and has **not** silently changed to a hosted session cookie. Hosted login, rotation, CSRF, rate limiting, and audit integration are later security/API work.

## Legacy SQLite data and cutover

Version 10 leaves existing SAT-SA rows with `organization_id=NULL`. They are inaccessible from `TenantRepository`. Migrate the source SQLite schema to version 10 before validation. A migration operator must supply a complete deterministic mapping of every source entity ID to a target organization ID. There is no default organization and no automatic assignment. The read-only `satsa.migration_validation.validate_migration()` checks mapped owners, row IDs and counts per mapped organization, all persisted row values (including canonical digests and relationships), review state, receipt keys/signatures, and optional ledger file integrity/equality. It raises on any discrepancy. The validator is a gate, **not** a data-copy command. The import procedure and live cryptographic verification of the target remain required before any production cutover. Preserve database backups and key/ledger files as one recovery set.

## Phase boundary

PostgreSQL holds the tenant foundation, not a complete hosted assessment workflow. The existing synchronous analysis, review, trust writer, and offline UI remain SQLite-only to avoid unscoped cross-tenant access. Phase 2 will add upload/validation and durable artifact storage; Phase 3 will add a PostgreSQL queue with atomic claim, leases, heartbeat, crash recovery, and idempotent stages. LangGraph follows the persistent run infrastructure. No SaaS deployment or frontend API is enabled by this change.

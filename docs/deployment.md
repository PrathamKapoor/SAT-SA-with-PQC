# SAT-SA Deployment and Operations

## Phase 7 production deployment

### Service topology

The backend image is a non-root Python runtime with the PostgreSQL and S3
extras installed. `docker-compose.saas.yml` runs PostgreSQL, a private
S3-compatible SeaweedFS instance for local production-like testing, a one-shot
migration step, a one-shot local signing-key initializer, FastAPI, and a
separate queue worker. PostgreSQL, object data, and SAT-SA ledger/key data use
independent persistent volumes. The S3 endpoint is not published to the host;
the API is bound to loopback and should be placed behind a TLS reverse proxy.

The bundled SeaweedFS service is a single-node local integration service, not
a claim of highly available object storage. Hosted deployments must provide
managed PostgreSQL, private durable S3-compatible object storage, a shared
durable ledger/key arrangement meeting the TRUST-SAT constraints, and secret
injection through the host platform. The application never returns credentials
or object keys to callers, and application authorization remains the boundary
for artifact access. Do not make the bucket public or grant anonymous listing.

### Local production-like start

Install Docker Engine with the Compose plugin, then:

```powershell
Copy-Item .env.saas.example .env.saas
# Replace all placeholder passwords/keys with unique local test secrets.
docker compose --env-file .env.saas -f docker-compose.saas.yml up --build -d
docker compose --env-file .env.saas -f docker-compose.saas.yml ps
```

The `migrate` service runs `python -m satsa.api.migrate upgrade`; API and worker
never apply schema changes at startup. To inspect or gate manually, set the
same environment as the services and run `python -m satsa.api.migrate status`
or `check`. For a hosted deployment, run `upgrade` as a serialized deployment
job before rolling out API/worker images. A failed migration must stop rollout.
The current migration system has no automatic schema downgrade; restore from a
tested backup or apply a reviewed forward repair. Never run two independent
migration jobs during a rollout (the PostgreSQL advisory lock serializes them,
but deployment should still designate one owner).

The Compose local stack deliberately uses `SATSA_ENVIRONMENT=development` so
HTTP SeaweedFS and a local cookie mode are possible on loopback. Production
must set `SATSA_ENVIRONMENT=production`, configure HTTPS S3, explicit trusted
hosts and HTTPS origins, secure cookies, PostgreSQL, a pre-provisioned signing
key and durable ledger, and `SATSA_AUTO_MIGRATE=false`. Production startup
fails closed when any required configuration is missing or unsafe. Do not use
the local Compose secrets or single-node object store in hosted environments.

Environment settings include:

| Setting | Required | Meaning |
|---|---|---|
| `SATSA_ENVIRONMENT` | hosted | `production` enables fail-closed checks; development/test retain offline defaults |
| `SATSA_DATABASE_URL` | hosted | PostgreSQL DSN; production does not fall back to SQLite |
| `SATSA_DB_POOL_MIN_SIZE`, `SATSA_DB_POOL_MAX_SIZE` | optional | Bounded connection pool (defaults 1/5, max 50) |
| `SATSA_DB_CONNECT_TIMEOUT_SECONDS`, `SATSA_DB_POOL_TIMEOUT_SECONDS`, `SATSA_DB_STATEMENT_TIMEOUT_MS` | optional | Database connection, pool wait, and query bounds |
| `SATSA_STORAGE_BACKEND` | hosted | `s3` in production; `local` for offline SQLite workflows |
| `SATSA_S3_ENDPOINT_URL`, `SATSA_S3_REGION`, `SATSA_S3_BUCKET` | hosted | S3-compatible endpoint, region, and private bucket |
| `SATSA_S3_ACCESS_KEY`, `SATSA_S3_SECRET_KEY` | provider-specific | Both together, or omit for workload identity |
| `SATSA_S3_USE_SSL`, `SATSA_S3_ADDRESSING_STYLE` | hosted | TLS must be enabled in production; style is `auto`, `path`, or `virtual` |
| `SATSA_TRUST_KEY_DIR` | hosted | Mounted/provisioned TRUST-SAT ML-DSA key directory; no key is generated in production |
| `SATSA_LEDGER_PATH` | hosted | Durable ledger path shared by API/worker instances; back it up consistently |
| `SATSA_AUTO_MIGRATE` | hosted | Must be `false`; migrations run in the dedicated job |
| `SATSA_ALLOWED_HOSTS`, `SATSA_ALLOWED_ORIGINS` | hosted | Exact hostnames and HTTPS browser origins; no wildcard |
| `SATSA_COOKIE_SECURE`, `SATSA_COOKIE_SAMESITE`, `SATSA_SESSION_TTL_SECONDS` | hosted | Secure cookie/session behavior; `SameSite=None` requires Secure |
| `SATSA_TRUST_PROXY_HEADERS`, `SATSA_TRUSTED_PROXIES` | proxy deployments | Forwarded headers are used only for explicitly trusted proxy IPs |
| `SATSA_MAX_REQUEST_BYTES`, `SATSA_MUTATION_RATE_LIMIT`, `SATSA_READ_RATE_LIMIT` | optional | API request and per-user rate bounds |
| `SATSA_LOG_LEVEL` | optional | Logging threshold; never include credentials or source data in log payloads |

Do not put real secrets in `.env` files committed to source control. Use the
managed platform's secret store or mounted secret files. The application does
not implement KMS/HSM integration; the signing key must be protected and
backed up by the operator. Loss of the private key prevents new signatures;
old receipts remain verifiable from their public key where the record is intact.

### Health, shutdown and recovery

`GET /health/live` means the API process is alive and deliberately does not
depend on PostgreSQL. `GET /health/ready` checks a database query, current
migration version, configured trust key, and artifact-storage reachability. The
worker has a container readiness command:
`python -m satsa.api.healthcheck --role worker`; it checks the DB, schema,
storage, and execution-queue table. These are readiness probes, not proof that a
full analysis will complete. API and worker handle container shutdown; the
worker stops claiming new work and finishes its current safe execution boundary.
If force-killed, queue leases expire and another worker can recover the run.

### Backup and restore contract

PostgreSQL is authoritative for tenants, users/sessions, submissions,
validation, canonical records, analysis runs/results, trust receipt rows, and
audit mirrors. Back up with provider-managed point-in-time recovery or a
scheduled encrypted `pg_dump` plus WAL retention. Test restore into an isolated
instance, then run migration `check` before routing traffic.

Object storage is authoritative for uploaded artifact bytes. Enable private
bucket versioning/retention and provider durability controls where available;
the application does not configure bucket replication, lifecycle policy, or
encryption at rest. Restore PostgreSQL and the corresponding object-storage
snapshot to a consistent point. If PostgreSQL is restored without objects,
artifact reads and validation will fail digest/existence checks. If objects are
restored without PostgreSQL metadata, they are orphaned and are not addressable
through SAT-SA. Do not garbage collect them without a reviewed reconciliation
process.

The append-only TRUST-SAT ledger and ML-DSA signing key are separate durable
state and must be backed up with PostgreSQL and artifacts. Restoring only the
database can omit the authoritative ledger append for a mirrored audit/receipt;
restoring only the ledger can leave its application references absent. A key
restore mismatch does not invalidate old self-contained receipt signatures but
may prevent finalization and verification of the expected run context. Restore
the database, artifact snapshot, ledger, and public/private key material as a
coordinated recovery set, then run trust verification and ledger-chain
verification before reopening writes. These procedures are operational
recommendations; automated cross-provider snapshots and disaster recovery are
not implemented here.

### Smoke testing and deployment claims

`python scripts/deployment_smoke.py` is the deterministic HTTP workflow check.
It requires analyst, supervisor, and auditor bearer credentials plus an
organization ID; it creates a fresh entity/submission, uploads a real CSV,
validates it, starts a graph run, waits for review, records a supervisor
decision, then checks findings/results, receipt verification, and audit events.
It checks live/readiness endpoints and confirms that the analyst cannot fetch
the resulting run under a foreign organization context.
It must be run against the API and a separately running worker. It creates
persistent, audited test records and should be run against a staging/test
organization, not a live supervisory assessment. The records are not deleted
because decisions and trust history are intentionally durable. It is not run
automatically at service startup.

Docker/Compose availability and target provider credentials vary by environment.
Record local container and hosted deployment results separately. A successful
build or unit suite alone is not deployment verification.

### Verification record (Phase 9, 2026-09-27)

Each layer is classified separately; nothing here is inferred from another.

| Layer | Status | Evidence |
| --- | --- | --- |
| Container build | **Not verified locally** — Docker is not installed on the development machine (Windows or WSL). CI builds the image in the `docker-build-smoke` job and runs the topology in `saas-topology-smoke` when the branch is pushed. | `.github/workflows/ci.yml` |
| Container startup / local production-like compose topology | **Blocked locally** (no Docker). CI path defined; not yet executed because nothing has been pushed. | `docker-compose.saas.yml`, CI job |
| API + worker as separate processes over HTTP | **Verified** with `SATSA_ENVIRONMENT=development`, SQLite and local artifact storage: migration, key initialization, admin bootstrap, member invitation over HTTP, then the full smoke workflow passed (6 findings, receipt verified, 20 audit events). | local run via `scripts/deployment_smoke.py` |
| PostgreSQL (live) | **Pending** — a PostgreSQL 18 server is available locally; live tests need `SATSA_TEST_POSTGRES_DSN` for a scratch database. | `tests/test_postgres_*.py` (skipped without DSN) |
| S3-compatible storage (live) | **Not verified.** Only mocked/emulated S3 tests exist; SeaweedFS runs only inside the compose topology. | — |
| HTTP smoke against the compose topology | **Not executed** locally (blocked by Docker); defined in CI. | — |
| Hosted deployment | **Not verified** in Phase 9. The Render site hosts the separate web UI, not this API/worker topology. | — |

Phase 10 re-check (2026-09-27): Docker is still not installed (Windows and
WSL) and `SATSA_TEST_POSTGRES_DSN` is still unset at process, user and machine
level, so container, compose, SeaweedFS, live-PostgreSQL and
PostgreSQL-vs-SQLite measurements remain **blocked**; no result is claimed.
The SeaweedFS service relies on the image's default `mini -dir=/data` mode,
which serves S3 on port 8333 and pre-creates `S3_BUCKET` — confirmed from the
upstream Dockerfile and documentation, not by execution. To unblock:

1. PostgreSQL: create a scratch database and set
   `SATSA_TEST_POSTGRES_DSN=postgresql://<user>:<password>@localhost:5432/<db>`,
   then run `python -m pytest tests/test_postgres_engine.py
   tests/test_postgres_migrations.py tests/test_tenant_schema.py
   tests/test_tenant_boundary.py tests/test_phase2_submission_platform.py
   tests/test_phase3_analysis_execution.py tests/test_phase4_langgraph.py
   tests/test_phase7_runtime.py -ra`.
2. Containers: install Docker, or push the branch so the `saas-topology-smoke`
   CI job runs the compose topology and uploads `smoke-report.json`.

Phase 11 status (2026-09-27, re-checked: Docker absent, DSN unset):

| Capability | CONFIGURED | BUILD VERIFIED | LOCAL DEPLOYMENT VERIFIED | INTEGRATION VERIFIED | HOSTED DEPLOYMENT VERIFIED |
| --- | --- | --- | --- | --- | --- |
| API + worker processes (SQLite, local storage) | yes | n/a | **yes** (18/18 HTTP checks) | no | no |
| Container images | yes | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Compose topology | yes | NOT EXECUTED | NOT EXECUTED (Docker absent) | NOT EXECUTED | NOT EXECUTED |
| Live PostgreSQL | yes | n/a | NOT EXECUTED (DSN absent) | NOT EXECUTED | NOT EXECUTED |
| Live S3 / SeaweedFS | yes | n/a | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| CI `saas-topology-smoke` | yes (build, start, migrate, key init, readiness, bootstrap, provision, 18-check smoke, logs, teardown) | NOT EXECUTED (no push authorized) | — | — | — |
| Hosted API/worker | no | NOT EXECUTED | n/a | n/a | NOT EXECUTED |

## Legacy offline deployment

The following CLI/Jinja deployment is the offline-compatible single-machine
path. The supported API/worker topology is documented above. These workflows
continue to use SQLite and local files, and are not the hosted SaaS run mode.

No cloud. No SaaS. No external AI. No remote fonts, CDN, or telemetry.
Everything below runs on an air-gapped host.

## 1. Dependencies

- Python ≥ 3.10 (3.13 verified)
- `pip install -r requirements.txt`

Core (runtime — mirrors `[project].dependencies` in `pyproject.toml`
and `requirements.txt`'s Runtime section exactly): `kyber-py`,
`dilithium-py`, `numpy`, `scipy`, `cryptography`, `pyyaml`, `fastapi`,
`starlette`, `uvicorn`, `python-multipart` (required — Starlette's
multipart form/file-upload parsing, used by `/ingest`), `click`,
`scikit-learn`, `pydantic`, `python-pkcs11` (optional, HSM only). Dev
(mirrors `[project.optional-dependencies].dev`): `pytest`, `httpx`,
`setuptools` (required to run the test suite — Python 3.12+ environments
no longer bundle it; see `tests/test_phase86_packaging_discovery.py`).

## 2. Verify the tree

```bash
python -m compileall satsa qsmlops scripts tests
python -m pytest tests/ -q        # release acceptance requires 0 failed
```

## 3. Key setup (TRUST-SAT)

The PQC keypair is generated in-process on first signed run and
persisted to `<key-dir>/satsa_trust_key.json`:

```bash
mkdir -p ./keys
# keys are created automatically by the first `analyze`/`demo` run.
# POSIX: the key file + directory are chmodded owner-only (0600/0700).
# Windows: ACLs are inherited from the user profile (documented limit).
```

Key providers: `file` (default), `vault/passphrase` (see
`satsa/analysis/trust_storage.py`), hardware/PKCS#11 abstraction
(`qsmlops/crypto/` — fails closed; no token on Earth supports ML-DSA
yet, self-certified in `reports/A12_*` / `A13_*`).

Rotate by replacing the key file; old receipts remain verifiable
(they carry their own algorithm + public key).

## 4. Database initialization

```bash
# The CLI migrates automatically on every invocation:
sat-sa --db ./satsa.db --trust-key-dir ./keys agents
```

Migrations live in `qsmlops/database/migrations.py` and are
idempotent. SQLite is the store; the hash-chained evidence ledger
remains the source of truth. Single-writer boundary documented.

## 5. Load the demo + run the story

```bash
python demo.py --db ./demo.db --keys ./demo-keys
# or: sat-sa --db ./demo.db --trust-key-dir ./demo-keys demo
```

Expected: 5 CSEs ingested, 16 workers × 5 runs, top-risk entity
surfaced, run + findings VERIFIED, a review decision recorded, and a
supervisor decision (`SATSA_INSPECT`) emitted.

## 6. Serve the UI (offline)

```bash
python scripts/serve_ui.py --db ./satsa.db --trust-key-dir ./keys --port 8000
```

`satsa.ui.create_app` takes a bound `SatsaService`, not a zero-argument
factory, so it cannot be launched with `uvicorn --factory` directly;
`scripts/serve_ui.py` does the `SQLiteDatabaseEngine` + migration +
`SatsaService` + `create_app` wiring and calls `uvicorn.run(app, ...)`
itself. It also loads the committed demo dataset automatically if the
database is empty (`--no-demo` to skip). Verified this launches and
serves real pages (`/`, `/entities`, `/findings`, `/trust`,
`/architecture`, `/agents`, `/security-data`, `/decisions`) with a
running server, not just importable in a test.

All assets are local (`satsa/ui/static/`, system fonts). No webfonts,
no CDN, no JS frameworks. Judge path: `/` → entity → finding →
`/trust` → review → `/decisions` → `/architecture` → `/agents`.

## 7. Validation

```bash
sat-sa --db ./demo.db validate     # synthetic ground truth + expert labels
python scripts/benchmark_scaling.py  # 5/10/25/50 CSE scaling numbers
```

## 8. Air-gapped install checklist

1. Copy this repository + a Python ≥ 3.10 + wheels for
   `requirements.txt` on removable media.
2. `pip install --no-index --find-links ./wheels -r requirements.txt`
3. `python -m compileall satsa qsmlops scripts tests`
4. `python -m pytest tests/ -q` (must be 0 failed).
5. `python demo.py` (must print DEMO COMPLETED SUCCESSFULLY).
6. Serve the UI on loopback; walk the judge path.

## 9a. Authentication bootstrap (TRUST-SAT identity, P18)

Recording a review decision (UI `/findings/{id}/review` or CLI
`sat-sa review`) requires an authenticated identity holding the
`decision.record` permission (role `satsa_supervisor` or
`satsa_admin`) — a caller-supplied header or `--principal` string is
no longer accepted; both paths resolve through the same
`qsmlops.security.identity.IdentityService` used by the underlying
MLOps platform. Cold-start on a fresh install:

```bash
python - <<'PY'
from pathlib import Path
from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.security.identity.models import KIND_HUMAN
from satsa import security as satsa_security

eng = SQLiteDatabaseEngine(Path("./satsa.db")); eng.connect()
MigrationRunner(eng).migrate()
idsvc = satsa_security.build_identity_service(eng, ledger_dir=Path("./keys"))
supervisor = idsvc.create_identity(
    KIND_HUMAN, "examiner-1", owner="examiner-1", role="satsa_supervisor")
token = idsvc.issue_credential(supervisor.id)
print("credential (store securely; shown once):", token)
PY
```

Use the token two ways:

- **Browser (UI)**: visit `/login`, paste the token — it is stored as
  an HttpOnly cookie (`satsa_credential`), not readable by page JS.
- **API/CLI**: `Authorization: Bearer <token>` header, or
  `sat-sa review --credential <token> ...` / `SATSA_CREDENTIAL` env
  var.

Additional roles: `satsa_viewer` (read-only), `satsa_analyst` (runs
analytics/validation), `satsa_auditor` (read + platform audit log),
`satsa_admin` (full control). See
`qsmlops/security/permissions/model.py` for the exact permission
grants per role, and `tests/test_phase63_satsa_auth_rbac.py` for the
adversarial test suite (unauthenticated, wrong-role, forged token,
revoked credential — each proven to fail closed).

## 9. Configuration

`configs/settings.{development,testing,production}.yaml`. Secrets are
never committed (see `.gitignore`); the secret audit is part of the
final report.

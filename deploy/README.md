# Deploying SAT-SA on a single host

This directory deploys the full SAT-SA product (web workbench, API, analysis
worker, PostgreSQL, object storage, TRUST-SAT) on one Linux host with Docker
Compose and automatic HTTPS. The same files are exercised by the
`production-stack` CI job, which starts the whole stack with production
settings and runs the browser workflow through HTTPS against it.

Offline development does not use any of this: see `../web/README.md`
(`scripts/local_stack.py`, SQLite, no Docker).

## 1. Host decision

**Selected:** a single Linux virtual machine that you control (any provider:
for example DigitalOcean, Hetzner, AWS EC2, Azure), running Docker Engine with
the Compose plugin. No provider-specific configuration is in the repository.

Why, from SAT-SA's own requirements (`../docs/deployment.md`, hosting contract):

- The TRUST-SAT evidence ledger and the ML-DSA-65 signing key must be on
  durable storage **shared by the API and the worker**, which are separate
  processes (the API appends audit entries; the worker finalizes runs). On one
  host, both containers mount the same named volume.
- Managed PaaS volumes checked on 2026-09-28 do not offer that:
  Railway documents "Each service can only have a single volume" and
  "Replicas cannot be used with volumes"
  ([docs.railway.com/reference/volumes](https://docs.railway.com/reference/volumes));
  Fly.io documents "A volume can be attached to only one Machine" and "you
  can't share a volume between apps"
  ([docs.fly.io/volumes/overview](https://docs.fly.io/volumes/overview/)).
  Running the API and worker as one service to share a volume would collapse
  a separation the product relies on.
- The topology below is already CI-tested; the host only needs Docker.

Limitations of this choice: one host is a single point of failure (no
automatic failover); scaling is vertical, or more workers on the same host;
backups are the operator's responsibility (section 7). Costs were not assessed
here; they depend on the provider and machine size.

**Object storage.** Uploaded evidence must not live on a container's
filesystem. Two supported options:

1. **External S3-compatible storage over HTTPS (recommended):** the provider's
   object storage (for example AWS S3, DigitalOcean Spaces, Hetzner Object
   Storage, Cloudflare R2). Durable independently of the host.
2. **Bundled single-node storage** (`compose.objectstore.yml`): SeaweedFS on
   the same host, reached through an internal TLS endpoint. Self-contained, but
   the data shares the host's disk; back it up (section 7).

## 2. Architecture

```
browser --HTTPS--> caddy :443  (TLS, security headers, HTTP->HTTPS)
                     |
                     v
                   web :3000     Next.js; server-side API calls only
                     |           (edge network + backend network 172.30.0.10)
                     v
                   api :8000     FastAPI, not published; trusts X-Forwarded-For
                     |           only from 172.30.0.10
        +------------+------------+
        v            v            v
   database       worker       object storage (S3 over HTTPS)
  PostgreSQL 17   queue, leases, LangGraph, 16 analytical workers,
                  risk, recommendations, TRUST-SAT finalization
        api + worker share volume satsa_durable: /data/evidence-ledger.jsonl, /data/keys
```

Only Caddy publishes ports (80 and 443). One-shot steps run before the
services on every `up`: `migrate` (schema upgrade; a failure stops the
rollout) and `key-init` (provisions the TRUST-SAT key once, then confirms it).
With bundled storage, `s3-ca` copies Caddy's local root certificate for the
backend to trust.

All backend containers run with `SATSA_ENVIRONMENT=production`, which fails
closed unless PostgreSQL, S3 over HTTPS, secure cookies, explicit hosts, a
provisioned signing key, a durable ledger path and
`SATSA_AUTO_MIGRATE=false` are all in place.

## 3. Prepare the host

1. A Linux VM with at least 2 vCPU, 4 GB RAM and enough disk for PostgreSQL,
   images and (if bundled) evidence files.
2. Install Docker Engine with the Compose plugin (docs.docker.com/engine/install).
3. Firewall: allow 22 (SSH, restricted to your addresses), 80 and 443. Nothing
   else needs to be reachable.
4. DNS: an A (and AAAA if used) record for your hostname pointing at the VM.
   Caddy obtains the certificate from Let's Encrypt on first start; ports 80
   and 443 must be reachable for that.

## 4. First deployment

```bash
git clone https://github.com/PrathamKapoor/SAT-SA-with-PQC.git satsa && cd satsa
cp deploy/production.env.example deploy/production.env
chmod 600 deploy/production.env
# edit deploy/production.env: SATSA_SITE_ADDRESS, SATSA_POSTGRES_PASSWORD
# (openssl rand -hex 32), S3 endpoint, bucket and credentials

COMPOSE="docker compose -f deploy/compose.production.yml --env-file deploy/production.env"
# bundled storage instead of external S3:
# COMPOSE="docker compose -f deploy/compose.production.yml -f deploy/compose.objectstore.yml --env-file deploy/production.env"

$COMPOSE config --quiet          # validates the configuration
$COMPOSE up -d --build           # migrate, key-init, then api, worker, web, caddy
$COMPOSE ps                      # api, worker and web should become healthy
```

Create the first organization and its administrator (once per installation;
the credential is printed once, store it securely):

```bash
PW=$(grep '^SATSA_POSTGRES_PASSWORD=' deploy/production.env | cut -d= -f2)
$COMPOSE exec -T api python scripts/bootstrap_satsa_admin.py \
  --database-url "postgresql://satsa:${PW}@database:5432/satsa" \
  --ledger /data/identity-audit-ledger.jsonl \
  --name "Administrator name" --email admin@example.org --organization "Organization name"
```

Sign in at `https://<your hostname>` with that credential and add members on
the **Members** page (each member's credential is shown once), or from the
host:

```bash
$COMPOSE exec -T api python scripts/provision_members.py --api http://api:8000 \
  --credential '<admin credential>' --organization '<organization id>' \
  --member supervisor "Supervisor name" supervisor@example.org
```

## 5. Verify

```bash
export SATSA_SMOKE_ORGANIZATION_ID=... SATSA_SMOKE_ANALYST_CREDENTIAL=... \
       SATSA_SMOKE_SUPERVISOR_CREDENTIAL=... SATSA_SMOKE_AUDITOR_CREDENTIAL=...
COMPOSE="$COMPOSE" bash deploy/smoke.sh
```

`smoke.sh` checks the HTTPS entry point (reachability, redirect, security
headers, sign-in required), API liveness and readiness, worker readiness, then
runs the full workflow through the API on the real worker: submission,
upload, validation, run, findings, risk, recommendations, evidence records,
priorities, decision, TRUST-SAT finalization and verification, audit. It
creates durable, audited records: use a test organization.

The browser test can target the deployment too (from a machine with Node):

```bash
cd web && npm ci && npx playwright install chromium
SATSA_E2E_BASE_URL=https://<hostname> SATSA_E2E_CREDENTIALS=/path/credentials.json npm run test:e2e
```

`credentials.json` holds `organization_id`, `admin`, `analyst` and
`supervisor` credentials of a test organization.

## 6. Updates and rollback

```bash
git pull
SATSA_IMAGE_TAG=$(git rev-parse --short HEAD) $COMPOSE up -d --build
```

`migrate` runs first on every `up`; the API and worker refuse to start on an
out-of-date schema. Rolling back the application is `git checkout <previous
commit>` and the same command. Migrations are forward-only: if the update
changed the schema, restore the pre-update database backup (section 7) before
starting the older version.

## 7. Backups

`deploy/backup.sh` takes one consistent recovery set; `deploy/restore.sh`
puts it back on a host with no stack and no SAT-SA volumes. CI runs the whole
cycle on every push (production-stack job): record every finished run's
TRUST-SAT status, back up, `down -v`, restore, start, and require every run
that verified before to verify again.

```bash
COMPOSE="docker compose -f deploy/compose.production.yml --env-file deploy/production.env"
deploy/backup.sh /secure/backups          # stops api+worker for the snapshot (about a minute)
# restore, on an empty host or after `$COMPOSE down -v`:
deploy/restore.sh /secure/backups/satsa-<UTC stamp>
$COMPOSE up -d && deploy/smoke.sh
```

| In the backup | Contents | Notes |
|---|---|---|
| `database.dump` | PostgreSQL (`pg_dump -Fc`) | every tenant's records, runs, decisions, receipts |
| `durable.tar.gz` | volume `satsa_satsa_durable` | TRUST-SAT ledger, identity audit ledger, **ML-DSA signing key** |
| `objects.tar.gz` | volume `satsa_object_data` | bundled storage only; with external S3 use the provider's versioning/replication |
| `SHA3-256SUMS` | digests | `restore.sh` refuses a set whose digests do not match |

The API and worker are stopped during the backup so the database, the
append-only ledgers and evidence are captured at one instant; a finalization
row must never reference a ledger entry the backup lacks. Restoring one part
without the others breaks verification of finalized runs.

The backup holds the private signing key and every tenant's evidence: encrypt
it (for example `age` or `gpg`) before it leaves the host, keep it
access-controlled, and keep at least one copy off the host. Test a restore on
a spare machine periodically; `scripts/verify_restored_state.py` is the check
CI uses (record before, compare after).

## 8. Operations and troubleshooting

- Logs: `$COMPOSE logs -f api worker` (JSON lines with `request_id`; the web
  UI shows the same request ID in every error). Worker log lines name the run.
- Health: `$COMPOSE ps`; details `docker inspect --format '{{json .State.Health}}' satsa-api-1`
  (the readiness check prints the failing dependency).
- `api` unhealthy: usually database, schema or object storage; the health log
  says which. `migrate` failed: `$COMPOSE logs migrate`.
- Certificate not issued: DNS must point at the host and ports 80/443 be
  reachable; `$COMPOSE logs caddy`.
- Runs stay `queued`: the worker is not running or not ready
  (`$COMPOSE logs worker`). A stopped worker loses nothing: queued runs are
  picked up when it returns, and runs whose lease expired are recovered.
- More analysis capacity: `$COMPOSE up -d --scale worker=2`.

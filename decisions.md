# Decision Log

Every meaningful change to SAT-SA / TRUST-SAT records its decisions here:
why this approach, why this package, what else was considered, and what it
means for later work. Code says *what*; this file says *why*.

## How to add an entry

Add an entry when a change:

- introduces, removes or pins a dependency;
- changes architecture, data model, a migration, an API contract or a security boundary;
- picks one approach over a credible alternative;
- does something that would look wrong or odd to a later reader.

Append new entries at the end of the log (newest last), using this format:

```
### D-NNN: <short decision>
- Date / phase / commit: YYYY-MM-DD, Phase N, <commit>
- Context: the problem or requirement that forced a choice
- Decision: what was chosen
- Why: the reasons, including evidence (measurements, failures, constraints)
- Alternatives considered: what else was possible and why it lost
- Consequences: what later work must respect; what this makes harder
- Files: main files affected
```

Never rewrite an old entry to match new code. If a decision is reversed, add
a new entry that supersedes it ("Supersedes D-012") and say why.

Entries D-001 to D-012 summarise architecture decisions from earlier phases
that the current code still depends on. They were reconstructed from the code
and docs; where the original reasoning was not recorded, only what is visible
in the repository is stated.

---

## Foundation (earlier phases, still in force)

### D-001: Python backend: FastAPI and Pydantic v2
- Date / phase / commit: Phase 6 to 19
- Context: The analytics engine (`satsa/`, `qsmlops/`) is Python. It needed an HTTP API with a typed contract the web tier could rely on.
- Decision: FastAPI (`fastapi>=0.110`) on uvicorn, with Pydantic v2 schemas in `satsa/api/schemas.py`.
- Why: Same language as the analytics. The OpenAPI contract is generated from the code. Pydantic validates input at the boundary (for example `MLDatasetInput.name` pattern, `DecisionInput.action` literals).
- Alternatives considered: A separate Node backend. It would have duplicated the domain model across languages.
- Consequences: The API contract test (`docs/API_CONTRACT.md`, 71 routes) breaks if a route is added without updating it.
- Files: `satsa/api/__init__.py`, `satsa/api/schemas.py`, `satsa/api/ml_routes.py`

### D-002: One migration history for SQLite and PostgreSQL
- Date / phase / commit: Phase 1 and later
- Context: The product must run offline (SQLite) and hosted (PostgreSQL) from the same code.
- Decision: Migrations are written once in SQLite DDL (`qsmlops/database/migrations.py`). `postgres_migrations.py` maps the few dialect differences (REAL, BLOB, AUTOINCREMENT, and since Phase 23 one JSON expression) and rejects anything it does not know.
- Why: There is only one schema history to reason about. Anything unsupported fails loudly instead of diverging silently.
- Alternatives considered: Alembic or ORM migrations. That would mean a second schema source and more dependencies.
- Consequences: Migrations are append-only. New DDL must work on both dialects or get an explicit mapping. The API refuses to start on an outdated schema.
- Files: `qsmlops/database/migrations.py`, `qsmlops/database/postgres_migrations.py`, `satsa/api/runtime.py`

### D-003: Post-quantum TRUST-SAT receipts with ML-DSA-65 and a hash-chained ledger
- Date / phase / commit: Phase 5 and later
- Context: Supervisory records must be verifiable later, and evidence must stay credible against a future quantum adversary.
- Decision: Each finalized run is signed with ML-DSA-65 (`dilithium-py`). Events go into an append-only evidence ledger on `/data`. Verification re-derives the canonical digest from the live rows.
- Why: ML-DSA is the NIST post-quantum signature standard. Re-deriving the digest detects tampering at verification time.
- Alternatives considered: Classical signatures only. They don't meet the project's post-quantum objective.
- Consequences: The signing key (`/data/satsa/keys/satsa_trust_key.json`) must never be regenerated on an initialized volume; `deploy.sh` refuses to continue if it is missing. The claim is detection of tampering, not tamper-proof storage.
- Files: `satsa/analysis/trust.py`, `deploy/aws/deploy.sh`

### D-004: LangGraph for run orchestration, with PostgreSQL checkpoints
- Date / phase / commit: Phase 4 and later
- Context: Runs are long. They must survive worker restarts and pause for a human decision.
- Decision: `langgraph==1.2.10` with `langgraph-checkpoint-postgres`/`-sqlite`. The graph runs readiness → analysis → recommendations → model_inference → reviewer_briefing → human_review (`interrupt`) → trust_boundary.
- Why: Durable checkpoints mean a run resumes after a crash or reboot. `interrupt()` gives a real human-review pause. The checkpoint lives in the same database as the records.
- Alternatives considered: A hand-rolled state machine. It would have to reimplement durable resume and interrupt.
- Consequences: Versions are pinned exactly. Checkpoint reads are scope-checked against the run (see D-020). LangGraph orchestrates only; the analytics stay deterministic.
- Files: `satsa/analysis/graph.py`, `satsa/analysis/execution.py`

### D-005: Database-backed job queues with leases; no broker
- Date / phase / commit: Phase 3, 19, 21
- Context: The API and the worker are separate processes, and work must not be lost or run twice.
- Decision: The `satsa_execution_jobs` and `satsa_ml_jobs` tables, with lease and heartbeat (`ExecutionQueue.claim/heartbeat/complete/fail`). Expired leases are reclaimed.
- Why: The database is already transactional, so this adds no extra infrastructure. That fits single-VM cost limits.
- Alternatives considered: Redis, SQS or Celery. They mean more services and cost, and no extra correctness.
- Consequences: Throughput is bounded by the database, which is acceptable for periodic assessment. Don't add Redis "because it is useful".
- Files: `satsa/analysis/execution.py`, `satsa/mlops/jobs.py`

### D-006: Rate limits and sessions stored in the database
- Date / phase / commit: Phase 19 and 20
- Context: The API needed abuse protection and revocable sessions without a cache service.
- Decision: Per-client-address limits in `satsa_api_rate_limits`: login 5/min, mutations 30/min, reads 300/min. Sessions are stored as SHA3 digests, and the cookie `satsa_api_session` is HttpOnly on path `/api/v1`.
- Why: Limits survive restarts and need no Redis. Session tokens are never stored in plaintext.
- Consequences: Every browser user behind one address shares the budget, which forced the E2E changes in D-016. Don't raise the limits to make tests pass.
- Files: `satsa/api/security.py`, `satsa/api/settings.py`

### D-007: Advisory model is logistic regression trained on the organization's own decisions
- Date / phase / commit: Phase 21
- Context: An advisory score to help order the review queue, governed end to end.
- Decision: `MODEL_FAMILY = "logistic_regression"` in numpy, with 11 features (`review-outcome-features/1`). Labels: 1 if the supervisor confirmed or escalated, 0 if dismissed. The governance gate (`satsa/mlops/policy.py`) needs 30 or more rows, 8 or more per class, ROC-AUC ≥ 0.60 and Brier ≤ 0.25.
- Why: Explainable, small, and needs no extra ML framework. The thresholds are documented in `policy.py`.
- Alternatives considered: Gradient boosting or a deep learning framework. Heavier dependencies on very little data.
- Consequences: The model never changes findings or decisions. It abstains when it can't score reliably. Its metrics on synthetic data mean nothing.
- Files: `satsa/mlops/*`

### D-008: Model providers behind a fallback chain, with a deterministic floor
- Date / phase / commit: Phase 22
- Context: Reviewer briefings could use hosted models (NVIDIA NIM, OpenRouter, Bedrock), but the product must work with none.
- Decision: `SATSA_LLM_CHAIN` lists the providers. `run_chain` retries transient errors within limits, then falls back to `briefing.deterministic`, then abstains. Keys go only to the worker (`/etc/satsa/llm.env`).
- Why: No external dependency is required to run, provider failures can't block a run, and secrets never reach the browser or the API.
- Consequences: In production, no provider secret exists, so every briefing is `deterministic`.
- Files: `satsa/llm/*`, `deploy/aws/compose.aws.yml`, `deploy/aws/deploy.sh`

### D-009: AWS hosting is one EC2 instance with Compose, plus RDS and S3
- Date / phase / commit: Phase 22
- Context: $100 of AWS credits; quality and cost were the priorities; a persistent LangGraph worker was needed.
- Decision: A t3.small with Docker Compose and Caddy, RDS PostgreSQL 17 on db.t4g.micro, S3 through the instance role, a separate EBS `/data` volume, SSM instead of SSH, and one CloudFormation stack.
- Why: The cheapest setup that keeps the worker persistent and the data durable (RDS, S3, EBS). Caddy issues TLS automatically.
- Alternatives considered: ECS/Fargate with an ALB (cost), or serverless (long-running worker and checkpoints).
- Consequences: No high availability. Instance loss is recovered by redeploying onto the surviving data.
- Files: `deploy/aws/*`

### D-010: Images are built from `git archive`, never from the working tree
- Date / phase / commit: Phase 22
- Context: Builds on Windows must be reproducible and contain exactly the committed code.
- Decision: `publish.sh` requires a clean tree and builds from `git -c core.autocrlf=false archive`, so the files keep LF endings.
- Why: An image must equal a commit (see D-013). Stray local files must never ship.
- Files: `deploy/aws/publish.sh`, `.gitattributes`

### D-011: The research paper is never committed
- Date / phase / commit: Phase 21 and later
- Decision: `paper/`, `research/` and `*.tex` are untracked and git-ignored.
- Why: An explicit owner requirement.
- Consequences: Check `git diff --name-only` before every commit.

### D-012: All commits as PrathamKapoor, with no AI attribution
- Decision: Every commit and push is authored as `PrathamKapoor <prathamkapoor027@gmail.com>`, with no co-author or "generated by" lines.
- Why: An explicit owner requirement. It overrides tool defaults.

---

## Phase 23 (2026-09-30 to 2026-10-01)

### D-013: The release identifier is the Git commit
- Date / phase / commit: 2026-09-30, Phase 23, `a626a9b`
- Context: It had to be possible to say exactly which version is running. `__version__` (`0.16.0-phase52-ui`), `pyproject.toml` (0.1.0) and `package.json` (0.1.0) disagreed, and the only tags were `archive/*`.
- Decision: Both images are built with `ARG SATSA_RELEASE` set to the commit. `/health/live` returns `release`, the System page shows the API and web releases, and `deploy.sh status` prints those plus `deployed.json`.
- Why: The commit is already unique and authoritative. A new semver scheme would be invented, not established.
- Alternatives considered: Tagging v1.0.0. Rejected because the project has no versioning convention.
- Consequences: Builds that don't go through `publish.sh` report `unreleased`. The deploy is correct when all three sources show the same commit.
- Files: `Dockerfile`, `web/Dockerfile`, `deploy/aws/publish.sh`, `satsa/api/__init__.py`, `web/src/app/(app)/workbench/system/page.tsx`

### D-014: Demo data lives in its own organization; a reset revokes members and deletes nothing
- Date / phase / commit: 2026-09-30, Phase 23, `a626a9b`, `f0aeac8`
- Context: The demo had to be deterministic and resettable, but supervisory records, receipts and audit history are immutable.
- Decision: `scripts/demo_environment.py` (called by `deploy.sh demo`) creates "SAT-SA demo (synthetic data) <UTC time>" and its members, seeds the 5 synthetic CSEs through the real API, records one decision and verifies it. A rerun revokes the previous demo's members and creates a new organization. Member names and emails include the timestamp.
- Why: Deleting evidence would contradict TRUST-SAT. A separate organization keeps demo data out of real tenants. Identity names are platform-unique: a reset failed with 409 `IDENTITY_EXISTS` until the timestamp was added.
- Consequences: Old demo organizations accumulate, as inert history.
- Files: `scripts/demo_environment.py`, `deploy/aws/deploy.sh`

### D-015: Synthetic supervisor rule for the MLOps demo: confirm if there are 5 or more signal findings
- Date / phase / commit: 2026-10-01, Phase 23, `21fa972`
- Context: The model needs both classes. The first rule ("confirm if any signal") confirmed all 39 runs, because every synthetic CSE has some signals (ANOM 10, EXEC 9, NEG 7, PEER 3, HEALTHY 1). Validation correctly rejected the single-class dataset.
- Decision: Confirm runs with 5 or more signals and dismiss the rest. The rule is written into every decision reason.
- Why: It produces two classes honestly through real decisions, without inserting labels by hand.
- Alternatives considered: Loosening validation, or writing labels into the database. Both were forbidden.
- Consequences: The labels are perfectly separable, so ROC-AUC 1.0 is meaningless. Never present these numbers as real performance.
- Files: `scripts/demo_mlops.py`

### D-016: Fix polling and tests instead of raising rate limits
- Date / phase / commit: 2026-09-30, Phase 23, `5ba4bfe` and the E2E commits
- Context: CI's browser tests hit 429s. One open run page refreshed every 3 seconds at about 11 reads per refresh, around 220 of the 300 reads per minute allowed per address.
- Decision: The default `AutoRefresh` interval is now 10 seconds. The E2E suite reloads a page whose render hit the limit (`open()` helper), and reloads after a dataset build.
- Why: The polling was a real product defect, since a second tab would get 429s. The limits are a security control.
- Alternatives considered: Raising `SATSA_READ_RATE_LIMIT` in CI. Rejected because it weakens what is tested.
- Consequences: In-progress pages update every 10 seconds.
- Files: `web/src/components/domain/auto-refresh.tsx`, `web/e2e/workbench.spec.ts`

### D-017: Expression index for the tenant audit query (migration 19)
- Date / phase / commit: 2026-09-30, Phase 23, `1d89bc8`
- Context: The audit trail filtered every tenant's events by `metadata::jsonb->>'organization_id'` with no index, a scan that grows without limit.
- Decision: Index `json_extract(metadata,'$.organization_id'), timestamp`, translated for PostgreSQL to `(metadata::jsonb->>'organization_id')` to match the query exactly. Also add organization indexes on the ML training-run, drift-report and deployment lists.
- Why: Audit metadata is always written with `json.dumps`, so the cast can't fail at write time any more than it already would at read time.
- Alternatives considered: A real `organization_id` column on `audit_events`. A larger change to the shared audit ledger schema.
- Consequences: If the audit query expression changes, the index stops being used. `tests/test_phase23_indexes.py` checks the query plan.
- Files: `qsmlops/database/migrations.py`, `qsmlops/database/postgres_migrations.py`

### D-018: The public hostname lives in SSM and is read at deploy time
- Date / phase / commit: 2026-09-30, Phase 23, `758af7e`
- Context: The custom domain `trustsat.mpst.me` had to be applied. The address was baked into EC2 user data, which runs once at first boot, and changing it stops and starts the instance.
- Decision: The `/satsa/<env>/site-address` SSM parameter is read by `deploy.sh`. User data keeps the sslip.io name, which Caddy serves as an alias (`SATSA_SITE_ALIASES`).
- Why: Changing the domain then needs no instance change, and the old link keeps working.
- Consequences: Stack updates must pass `--tags project=satsa` and be previewed with a change set. The one update that introduced this did stop and start the instance once, with data unaffected.
- Files: `deploy/aws/satsa.cfn.yaml`, `deploy/aws/deploy.sh`, `deploy/caddy/site.caddy`, `deploy/compose.production.yml`

### D-019: The restore drill restores next to production, never in place
- Date / phase / commit: 2026-10-01, Phase 23, `ecf8d30`
- Decision: Restore the snapshot pair into a temporary RDS instance and EBS volume. Migrate the copy forward, as `deploy.sh deploy` would. Run a separate API container against it, verify, then delete.
- Why: It proves the backup without risking production.
- Consequences: Cutting production over to restored resources is still unexercised.
- Files: `docs/backup-restore.md`

### D-020: A graph checkpoint without scope fields means "starting", not a scope violation
- Date / phase / commit: 2026-10-01, Phase 23, `cc8f0e6`
- Context: `POST /api/v1/runs` returned 403 for a run it had just created. A fast worker had already written LangGraph's first checkpoint, which has no `run_id`, `organization_id` or `submission_version_id`, and `get_graph_progress` compared those `None` values with the run.
- Decision: If none of the scope keys is present, return `current_stage: "starting"`. If any key is present and doesn't match, still refuse with 403.
- Why: It fixes a real race without weakening the cross-tenant check.
- Consequences: Covered by two tests in `tests/test_phase4_langgraph.py`.
- Files: `satsa/analysis/execution.py`

### D-021: "TRUST-SAT" is used as the brand mark; product copy stays "SAT-SA" for now
- Date / phase / commit: 2026-09-30, Phase 23, `a41e4f8`, `83bb687`
- Context: The owner finalized the name TRUST-SAT. But the UI already uses "TRUST-SAT" for the cryptographic verification feature.
- Decision: The icon and wordmark, nav, hero label and page titles say TRUST-SAT. Body copy ("Sign in to SAT-SA", for example) is unchanged.
- Why: A full rename would make the product name and the verification feature identical. That's an owner decision and remains pending.
- Consequences: Ask before renaming the copy. The suggested option is to rename the feature to "Evidence verification".
- Files: `web/src/components/brand.tsx`, `web/src/app/icon.svg`, `favicon.ico`, `apple-icon.png`, landing components

### D-022: Small favicon sizes use a simplified version of the icon
- Date / phase / commit: 2026-09-30, Phase 23, `a41e4f8`
- Context: At 16 px the chip pins took half the canvas and the shield was illegible.
- Decision: `favicon.ico` holds a 16/32 px version without pins and with a purple edge (still visible on dark tabs), plus the full design at 48 px. `icon.svg` is the full design.
- Why: Readability in a browser tab. The rendered sizes were checked.
- Files: `web/src/app/favicon.ico`, `web/src/app/icon.svg`

### D-023: Rotate the exposed administrator credential: new administrator member, revoke the old credential itself
- Date / phase / commit: 2026-10-01, Phase 23 operations (credential rotation), uncommitted
- Context: The production administrator credential (`satsa/prod/admin-credential`) and the 2026-10-01 demo members' credentials had been shown in a chat transcript (handoff §8). They had to be replaced, the old ones revoked, and the replacement kept only in AWS Secrets Manager.
- Decision: Follow the runbook path, which needs no code change. With the old credential, revoke the four demo members (`DELETE /api/v1/members/{user_id}` in `org_36405d05c62c496f92310146bb6e898d`) and invite a new `satsa_admin` member in the bootstrap organization (`POST /api/v1/members`). Write its credential straight from the API response to `satsa/prod/admin-credential` with `put-secret-value`, and confirm it by comparing what Secrets Manager reads back. Then revoke the old credential with `DELETE /api/v1/session` (raw credential as Bearer), revoke the old membership with the new credential, replace `admin` in `/root/satsa-e2e/credentials.json`, delete the old demo state file, and run `deploy.sh demo` to create a fresh demo organization. All steps ran on the instance through SSM inside the api container, printing status codes only. Old user `usr_2fe9a36d456e465d8fd54701106e16ab`, new user `usr_1642237f1a5d451fb06be303b7059475`.
- Why: The runbook step "revoke the old administrator member" alone is not enough. A membership revoke is per organization, and the old identity remained `satsa_admin` of every organization it created, the demo organizations included. Revoking the credential ends access everywhere, including existing sessions. Evidence from the SSM output: before revocation the old credential got 200 and an old session got 200. After revocation the old credential got 401 on `GET /session`, `POST /session` and the tenant read, the old pre-existing session got 401, and the new credential got 200. Revoked demo members got 403.
- Alternatives considered: Issue a new credential for the same identity by calling `IdentityService.issue_credential` in the container. That keeps the memberships in the old demo organizations, but it is not an existing API or runbook path and it leaves the exposed identity in place. Rejected.
- Consequences: The new administrator is not a member of the earlier demo organizations (2026-09-30, the empty one, 2026-10-01). Their immutable records are kept but can no longer be reached through the UI. `AWSPREVIOUS` in Secrets Manager holds the revoked credential, which is harmless but must not be restored. Copies of the old credential remain in earlier local session transcripts outside the repository. It is revoked. The runbook was corrected.
- Files: `deploy/aws/README.md`, `decisions.md`, `flow.md`, `handoff.md`
- Symptom: The credential was exposed in chat. The runbook's rotation procedure would also have left the old identity able to authenticate and administer the demo organizations.
- Root cause: The runbook described only a membership revoke. Membership is checked per organization (`X-Organization-ID`), while the credential authenticates across all of the identity's organizations.
- Regression test: none. This is an operational procedure. It was verified live by the status checks listed above.

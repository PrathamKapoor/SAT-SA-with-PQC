# Project Handoff

## 1. Current Phase

- **Phase**: 23 — final product convergence, release hardening and demo
  readiness (after Phase 18 live workbench, 19 production runtime, 20
  security hardening, 21 MLOps lifecycle, 22 AWS deployment).
- **Subphase**: operations — rotation of the exposed administrator and demo
  credentials (2026-10-01), after the final operational closure.
- **Objective**: turn the existing system into one coherent, deployed,
  demo-ready product without new architecture; audit and fix what was
  fragile.
- **Overall project**: SAT-SA / TRUST-SAT — a periodic, offline-capable,
  evidence-driven supervisory analytics platform for CSE/SOC assessment
  (SIH 26157, NCIIPC), with signed, hash-chained post-quantum evidence
  (TRUST-SAT, ML-DSA-65), a LangGraph-orchestrated worker, an MLOps
  lifecycle for an advisory review-outcome model, and a Next.js workbench.
- **Rotation status**: **COMPLETE** (D-023), committed in `04fc7e7` (docs only, no code change). Push and CI on the pushed commit are pending.
- **Phase 23 status**: **COMPLETE.** `main` = `b60a051`, deployed to AWS, public
  browser suite 11/11 (twice), CI 10/10 on `main`, `phase23/convergence`
  deleted. Phase 24 has **not** been started and has no defined scope.

## 2. Work Completed

0. **Credential rotation (2026-10-01, D-023)**, run on EC2 through SSM in the
   api container, printing status codes only. With the old administrator credential: the 4
   members of demo org `org_36405d05…898d` were revoked (their credentials now get 403), and a new
   `satsa_admin` member was invited to the bootstrap org (new user
   `usr_1642237f1a5d451fb06be303b7059475`). Its credential went straight to
   `satsa/prod/admin-credential` (AWSCURRENT; confirmed by comparing the read-back).
   The old credential was then revoked with `DELETE /api/v1/session` (raw credential as Bearer),
   and the old membership (`usr_2fe9a36d…16ab`) was revoked. Checks: old → 401 on session, login and tenant read;
   an old session opened before revocation → 401; new → 200. The `admin` field in
   `/root/satsa-e2e/credentials.json` was replaced, the old demo state file was shredded, and
   `deploy.sh demo` created a new demo org (decision recorded, TRUST-SAT
   `verified`). Non-obvious: a membership revoke is per organization, so the
   credential itself had to be revoked; the runbook was corrected.

1. **Release identity = Git commit** (`a626a9b`). Both Dockerfiles take
   `ARG SATSA_RELEASE=unreleased` → `ENV SATSA_RELEASE`; `deploy/aws/publish.sh`
   passes `--build-arg SATSA_RELEASE=$COMMIT`; `GET /health/live` returns
   `{"status":"alive","release":...}` (`satsa/api/__init__.py` `live()`);
   Admin → System page shows API and web release; `deploy.sh status` prints
   `deployed.json`, API release and web release. No semver was invented
   (repo has only `archive/*` tags).
2. **Operator commands** in `deploy/aws/deploy.sh`: `status`, `logs [svc]
   [lines]`, `restart [svc...]`, `demo` (plus existing `deploy`,
   `bootstrap-admin`, `snapshot`, `public-e2e`). API release is probed at
   `http://api:8000` because production refuses Host `127.0.0.1`.
3. **Demo mode** (`scripts/demo_environment.py`, `deploy.sh demo`): creates
   a new org "SAT-SA demo (synthetic data) <UTC time>", members
   analyst/supervisor/auditor/viewer (identities unique per demo — identity
   names are platform-unique, a reset once failed with 409 IDENTITY_EXISTS),
   seeds `docs/demo/submissions` (5 synthetic CSEs) via the real API,
   waits, records one supervisor decision, verifies TRUST-SAT. Re-running =
   reset: previous demo members revoked, **nothing deleted**. State JSON
   (with credentials) at `/root/satsa-demo/state.json` (root-only) on EC2.
4. **Full MLOps demo** (`scripts/demo_mlops.py`): 7 extra monthly periods per
   CSE, synthetic supervisor rule **confirm iff ≥5 signal findings** (every
   synthetic CSE has some signals; "any signal" gave a single class that
   validation correctly rejected), dataset → validate → train → approve
   (supervisor ≠ trainer) → deploy → inference → drift → retraining
   request → v2 train/deploy → rollback. Resumable: 409 on an already-done
   transition is treated as done (`settled()`).
5. **Demo API client** (`scripts/seed_demo_via_api.py`): retries 429 using
   `Retry-After` (refused requests did nothing); `SATSA_DEMO_SUBMISSIONS`
   env overrides the data dir (needed when the script runs from `/tmp`).
6. **Polling fix** (`5ba4bfe`): `AutoRefresh` default 3s → 10s; one open run
   page (≈11 API reads per refresh) consumed most of the 300 reads/min
   per-address limit.
7. **Migration 19** `tenant_read_indexes` (`1d89bc8`): expression index on
   audit org (`json_extract(metadata,'$.organization_id')`, translated for
   PostgreSQL in `postgres_migrations.py` to
   `(metadata::jsonb->>'organization_id')` — must match the query in
   `satsa/api/repository.py audit_events`), plus org indexes for
   `satsa_ml_training_runs`, `satsa_ml_drift_reports`, `satsa_ml_deployments`.
8. **Custom domain** (`758af7e`): site address moved out of EC2 user data
   into SSM parameter `/satsa/<env>/site-address`; `deploy.sh` reads it on
   every deploy; Caddy serves `{$SATSA_SITE_ADDRESS} {$SATSA_SITE_ALIASES}`
   (sslip.io name kept as alias). Live domain **trustsat.mpst.me** (A →
   Elastic IP 16.4.5.15, record owned by a friend of the user).
9. **Graph progress bug** (`cc8f0e6`): `AnalysisExecutionService.get_graph_progress`
   raised `PermissionDeniedError` (HTTP 403 on `POST /api/v1/runs`) when a
   fast worker had written LangGraph's first checkpoint (no scope fields yet).
   Now: no scope fields → `current_stage: "starting"`; any present
   mismatching scope still → 403. Tests added in `tests/test_phase4_langgraph.py`.
10. **Branding**: new icon (`web/src/app/icon.svg`, `favicon.ico` with a
    simplified 16/32 px cut + full 48 px, `apple-icon.png`); `BrandMark`/
    `Wordmark` in `web/src/components/brand.tsx` show "TRUST-SAT"; landing
    nav, hero canvas label (box widened) and page titles renamed. Body copy
    still says "SAT-SA" deliberately (see §5).
11. **E2E robustness** (`web/e2e/workbench.spec.ts`): `open()` helper reloads
    a render that met the shared read limit; dataset build reloads until
    listed; `pageAs` detects the organization picker **by content** (sign-in
    passes through `/workbench` before redirecting) and picks
    `credentials.organization_id`.
12. **Docs**: AWS runbook (`deploy/aws/README.md`) gained version, logs,
    restart, worker recovery, secret rotation, demo, custom domain, instance
    failure; RDS retention corrected to 1 day; stale "not deployed" claims
    fixed in `README.md`, `docs/deployment.md`; AWS restore drill recorded in
    `docs/backup-restore.md`; `docs/SAAS_BACKEND_DISCOVERY.md` marked historical.
13. Minor: `ClassicalProvider` misleading comment fixed; models page shows
    abstentions as `"40 × no deployed model"`.

## 3. Files Changed (92075e8 → b60a051)

| Path | Change / why it matters |
|---|---|
| `Dockerfile`, `web/Dockerfile` | `SATSA_RELEASE` build arg → env |
| `deploy/aws/publish.sh` | passes `SATSA_RELEASE=$COMMIT`; builds from `git archive` of a clean tree |
| `deploy/aws/deploy.sh` | status/logs/restart/demo; SSM site-address + aliases |
| `deploy/aws/satsa.cfn.yaml` | `SiteAddressParameter` (SSM), IAM `ssm:GetParameter`; UserData `Site` is always the sslip name |
| `deploy/caddy/site.caddy`, `deploy/compose.production.yml` | `SATSA_SITE_ALIASES` |
| `deploy/aws/README.md`, `docs/deployment.md`, `docs/backup-restore.md`, `README.md`, `docs/SAAS_BACKEND_DISCOVERY.md` | operator docs, drill record, stale claims |
| `qsmlops/database/migrations.py`, `qsmlops/database/postgres_migrations.py` | migration 19 + PG expression mapping |
| `satsa/api/__init__.py` | `/health/live` release |
| `satsa/analysis/execution.py` | early-checkpoint scope fix |
| `qsmlops/security/crypto/providers/classical.py` | comment only |
| `scripts/demo_environment.py`, `scripts/demo_mlops.py`, `scripts/seed_demo_via_api.py` | demo + MLOps lifecycle tooling |
| `tests/test_phase23_release.py`, `tests/test_phase23_indexes.py`, `tests/test_phase4_langgraph.py` | new regression tests |
| `web/src/components/domain/auto-refresh.tsx`, `workbench/page.tsx`, `review-queue/page.tsx` | 10 s refresh |
| `web/src/app/(app)/workbench/system/page.tsx`, `web/src/lib/api/client.ts` | release display |
| `web/src/app/icon.svg`, `favicon.ico`, `apple-icon.png`, `web/src/components/brand.tsx`, landing `SiteNav.tsx`, `content/site.ts`, `hero/evidenceEngine.ts`, layouts | brand |
| `web/src/app/(app)/workbench/models/page.tsx` | abstention wording |
| `web/e2e/workbench.spec.ts` | resilience for live deployment |

## 4. Current Architecture / State

- **Topology (AWS, stack `satsa-prod`, ap-south-1, account 386859041719)**:
  Caddy (HTTPS, Let's Encrypt) → Next.js `web` → FastAPI `api` (internal
  `api:8000`, never public) ; `worker` (analysis queue + ML job queue,
  LangGraph) ; RDS PostgreSQL 17.11 private, `sslmode=verify-full`; S3 via
  instance role (no static keys, BPA, SSE-KMS, versioning, noncurrent 90 d);
  EBS `/data` mounted at `/data/satsa` (UID 10001) holds signing key
  `keys/satsa_trust_key.json` (0600) and ledgers; CloudWatch log group
  `/satsa/prod`. EC2 `i-0f93ebf08ff6feb71` t3.small, EIP 16.4.5.15, SSM only
  (port 22 closed by SG). Compose: `deploy/compose.production.yml` +
  `deploy/aws/compose.aws.yml` (+ `compose.database.yml` only for CI/single host).
- **Deploy**: from a clean checkout, `bash deploy/aws/publish.sh --stack satsa-prod`
  (builds images, pushes to ECR tagged with the first 12 chars of the commit, uploads bundle to
  `s3://satsa-prod-386859041719-ap-south-1/releases/<commit>/`, runs
  `deploy.sh deploy <commit>` via SSM). On instance:
  `sudo bash /opt/satsa/current/deploy/aws/deploy.sh <cmd>`.
- **Secrets**: Secrets Manager `satsa/prod/admin-credential` (JSON
  `organization_id`, `credential`), RDS-managed master secret,
  optional `satsa/prod/llm-providers` (**does not exist**). Rendered to
  `/etc/satsa/production.env` and worker-only `/etc/satsa/llm.env`.
- **Orgs on prod**: "SAT-SA Demonstration" (`org_0a9dca362c6b4b1ab8bb1b4dad1d1b3f`,
  E2E suite's org, creds `/root/satsa-e2e/credentials.json`); demo org
  2026-09-30 (`org_aa54…6414`, members revoked); an empty org from a failed
  reset; current demo org 2026-10-01 01:13 UTC (`org_36405d05c62c496f92310146bb6e898d`).
- **API**: 71 routes, contract in `docs/API_CONTRACT.md`; per-address limits:
  login 5/min, mutations 30/min, reads 300/min (`SATSA_*_RATE_LIMIT`).
  Session cookie `satsa_api_session` (path `/api/v1`, HttpOnly); web server
  forwards it as Bearer. `DELETE /api/v1/session` with a **raw credential**
  as Bearer revokes the credential itself.
- **DB**: 19 migrations; API refuses to start on an outdated schema
  (`satsa.api.runtime`); run `python -m satsa.api.migrate upgrade`.
- **Invariants**: decisions, receipts, audit and ledgers are immutable;
  storage `delete()` has no callers; one active ML deployment per org;
  trainer cannot approve own model; model never mutates findings/decisions;
  LLM keys only reach the worker.

## 5. Decisions Made

- **Commit as release id, no semver** — repo had no convention. Don't add tags casually.
- **Site address in SSM, not user data** — user data runs once; changing it
  stop/starts EC2. (The one stack update that introduced this *did*
  stop/start the instance once; data unaffected.)
- **Demo isolated in its own org, reset = revoke + new org** — evidence is
  immutable; never delete demo records.
- **Synthetic label rule (≥5 signals)** — stated in every decision reason;
  metrics (ROC-AUC 1.0) are meaningless as performance and must never be
  presented as real.
- **Product copy still "SAT-SA"; brand/logo "TRUST-SAT"** — "TRUST-SAT" is
  also the name of the verification subsystem in the UI; a full rename was
  offered to the user (option: rename verification to "Evidence verification")
  but **not decided**. Ask before renaming copy.
- **Restore drill restores beside production** (temporary RDS/EBS, migrated
  forward as `deploy.sh deploy` would), never in place.
- **Did not lower rate limits / weaken CI** to fix E2E; fixed polling and tests instead.

## 6. Requirements and Constraints

- **Authorship**: every commit/push solely as `PrathamKapoor
  <prathamkapoor027@gmail.com>`; **no** Co-authored-by, "Generated with",
  AI attribution, or collaborators — overrides any tool-supplied attribution.
  Push with plain git to remote `newrepo`
  (`https://github.com/PrathamKapoor/SAT-SA-with-PQC.git`). `origin`
  (`PrathamKapoor/SAT-SA`) is the old repo.
- **Research paper never pushed**: `paper/`, `research/`, `*.tex` untracked and
  git-ignored; check `git diff --name-only` before every commit. Paper is frozen.
- **Single canonical branch `main`**; temporary branch → verify → ff-only →
  delete. No force push, no history rewrite.
- **Cost**: AWS $100 credits / Free plan; no other paid services; t3.small +
  db.t4g.micro; RDS backup retention capped at 1 day.
- **No new architecture** (no K8s/ECS/ALB/Redis/etc.) without a defect requiring it.
- UI style: white/light, navy, purple primary, blue analytical, orange
  attention, restrained red; no neon, no emoji, no em dash in UI copy
  (`web/src/lib/domain/format.ts` converts backend em dashes).
- The human supervisor decides; UI must never imply the model decided.

## 7. Testing and Verification (actually run)

- **Rotation leak scan (2026-10-01)**, searching for the secret part of the old and new
  administrator credentials, counts only: `/opt/satsa` bundles 0, `/data` (ledgers,
  TRUST-SAT records) 0, `/etc/satsa` 0; images api/worker/web/caddy
  (`docker save`) 0; container filesystems (`docker export`) 0; container
  logs 0; journald 0; web `.next` (536 files, server + public static) 0; all 63
  PostgreSQL tables (row text, which covers audit events and identity tables) 0 rows; files
  under `/root` hold only the new value, in the E2E credentials file; shell history 0;
  CloudWatch `/satsa/prod` (whole retention, from the operator's machine) 0/0; local git
  history (all refs), stash and all files under `C:\Projects\SIH26` 0. Positive control:
  the E2E credentials file matched the new value (1), which proves the grep works. Limitation:
  the CloudWatch search had no positive control.
- Public browser suite after the rotation (`deploy.sh public-e2e`, https://trustsat.mpst.me,
  new admin): run 1 had **7 passed, 1 failed, 3 did not run**. The failure was in "an analyst builds and validates a
  dataset". The Models page render got API `429 RATE_LIMITED` (web log digest 450754533:
  every role shares one address, the known per-address read limit) and had nothing to do with the rotation.
  Run 2, unchanged: **11/11 passed** (1.5 m), covering sign-in, the forged organization
  selection, ingest, the run, the supervisor decision with TRUST-SAT verification, abstention, the dataset,
  the admin audit trail, audit refusal for a role without permission, and sign-out session revocation.
- Re-scan after the E2E runs (same targets as above, plus the E2E work directory with traces unzipped): 0
  everywhere except the intended E2E credentials file (control = 1); CloudWatch 0/0; git 0.
  Run 1's failure trace was deleted when run 2 cleared the work directory, before it could be scanned.

- CI (`.github/workflows/ci.yml`, 10 jobs: py3.11/3.13 tests, web lint/
  typecheck/build, dependency audit + Bandit, Docker smoke, Trivy, SaaS
  topology, web E2E, production stack + browser E2E, package integrity):
  **10/10 green** on `b60a051` — branch run 36805481867, `main` run 36832738724.
- Public browser suite on AWS: `deploy.sh public-e2e` → **11/11** twice on
  `b60a051` (1.2 m, 1.7 m).
- Local targeted pytest: `tests/test_phase23_release.py`,
  `test_phase23_indexes.py`, `test_phase4_langgraph.py` (10 passed, sqlite),
  phase22 AWS template/runtime tests (21 passed). PostgreSQL variants skip
  locally (no `SATSA_TEST_POSTGRES_DSN`) and run in CI. The full local suite
  was **not** run this phase (CI ran it).
- On AWS: session revocation direct check (200 → 204 → 401); role matrix
  probe (viewer/analyst/supervisor/auditor/admin as designed); MLOps
  negative checks (403/403/403/409/404/409); secret scan with 3 real secret
  values → 0 hits in bundle, images, logs, DB records; RDS private, SG only
  80/443, S3 anon 403; `http_security_check.py` 0 failures; service restart
  and EC2 reboot fingerprints identical; restore drill (see
  `docs/backup-restore.md`).
- **Unexplained**: one earlier public run 10/11 ("sign-out revokes the
  backend session", 9.1 min). CloudWatch showed no 5xx/429, p95 < 650 ms;
  CPU credits ≈250 (no throttling); artifacts overwritten. Not reproduced.
- **Not verified**: any real external LLM provider call.

## 8. Known Issues / Risks

- Confirmed: `scripts/` research tooling (`airgap_rehearsal.py`,
  `benchmark_scaling.py`, `build_demo_dataset.py`) has 14 ruff findings; not in CI.
- Resolved 2026-10-01: the exposed admin and demo credentials are rotated and revoked (D-023).
  The old values remain in earlier local session transcripts (outside the repo); they are revoked.
- Confirmed: the new administrator is not a member of the earlier demo orgs; their
  records are kept but can't be reached through the UI.
- Confirmed: the EC2 instance role lacks `logs:FilterLogEvents` (the CloudWatch scan
  was run from the operator's machine instead).
- Confirmed: the AWS CLI deployment session currently uses the account root identity; future operational access should be moved to a dedicated IAM Identity Center/role-based identity. No root access keys exist in the repo or were created.
- Confirmed (flaky, not fixed): the dataset test in `web/e2e/workbench.spec.ts` opens Models through a link click, not the `open()` reload helper, so a 429 render fails it. Fix it only if it recurs.
- Confirmed: a `router.refresh()` that hits 429 keeps the stale render with
  no error shown (Next.js behaviour); mitigated by 10 s polling, not fixed.
- Limitations: single instance/AZ (no HA); signing key on EBS (no KMS/HSM);
  Trivy findings accepted in Phase 20; security is smoke-tested, not
  pen-tested; two historical Phase 20 CI failures unclassified; demo/model
  data synthetic; drift needs ≥30 samples (`insufficient_data` so far).
- Possible: AWS CLI session expires every few hours (`aws login`), and the
  user's network (Fortinet TLS interception) intermittently blocks
  `ssm.`/`ec2.ap-south-1.amazonaws.com`; switching to a hotspot fixed it.
  Docker DNS can fail right after a network switch (retry).

## 9. Unfinished Work


- Real LLM provider test: needs user to create `satsa/prod/llm-providers`
  (format in `docs/LLM.md`) and to explain "tokenhabour". Optional.
- GitHub "Deploy to AWS" workflow (`.github/workflows/deploy-aws.yml`) is
  not usable: repo variable `AWS_DEPLOY_ROLE_ARN` and environment `aws-prod`
  don't exist. Offered to user, not requested.
- Copy rename SAT-SA → TRUST-SAT: undecided (§5).
- Optional footer credit "Built by The Unsupervised Suspects": needs the team logo file from the user.

## 10. Next Subphase

No Phase 24 scope exists. Wait for the user's instructions. If asked to
continue operations, first: verify `aws sts get-caller-identity` (region
ap-south-1), `git status` on `main`, `deploy.sh status` shows the
`main` commit. The admin credential was rotated on 2026-10-01 (D-023); repeat the
rotation (runbook "Rotating secrets") whenever a credential is shown anywhere.

## 11. Critical Context

- Worktree: `C:\Projects\SIH26\TRUST-SAT-hosting` (branch `main`). Other
  worktrees (`TRUST-SAT`, `TRUST-SAT-render`) belong to other sessions;
  don't use them to deploy.
- Git-bash on Windows rewrites `/aws/...`, `/satsa/...`, `/dev/sdg` args:
  set `MSYS_NO_PATHCONV=1`. AWS CLI at `C:\Program Files\Amazon\AWSCLIV2`,
  Docker at `C:\Program Files\Docker\Docker\resources\bin` (not on PATH).
  GitHub API token via `git credential fill` (no `gh` installed).
- SSM command parameters have a size limit: upload large scripts in separate calls.
- Stack updates must pass `--tags project=satsa` (else every resource is
  retagged) and must be previewed with a change set; `LatestAmiId` is an
  SSM public parameter re-resolved on update (a new AMI would replace EC2).
- Test suite assumes one address for all roles (rate limits); live admin is
  in several orgs (picker). Don't "fix" by raising limits.
- `docker compose logs` works with the awslogs driver via local cache.

## 12. Agent Instructions

- Repository: `main` = `b60a051`, clean, equal to `newrepo/main`, deployed
  and verified. Only `main` exists remotely.
- Inspect first: `deploy/aws/README.md`, `deploy/aws/deploy.sh`,
  `docs/deployment.md`, `docs/backup-restore.md`, `.github/workflows/ci.yml`.
- Do not rewrite: deploy scripts, migrations (append only), TRUST-SAT/ledger
  code, rate limits, demo isolation model, E2E resilience helpers.
- Preserve: authorship rule, paper exclusion, immutability of evidence,
  human-final-decision framing.
- Next objective: none until the user defines Phase 24. Do not start one automatically.

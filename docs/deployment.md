# SAT-SA Deployment — reproducible offline path

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

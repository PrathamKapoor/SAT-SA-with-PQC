# SAT-SA Phase 1 — Technology baseline

Audit date: 2026-09-05. Repository: `TRUST-SAT`, commit `5995f0dab48819bd6fb2588cf4cc55c86861bf91`. The supplied SIH26157 brief is the requirements baseline; it is not evidence that the repository implements those requirements. All target choices in this document set are proposals, not installed capabilities.

## Inspection scope and method

Initial discovery was read-only: root and hidden-file inventory, Git state, source/configuration/build/deployment files, documentation, tests, scripts and historical provider artifacts. Initial worktree was clean. No `AGENTS.md`, frontend package manifest, browser application, container manifest, CI pipeline or offline distribution was found in the inspected tree. Absence claims refer to this checkout, not external systems.

The checkout contains 113 Python files including tests, 27 `test_*.py` modules, `conftest.py`, 14 existing documents, two provider reports, three environment YAML files, a PowerShell bootstrap script and a Python demo. Runtime source was read by module; test functions/assertions were inventoried using AST inspection with focused full reads of trust, provider, artifact and failure paths. Configuration and documentation claims were checked against callers and implementations. Schema presence was checked separately from actual persistence calls.

| Area | Verified files | Result |
|---|---|---|
| Packaging | [pyproject.toml](../../pyproject.toml), [requirements.txt](../../requirements.txt) | Python package `qsmlops` 0.1.0; setuptools build; lower-bounded, unlocked dependencies |
| Entrypoints | [app.py](../../qsmlops/app.py), [cli.py](../../qsmlops/cli.py), [API](../../qsmlops/api/app.py), [demo](../../demo.py) | Python service container, Click CLI, FastAPI JSON API, terminal MLOps demo |
| Domain | `pipeline/`, `registry/`, `passport/`, `supplychain/` | Model training, registration, deployment, provenance; not periodic SOC assessment |
| Analytics | `ml/`, `scores.py`, `monitoring/` | Regression, drift/statistical checks, MLOps health scores and monitoring |
| Agents | `agents/`, `supervisor/` | Nine deterministic agents, validation, policy, risk aggregation and automated recovery |
| Trust | `crypto/`, `security/crypto/`, `evidence/`, `artifacts/` | Actual PQC providers, optional keystore encryption, PKCS#11 abstraction, passports, chained ledger, content-addressed artifacts |
| Storage/security | `database/`, `security/identity/`, `permissions/`, `audit/`, `policies/` | SQLite platform schemas, model registry storage, identity/permission services; API authorization not enforced |
| Deployment | `configs/`, `scripts/bootstrap_softhsm2.ps1`, `.devtools/softhsm2/README.md` | Environment settings and download bootstrap; no bundled provider DLL or offline installer |
| Documentation | `docs/`, `reports/`, root README | Useful historical design material, but several claims contradict current source |

## Declared and observed versions

Observed versions below are metadata from this machine, not a reproducible supported deployment matrix. No package installation or dependency upgrade was performed.

| Technology | Declared requirement | Observed environment |
|---|---|---|
| Python | >=3.10 | 3.13.14, MSC v.1944, AMD64, Windows Store distribution |
| setuptools | >=68 | 84.0.0 |
| FastAPI | >=0.110 | 0.129.0 |
| Uvicorn | >=0.29 | 0.40.0 |
| Click | >=8.1 | 8.3.1 |
| Pydantic | >=2.0 | 2.12.5 |
| PyYAML | >=6.0 | 6.0.2 |
| NumPy | >=1.24 | 2.5.2 |
| SciPy | >=1.10 | 1.17.1 |
| scikit-learn | >=1.3 | 1.9.0 |
| cryptography | >=42.0 | 49.0.0 |
| kyber-py | >=1.2.0 | 1.2.0 |
| dilithium-py | >=1.4.0 | 1.4.0 |
| python-pkcs11 | >=0.9.0 | 0.9.5; provider DLL absent |
| pytest | >=8.0, development extra | 9.1.1 |
| HTTPX | >=0.27, development extra | 0.28.1 |
| SQLite | Python standard library | 3.50.4 |
| PyTorch | Optional adapter import; not declared | 2.13.0 installed globally |
| TensorFlow | Optional adapter import; not declared | Not installed |
| Frontend/chart library | None | None in repository |

Python, YAML, SQL embedded in Python, Markdown and PowerShell are the relevant languages. Installation instructions use pip; there is no lockfile or verified wheelhouse. Project metadata declares MIT; a standalone license file was not found and release licensing needs reconciliation.

## Execution evidence

The suite was run in a temporary copy to avoid rewriting tracked historical HSM sentinel files. Source, tests, configs, scripts, docs, reports and package metadata were copied; no `.git` or unavailable HSM binary was copied. Command: `python -m pytest tests -q -ra --junitxml=phase1-tests.xml`.

JUnit result: **469 collected executions; 451 passed, 1 failed, 17 skipped; 0 errors; 244.949 seconds**. The invocation inherited quiet options, so the XML was inspected for totals rather than inferring them from progress dots. Temporary evidence: `C:/Users/LENOVO/AppData/Local/Temp/satsa-phase1-904b765914cc4454958114fd2931387d/phase1-tests.xml`; this path is session-local, not a release artifact.

The sole failure is `TestDeterminismAndQuiet.test_boundary_still_clean_after_phase10`, at `tests/test_phase10_adaptive_supervisor.py:246`: subprocess starts Unix `grep`, unavailable on this Windows PATH, raising `FileNotFoundError [WinError 2]`. Source and `Get-Command grep` confirm the missing executable. It is a test portability defect, not demonstrated supervisor malfunction. Phase 1 did not modify it. A future portable source scan must also check subprocess exit status; empty stdout alone can hide a failed scan.

Fifteen A12 and two A13 checks skipped for absent SoftHSM2. Passing mock/backend tests and historical sentinel files do not prove real hardware operation here. No expert SOC validation, production load test, browser E2E, air-gap installation rehearsal or accredited cryptographic certification was performed.

## OS and runtime implications

Default data home is `~/.qsmlops`. Windows-specific SoftHSM bootstrap exists; generic Python/file/SQLite code is mostly portable, but current tests demonstrate that portability is incomplete. Development/testing API binds loopback; production config binds `0.0.0.0`, which is not an air-gap security control. Two SQLite concerns are distinct: the platform database and the legacy model registry. JSON/JSONL and artifact files also contain important state.

Pure local numerical processing and PQC execution provide useful offline foundations. Installation currently resolves packages online; the bootstrap downloads an archive; default FastAPI documentation can require CDN assets. There is no verified zero-egress product. See [deployment architecture](deployment-architecture.md) for the proposed offline bill of materials and acceptance gates.

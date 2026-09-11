# Phase 3 — Verification Record

Run on: phase 3 implementation (commit pending — see `git log`).
Test target: `tests/test_phase3_satsa_ingestion.py` (new, 32 tests).
Full regression: `tests/` (554 passed, 17 skipped, 0 failed).

## Foundation reconciliation (Phase 2.5)

The Phase 2 commit (`ab9320f`) provides the verified foundation:

- `satsa.domain.{entities,evidence,workflow,runs,base}` — domain records with `validate()` and `to_dict()`.
- `satsa.contracts.{worker,orchestration}` — the worker + AnalysisRun contract surface.
- `qsmlops.crypto.hashing` — `digest_document`, `sha3_hex` (used for content digests).
- `qsmlops.database.engine.SQLiteDatabaseEngine.transaction()` — atomic multi-statement writes.
- `qsmlops.database.migrations` — `MigrationRunner.migrate()` applying all migrations including 5/6.

Two pre-Phase-3 corrections were made on top of the foundation:

1. `tests/test_phase10_adaptive_supervisor.py::test_boundary_still_clean_after_phase10` — replaced a `subprocess.run(["grep", …])` call (a Unix-only shell-out) with a pure-Python tree walk. The test was failing on Windows with `FileNotFoundError: [WinError 2]`. Behaviour is identical: it still asserts no `*.py` file under `qsmlops/`, `satsa/`, or `tests/` contains the word `guardrailed`.

2. `satsa/ingest/normalize.py::normalize_category` — added the missing `return res` at the end of the function (it had been silently returning `None`, which would have made the entire ingestion service unusable). One stray comment indentation under the same loop was also tidied.

## Phase 3 work committed

New (untracked) files:

- `satsa/ingest/spec.py` — field specs, severity/criticality/disposition maps.
- `satsa/ingest/readers.py` — `parse_csv_bytes`, `parse_json_bytes` (with JSONL dispatch), `parse_file`, `scan_directory`.
- `satsa/ingest/normalize.py` — `normalize_category` with alias matching, cross-ref resolution, ref-dropping sweep, phantom-pruning.
- `satsa/ingest/service.py` — `IngestionService` (transactional, full report, identical-submission guard, source-record assignment, status derivation).
- `satsa/store/repositories.py` — typed row stores matching migrations 5/6; content digest on every insert.
- `satsa/store/dataset.py` — `CanonicalDataset` + `load_dataset`; per-assessment frozen snapshot.
- `satsa/service.py` — `SatsaService` facade (entity/assessment/submission management + ingestion + scope load).

Modified:

- `qsmlops/database/migrations.py` — added migrations 5 (`satsa_core_tables`) and 6 (`satsa_workflow_tables`) with the schema documented in `docs/phase1/data-architecture.md` plus indexes for the common scope lookups.
- `satsa/__init__.py` — version bumped to `0.2.0-phase3-ingestion`; module docstring updated.

New tests:

- `tests/test_phase3_satsa_ingestion.py` — 32 tests (see `docs/phase3/ingestion.md#tests`).

New docs:

- `docs/phase3/ingestion.md`
- `docs/phase3/verification.md` (this file)

## Result

- Phase 3 test file: 32/32 passed.
- Full regression: 554 passed (was 522), 17 skipped, 0 failed.
- Repository remains runnable; no debug code, no temporary files, no secrets introduced.

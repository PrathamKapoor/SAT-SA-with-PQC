# Phase 24 — Deployment Audit

## Can an operator install it?

**Yes.** The repository is a standard Python project
(`pyproject.toml`, `requirements.txt`, `tests/`). `pip install -e .`
or `pip install -r requirements.txt` resolves the platform's
existing dependencies. The platform's existing `qsmlops`
dependencies (PQC providers, FastAPI, etc.) are reused — SAT-SA
does not introduce any new third-party requirements.

## Can an operator run it offline?

**Yes.** Phase 18 proves the pipeline opens **zero** network
sockets. The only outbound dependency in the entire `satsa/`
tree is `docs/demo/ground-truth.json` which is committed to the
repo.

## Can a CSE submission be imported?

**Yes.** `SatsaService.submit(assessment_id, source)` accepts a
directory path or a `{category: path}` mapping. CSV and JSON
(and JSONL) are supported. The `IngestionResult` returns
per-category summaries including any per-row rejections and
warnings.

## Can an assessment be executed?

**Yes.** `SatsaService.run_analysis(entity_id, assessment_id)` (or
`RunService.run` directly) executes every registered worker
through the orchestrator and persists run + observations + findings
+ jobs in a single transaction. The default worker set is the
nine-worker set assembled across Phases 3–8; custom workers can
be passed in.

## Can findings be inspected?

**Yes.** The UI's finding detail page (`/findings/{id}`) renders
the full rationale, threshold/effect/statistic, confidence, the
evidence rows from the original submission, and the human-review
audit history. The CLI equivalent is
`engine.query_one("SELECT * FROM satsa_findings WHERE id=?", …)`.

## Can evidence be traced?

**Yes.** Every accepted row carries a `SourceRecord` linking it
back to the exact bytes submitted (`file_digest`) and the
canonicalized record (`original_record_digest`). The UI's
`/evidence` page shows every source record; the finding detail
page shows the records attached to a specific finding.

## Can integrity be verified?

**Yes.** `SatsaService.verify_run(run_id, trust_key_dir)`
re-derives each record's live content digest and verifies the
PQC (ML-DSA-65) signature against the platform's trust key. The
UI's `/system` page shows the latest run's verification status.

## Can a human examiner make a decision?

**Yes.** `SatsaService.record_review(...)` (or the UI's form on
the finding detail page) records a decision with one of the five
`REVIEW_ACTIONS`, a free-text reason, and the previous revision
id for an append-only chain. The decision row is bound to the
finding's content digest at decision time.

## Can a report be generated?

**Yes.** `SatsaService.compute_risk(...)` + the
`satsa.analysis.report.render_report(...)` function produce a
self-contained printable HTML report. The UI's `/reports/{id}`
route serves it.

## Can the application recover from common failures?

**Yes.**
* Ingestion is transactional: a parse failure of one file does
  not abort the rest; the report enumerates the file-level
  failures and per-row rejections.
* A worker that crashes produces a `failed` Job and a
  withheld observation; the run's overall status is `partial`
  but other workers' findings are still persisted.
* Re-ingesting the same bytes for the same assessment is rejected
  with a clear `IngestionError` (idempotency guard via
  `file_digests_json`).
* The trust layer is best-effort: a signing failure logs a
  warning and the run is still valid; the supervisor simply does
  not have a receipt to verify.

## Can the demo run without developer intervention?

**Yes.** The overview page's hero CTA — **Load Demonstration
Assessment** — ingests the committed demo dataset, runs the
full analytics on every CSE, and presents the top-risk entity's
risk decomposition. No script, no CLI, no configuration.

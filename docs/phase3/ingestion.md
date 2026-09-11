# Phase 3 — SAT-SA Ingestion

## Goal

Make a periodic CSE evidence submission (CSV or JSON) enter the system
and become **validated canonical SAT-SA evidence**, with full
provenance and the explainability chain anchor in place.

## Scope

- CSV and JSON submission files (arrays of objects *and* JSONL).
- The six SIH input categories: alerts, cases, investigation steps,
  escalations, dispositions, assets.
- Operator-managed entity/assessment/submission records.
- Per-row source records linking every accepted domain record back to
  its exact original bytes.
- A frozen per-scope `CanonicalDataset` view (loaded once per run, given
  to workers, no live DB handle).

Out of scope for Phase 3 (deferred to later phases):

- Analytical workers / detectors.
- UI, API surface, CLI.
- Database / API / database-export adapters (CSV+JSON are the floors).
- Signature verification on submissions.

## Entry point

```python
from satsa.service import SatsaService

service = SatsaService(database)
entity = service.register_entity("CSE-001", sector="defence")
assessment = service.open_assessment(entity.id, period_start, period_end)
result = service.submit(assessment.id, "/path/to/submission/directory")
# or
result = service.submit(assessment.id, {"alerts": "alerts.csv", "cases": "cases.csv", ...})
```

`result` is an `IngestionResult` carrying `status` (accepted /
accepted_with_warnings / partial / rejected), `counts`, the per-category
summaries, and the `snapshot_digest` (a content digest over the entire
ingested payload — the anchor later phases sign).

## Validation

Each row is checked for:

| Issue | Outcome |
|---|---|
| Missing required field (per category spec) | row rejected, reason listed |
| Unparseable timestamp | row rejected, reason listed |
| Empty required timestamp | row rejected, reason listed |
| Unrecognised severity / criticality / disposition | row accepted, value coerced to `unknown`, warning recorded |
| Unknown severity values are **not** silently coerced to a real severity |
| Unresolved mandatory cross-reference (step→case, escalation/disposition→alert or case) | row rejected |
| Unresolved *optional* cross-reference (alert.case_refs) | row accepted, ref dropped, warning recorded |
| Duplicate `native_id` within the same file | second occurrence rejected |
| Duplicate `native_id` already persisted for this scope | row rejected (cannot re-ingest silently) |
| Re-submission of the identical file-digest set | `IngestionError` (a new submission must bring new bytes) |

Rejection reasons are enumerated in `IngestionResult.categories[*].rejections`
*and* persisted in `satsa_submissions.ingest_report_json` for later audit.

## Provenance

Every accepted record gets a `SourceRecord` carrying:

- the exact SHA3-256 of the submitted file (`file_digest`),
- a content-addressed locator (`row N` for CSV, `index N` for JSON, `line N` for JSONL),
- a content digest of the canonicalized original record
  (`original_record_digest`).

The submission row additionally carries:

- `file_digests_json` (filename → file digest),
- `declared_counts_json` (category → row count from the parser),
- `snapshot_digest` (content digest of the entire ingested payload),
- `ingest_report_json` (full report for audit),
- `received_at` and the `ingest_status`.

## Determinism

- `parse_*_bytes` over the same bytes always produces the same
  `file_digest` and per-row `original_digest` (SHA3-256, canonical
  JSON, no timestamp noise).
- `normalize_category` over the same `ParsedFile` and same
  native→internal maps produces the same set of accepted native ids,
  the same warnings, and the same rejection reasons (only the
  auto-generated record ids vary, as designed — see
  `docs/phase1/data-architecture.md`).

## Persistence model

All writes for a submission happen in a single
`engine.transaction()`:

- one `satsa_submissions` row,
- one `satsa_source_records` row per accepted record,
- one row per accepted record in its category table
  (`satsa_alerts`, `satsa_cases`, `satsa_investigation_steps`,
  `satsa_escalations`, `satsa_dispositions`, `satsa_assets`).

A failure mid-transaction rolls everything back: there is no
half-ingested submission.

## Tests

`tests/test_phase3_satsa_ingestion.py` — 32 tests covering:

- valid CSV / JSON / JSONL end-to-end,
- malformed files (whole-file parse failure vs. row rejection),
- missing required fields, invalid timestamps, duplicate native ids,
- identical-submission guard, cross-submission duplicate guard,
- mandatory vs. optional cross-reference resolution,
- severity / criticality mapping with warnings,
- multiple entities and per-scope isolation,
- determinism (parse + normalization decisions),
- provenance (submission row, source records, file digests),
- `SatsaService` entity/assessment validation,
- parser edge cases (JSON wrapper keys, non-array JSON, empty CSV).

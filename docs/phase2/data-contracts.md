# SAT-SA Phase 2 — Data contract foundation (Part I)

Status: **FOUNDATION ONLY** — the canonical in-memory shape for each of the six SIH input categories exists and is validated ([domain-foundation.md](domain-foundation.md) has the full record-by-record detail); no ingestion adapter parses an actual CSV/JSONL file into these shapes yet, and no premature normalization was added beyond what [data-architecture.md](../phase1/data-architecture.md) already specified.

## The six categories, mapped to what exists

| # | SIH category | Canonical record | Required identifiers | Entity/source association |
|---|---|---|---|---|
| 1 | Alert metadata | `satsa.domain.workflow.Alert` | `entity_id`, `assessment_id`, `native_id` | `source_record_ref` field (points to a `SourceRecord`, not yet wired to real bytes) |
| 2 | Case-management records | `satsa.domain.workflow.Case` | `entity_id`, `assessment_id`, `native_id` | same |
| 3 | Investigation workflow data | `satsa.domain.workflow.InvestigationStep` | `case_id` | inherits scope from its parent `Case` |
| 4 | Escalation records | `satsa.domain.workflow.Escalation` | `entity_id`, `assessment_id`, at least one of `alert_id`/`case_id` | same |
| 5 | Disposition/closure information | `satsa.domain.workflow.Disposition` | `entity_id`, `assessment_id`, at least one of `alert_id`/`case_id` | same |
| 6 | Asset/system inventory | `satsa.domain.entities.Asset` | `entity_id`, `native_id` | same |

Every record carries `entity_id` (directly, or transitively through a parent reference for `InvestigationStep`) — this is the contract's core invariant, and it is enforced (not just documented): every `validate()` method checks the identifiers listed above are non-empty, and the domain test suite exercises the negative case for each.

## Validation, missing fields, optional fields — as designed, not aspirational

- **Timestamps**: every time field is a plain `float` (Unix epoch), matching [data-architecture.md](../phase1/data-architecture.md)'s "normalize timestamps to UTC" decision at the contract level; no timezone-object dependency was introduced (avoiding a premature choice among several viable libraries before an actual ingestion adapter needs one).
- **Optional vs. missing**: `Alert.acknowledged_at`/`closed_at`, `Case.closed_at`, `AnalysisRun.model_version`, `Escalation`/`Disposition`'s non-required alert/case reference are all typed `Optional[float | str]` with `None` as the explicit "not yet happened / not provided" value — never a sentinel like `0` or `""`, which is exactly the missing-data trap [data-architecture.md](../phase1/data-architecture.md) warned about ("optional acknowledgment/closure is null, not zero duration").
- **Required fields**: enforced by `validate()`, not by making the dataclass constructor raise on omission — a caller can still construct an incomplete record (e.g. while assembling one field at a time during parsing) and check `validate()` once assembly is done, rather than being forced into a single all-at-once constructor call. This is a deliberate ingestion-ergonomics decision, made now so a future adapter is not fighting the contract's shape.
- **Source provenance**: `Alert`/`Case` carry a `source_record_ref` field pointing at a `SourceRecord` (submission_id, file_digest, locator, original_record_digest) — the mechanism [data-architecture.md](../phase1/data-architecture.md) specifies for "references immutable original bytes." No `SourceRecord` is actually populated from a real file yet; the field exists so a future ingestion adapter has somewhere to put it without a schema change.

## What "avoid over-normalizing prematurely" ruled out

No taxonomy-mapping table (native category/severity -> a fixed internal enum) was built — `Alert.mapped_severity`/`mapped_category` are plain strings with an "unknown" default, not a closed enum, because [data-architecture.md](../phase1/data-architecture.md) is explicit that native-to-mapped taxonomy is a per-adapter, per-CSE concern with its own versioning, not a single global vocabulary Phase 2 can responsibly invent. No coverage/expectation-graph modeling was added for `Asset` beyond a plain `control_applicability` list — the expectation graph itself (what control should apply, and when its absence is a finding) is explicitly analytics-phase work (SIH-NS-06).

## Explicit non-goals, restated from Part I

Every detector this data eventually feeds (SIH-EG-01..06, SIH-NS-01..07) is out of scope for this phase — these contracts exist so a future ingestion/analytics phase has a stable shape to build against, not so Phase 2 can start scoring anything. See [domain-foundation.md](domain-foundation.md) for the full per-record implementation table and [gap-analysis.md](../phase1/gap-analysis.md) GAP-01/GAP-14 for what ingestion parsing itself will require.

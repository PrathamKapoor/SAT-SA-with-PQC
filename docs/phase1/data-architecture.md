# SAT-SA Phase 1 — Data architecture

## Baseline and boundary

Current datasets are numerical ML samples, not SOC evidence. Generic SQLite schema names do not implement this domain. Build a dedicated `satsa.domain` and `satsa.ingestion` bounded context beside the preserved MLOps package. All definitions below are proposed contracts to implement, not claims of existing data.

Accept periodic bounded submissions through an authenticated local operator, not continuous telemetry. Initially support a manifest plus UTF-8 CSV/JSONL records and optional local attachments. Do not require raw logs, packet captures, customer identifiers, passwords or executable models in CSE submissions. Compressed archives are not needed for the first adapter; if added, explicitly bound expanded bytes, member count/depth and reject paths/symlinks. Never deserialize pickle from submitted evidence.

## Canonical model

All primary IDs are opaque strings generated or namespaced by the platform. Every operational row carries `entity_id`, `assessment_id`, `source_record_ref`, `schema_version` and normalized snapshot version. CSE-local IDs are unique only within their declared source namespace. Relations must match entity scope. Store original values alongside normalized values where mappings can change interpretation.

| Record | Essential fields / relationships | Missing-data semantics |
|---|---|---|
| Entity | ID, display pseudonym/name, sector/environment class, assessment cohort attributes, access scope | Unknown cohort dimensions prohibit the relevant comparison |
| Assessment | ID, entity, period start/end, timezone, submission cutoff, policy version, status, supersedes ID | Half-open period `[start,end)`; late corrections create versions |
| Submission | ID, source organization/system, declared period, file inventory/digests, counts, schema, received time, submitter/receiver signature status | Manifest completeness is a claim to reconcile, not proof |
| Alert | Native ID, created/acknowledged/closed timestamps, native+mapped severity/category, asset refs, case refs, disposition, detector/control refs | Optional acknowledgment/closure is null, not zero duration |
| Case | Native ID, open/close, alert links, owner pseudonym/team, status, closure reason, investigation/remediation refs | No case link can mean not submitted; use completeness claim |
| Investigation step | Case, action type, timestamp/sequence, analyst pseudonym, evidence/result refs, note text where permitted | A note length or checkbox alone does not prove investigation |
| Escalation | Alert/case, time, destination role/team, trigger, outcome, policy exception refs | Absence is interpretable only with expected policy and complete coverage |
| Disposition/closure | Alert/case, mapped category, reason, time, approver role, exception, supporting refs | Preserve benign/duplicate/test/suppressed classifications and uncertainty |
| Asset/system | Native ID, pseudonym, criticality, environment, active intervals, control applicability | Optional inventory; no inventory means coverage usually unassessed |
| Coverage summary | Asset/control/category, period, expected coverage source, enabled interval, available aggregate telemetry/heartbeat counts, collection gaps | Extra periodic metadata, not a telemetry stream; missing count is not zero |
| Remediation | Case/asset, action, completed/planned time, verification evidence, affected recurrence family | Missing evidence is not proof remediation did not occur |
| Expectation/policy | Scope, effective interval, escalation SLA, applicable categories/controls, exceptions, owner and version | Operator/CSE supplied and reviewable; never infer universal SLAs |
| Source record | File digest, format, row index or JSON pointer, original record digest, normalized row IDs | References immutable original bytes; display safe escaped content |
| Quality issue | Rule/code, field/record refs, count, severity, affected detectors, disposition | Separate rejection, warning and insufficient evidence |
| Analytical run | Snapshot/baseline/config/code/model digests, seed, detector versions, start/end, status, resource metrics | Rerun creates new ID; never overwrite prior findings |
| Signal/finding | Stable ID, rule/category, scoped subjects, rationale, statistic/effect/threshold, confidence vector, evidence refs, limitations | `not_applicable`, `insufficient_data`, `no_signal`, `signal`, `error` distinct |
| Review decision | Finding version, authenticated principal, action, reason, time, previous revision, signature/ledger ref | Append-only decisions; correction supersedes, not edits history |

## Ingestion transaction and quality gates

1. Reserve submission ID and enforce user/entity authorization, file count/size/resource limits and allowed type. Stream bytes into a quarantine area, calculate digest; preserve receipt and source-signature status.
2. Parse with bounded resource use. Reject path traversal, encoding failure, duplicate headers, malformed records, unsupported schema and impossible IDs. Escape active HTML in all displays; neutralize spreadsheet formula injection on exports.
3. Reconcile manifest counts/digests. Validate timestamps, timezone offsets, relations, asset active intervals, chronological contradictions and native category mappings. Repeated identical rows are deduplicated by declared identity; conflicting duplicates are quarantined with both originals retained.
4. Produce a preview and machine-readable quality report: accepted/rejected counts, missing tables/fields, unresolved mappings, relation orphans, coverage claims and detectors enabled/disabled. An authorized operator accepts a version; no silent dropping to improve metrics.
5. Normalize into a new immutable snapshot. Commit snapshot metadata + provenance outbox transactionally, then publish after trust acknowledgement. Analysis only reads published snapshots.

Use a schema registry and adapter fixtures; first schema version must define required/optional fields, enums, bounds, timestamp precision, null representation and error codes. A corrected submission supersedes rather than mutates an assessed snapshot. Events spanning periods are linked: opened-before-period cases can still contribute work during the period; closed-after-period cases are censored for closure-time analysis, not counted as instantaneous or missing.

## Evidence completeness model

Completeness is multidimensional: declared-file receipt; row reconciliation; required-field population; temporal coverage; relational linkage; expected assets/categories represented; and known missing source systems. Report numerators/denominators and provenance for each. Do not collapse unknown expected population into a percentage.

Detector eligibility is a contract: required tables/fields, minimum comparability, valid time coverage, denominator definition and accepted quality issues. Each detector emits an explicit reason when ineligible. “Critical asset has no telemetry” requires inventory + applicable expectation + valid periodic telemetry-count/coverage summary. Alert metadata alone supports only “no submitted alerts for this asset,” not “no telemetry.” This distinction is a mandatory negative-space test.

## Storage, isolation and retention

Proposed initial deployment: SQLite for a single local installation with bounded workers, immutable CAS for original/derived bytes, and one provenance writer. Use foreign keys, entity-scoped compound indexes, transaction migrations, unique idempotency keys and explicit record states. Put tenant scope into repository method arguments and query predicates; UI filtering is not access control. Cross-CSE analytics consumes only authorized de-identified aggregates and returns suppressed cohorts when privacy/size criteria fail.

Normalize timestamps to UTC while retaining source offset/timezone and precision; store durations as integer units, confidence as typed bounded values and rates with denominator. Keep deterministic serialization separate from display rounding. Preserve source-to-normalized field mapping and taxonomy version so an auditor can reproduce a derived value.

Retention periods, classification, legal hold, approved removable media and backup locations are not provided. Production must refuse an unspecified retention configuration rather than invent policy. Retention deletion is an approved, audited operation recording digests and tombstones; it must not rewrite ledger history or claim deleted content is still independently inspectable. Cryptographic erasure and encrypted backups require separately managed keys. Data-at-rest encryption is a required deployment control, not a current feature established by the generic AES service.

## Contract acceptance examples

Tests must include identical native IDs in two CSEs; mixed timezones; missing inventory; legitimate zero activity; truncated files; duplicate contradictory case closures; unresolved escalation refs; an alert linked to multiple cases; closure outside period; late corrections; decommissioned assets; maintenance windows; and a source digest mismatch. Expected outcome for missing telemetry counts is `insufficient_data`, never an automatic coverage finding.

Volume limits are configurable and benchmarked before production. No actual CSE schema/sample or NCIIPC classification policy was supplied; adapter field mappings and retention remain explicit approval gates, not hidden assumptions.

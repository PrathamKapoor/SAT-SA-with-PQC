# SAT-SA Phase 2 — Evidence and provenance persistence

Status: **IMPLEMENTED** (durable insert/read path for observations, findings, supervisor decisions, provenance edges; transactional multi-row writes; digest-based tamper detection) / **NOT IMPLEMENTED** (cryptographic signing of these records, ledger commitment, external checkpoint anchoring — all correctly scoped in [quantum-trust-audit.md](../phase1/quantum-trust-audit.md) as later-phase "provenance writer" work, not restated here as done).

## E1 — Re-tracing the schema-to-application gap

Re-verified directly against current source (not assumed from Phase 1's write-up): `qsmlops/database/migrations.py` defines `observations`, `findings`, `supervisor_decisions`, `security_evidence`, `provenance_edges` (plus `recovery_actions`) with real indexes. Before this phase, `qsmlops/database/repositories.py` contained exactly two repository classes: `AuditEventRepository` and `IdentityRepository`. Grep confirmed no other class existed. These five tables were schema with no application behind them — a fact worth stating precisely, because the column shapes turned out to already match the platform's real in-memory objects almost exactly:

- `observations` columns (`observation_id, agent, subject_id, recommendation, notes, max_severity, mean_confidence, created_at`) map field-for-field onto `qsmlops.agents.base.Observation.to_dict()`.
- `findings` columns map field-for-field onto `qsmlops.agents.base.Finding.to_dict()`, plus the linking columns (`observation_id, agent, subject_id`).
- `supervisor_decisions` columns map field-for-field onto `qsmlops.supervisor.decisions.DecisionReport.to_dict()`, plus caller-supplied context (`model_name, packet_id, action_success, verified, detail`).

This strongly suggests the tables were designed with these exact objects in mind and the persistence step was simply never written — not that the schema is wrong for the domain.

One gap: `Finding` had no stable identifier of its own (only `Observation` had `observation_id`). Added `Finding.finding_id` (a `uuid4().hex` default, mirroring `Observation.observation_id` exactly) so a `provenance_edges` row can reference a specific finding. `to_dict()`/`from_dict()` were updated to round-trip it; `from_dict()` mints a fresh one only when the field is absent (pre-Phase-2 serialized findings never had one — there is no existing persisted data to preserve identity for, since these tables had zero rows before this phase).

`recovery_actions` and `security_evidence` were found to be equally orphaned during this trace but are not in Part E's explicit list (Observations/Findings/Supervisory decisions/Provenance edges) and were left as **FUTURE PHASE** — noted here rather than silently ignored, tracked as an extension of GAP-13 in [gap-analysis.md](../phase1/gap-analysis.md).

## E2 — The interfaces built

Four new repository classes in `qsmlops/database/repositories.py` (`ObservationRepository`, `FindingRepository`, `SupervisorDecisionRepository`, `ProvenanceEdgeRepository`), following the exact construction/error-handling pattern already established by `AuditEventRepository`/`IdentityRepository` — no new abstraction layer was introduced (Part E2's explicit instruction). A single `qsmlops/database/evidence_store.py::EvidenceStore` wraps all four behind two write operations (`persist_observation`, `persist_decision`) and read/verification operations, mirroring how `AuditService` already wraps ledger + database mirror writes. `EvidenceStore` is registered in `ServiceContainer` (`core/context.py`) as `"evidence_store"` and eagerly built during `initialize()`, alongside `audit_service`.

Deliberately **not done**: no automatic wiring into every `pipeline.evaluate_version()`/`health_check()` call. Part E is explicit that "Phase 2 does NOT need the final SAT-SA analytics; it does need the storage/trust path required for those analytics" — wiring persistence into the pipeline's control flow on every call would be exactly the kind of premature, larger-blast-radius change Rule 3 warns against (it would touch behavior exercised by most of the existing 450+ test suite for no functional gain in this phase). Instead, the store is available and proven against real pipeline-produced objects (below); a future analytics phase decides when and what to persist.

## E3 — Connected to actual operations, not just built standalone

Every test in `tests/test_phase2_evidence_persistence.py` uses **real** objects: a real `SelfHealingMLOps` pipeline trains and registers an actual model, `pipeline.evaluate_version()` runs the actual nine agents and returns actual observation/finding data, which is rebuilt into real `Observation`/`Finding` instances (the same `_rebuild()` pattern `qsmlops/api/app.py` already uses) and persisted. A real `pipeline.supervisor.reason(version_id)` call produces an actual `DecisionReport`, persisted and linked via a provenance edge back to the observation it was based on. This is the "Evidence -> Observation -> Finding -> Decision" lifecycle Part E3 asks for, exercised end to end against the platform's genuine behavior — not a hand-built fixture standing in for it.

## E4 — What "integrity" means here, precisely

Each persisted row carries a `content_digest` (SHA3-256 over the object's own canonical `to_dict()`, via the existing `crypto.hashing.digest_document` — the same primitive the model-passport signing path uses). `EvidenceStore.verify_observation_integrity()` recomputes the digest from the stored row and its findings and compares. This **does** detect an in-place row edit made after persistence (verified by test: a raw `UPDATE observations SET ...` is caught). This **does not**: prove the row was genuinely written by the agent it claims (no signature — the digest is unsigned, computed and checked by the same code, not an independent verifier); protect against an edit to *all* the fields the digest covers simultaneously with a stored digest recomputed to match (an attacker with direct database write access could recompute and overwrite `content_digest` too — this is tamper-*evidence* against accidental/partial modification and modification through any path other than direct row+digest rewrite, not tamper-*proofness* against a fully privileged database attacker); or provide any ledger commitment, checkpoint, or timestamp authority. Per Rule 7, this phase does not claim more than that. Signed, ledger-committed provenance for these record types is exactly the "provenance writer" extension [quantum-trust-audit.md](../phase1/quantum-trust-audit.md) scoped as later-phase work (SAT-TR-03), and remains **FUTURE PHASE**.

## E4/E5 — Transactional writes (a necessary building block, added here)

Tracing `qsmlops/database/engine.py::SQLiteDatabaseEngine` before writing `EvidenceStore` found `execute()` runs in sqlite3 autocommit mode (`isolation_level=None`) — **every individual statement commits independently**; there was no multi-statement atomicity anywhere in the platform database layer. `persist_observation` writes one observation row, N finding rows, and N provenance-edge rows — without atomicity, a crash or constraint failure partway through would leave a partially-committed observation, which is exactly the kind of "durable evidence" claim this phase must not make falsely.

Added `DatabaseEngine.transaction()` (abstract) / `SQLiteDatabaseEngine.transaction()` (concrete): an explicit `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`-on-exception context manager. This required changing the engine's lock from `threading.Lock` to `threading.RLock`, because code inside a `with engine.transaction():` block calls the public `execute()` method (which itself acquires the same lock) for each statement — a plain `Lock` would deadlock on the second statement. This is a targeted, minimal, and load-bearing fix: `RLock` behaves identically to `Lock` for every existing call site (none of which re-enter the lock on the same thread), and only changes behavior for the new transactional path. Verified by test: `test_persist_observation_rolls_back_on_partial_failure` forces a `finding_id` collision partway through a multi-row persist and confirms **neither** the observation row **nor** the finding that would otherwise have succeeded remains visible afterward — proving rollback, not just asserting it.

## E5 — Test coverage

`tests/test_phase2_evidence_persistence.py` (9 tests): persist/retrieve against real pipeline-produced observations and findings; finding-to-observation provenance linkage; decision persistence linked to its source observation; duplicate observation_id rejected (`DuplicateEntryError`); missing-reference reads return `None`/`[]`, never raise; provenance-edge idempotency (asserting the same edge twice is a no-op); integrity check passes for an untouched row and detects an out-of-band row edit; and the transaction-rollback guarantee above.

## Honest summary for Part P labeling

- Observation/Finding/Decision/ProvenanceEdge persistence: **IMPLEMENTED**.
- Transactional multi-row writes: **IMPLEMENTED** (new engine capability, not previously present at all).
- Content-digest tamper *detection*: **IMPLEMENTED**, with the precise limits stated above.
- Cryptographic signing / ledger commitment of these records: **FUTURE PHASE** (SAT-TR-03, tracked in gap-analysis.md).
- `recovery_actions`/`security_evidence` repositories: **FUTURE PHASE** (found during this trace, not in Part E's explicit scope).
- Automatic persistence on every pipeline run: **NOT DONE, DELIBERATELY** (would be premature analytics wiring per Rule 3).

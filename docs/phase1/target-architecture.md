# SAT-SA Phase 1 — Target architecture

This document assembles [existing architecture](existing-architecture.md), [agent architecture](agent-architecture.md), [analytics architecture](analytics-architecture.md), [data architecture](data-architecture.md) and [quantum-trust-audit.md](quantum-trust-audit.md) into one target system. It proposes structure; it does not claim any of this is built. Gaps are tracked in [gap-analysis.md](gap-analysis.md).

## Bounded contexts

SAT-SA is a **new bounded context** (`satsa.*`) that sits beside, and reuses selected primitives from, the existing `qsmlops.*` MLOps package. It does not replace or rename `qsmlops`; the two remain independently testable.

```text
qsmlops.*  (existing, preserved)              satsa.*  (new)
------------------------------------          ------------------------------------
core/ settings, logging, errors        <----  reused directly (SAT-ENG-01, EXISTING)
crypto/ PQC providers, keystore, HSM   <----  hardened, extended with envelope types
evidence/ ledger, packets              <----  hardened, extended with outbox
artifacts/ content-addressed store     <----  reused with verified-read hardening
database/ engine, migrations           <----  engine reused; new satsa.* migrations
security/identity, permissions         <----  wired into satsa API auth (was unused)
agents/base.py contracts               <----  pattern reused for new worker contract
pipeline/, registry/, serving/, ml/,   ----    NOT reused as SAT-SA domain logic;
scores.py, monitoring/, supervisor/            preserved as the legacy MLOps product
                                                (separate tests, separate API surface)
```

## Target system diagram

```text
CSE periodic submission (manifest + CSV/JSONL, local operator upload)
        |
        v
+-------------------+       +----------------------------+
| satsa.ingestion    | ----> | Evidence Object Store       |  (artifacts/store.py, ADAPTed)
| quality gates,     |       | content-addressed, verified |
| schema registry    |       +----------------------------+
+-------------------+                    |
        |                                v
        v                       +------------------+
+-------------------+           | Provenance writer |  (evidence/, crypto/, ADAPTed)
| satsa.domain       | <------- | signed envelopes,  |
| normalized snapshot|          | hash-chained ledger,|
| (immutable, versioned)        | checkpoint export   |
+-------------------+           +------------------+
        |
        v
+-----------------------------------------------------------+
| satsa.analytics — bounded worker orchestration              |
|  Evidence readiness -> {Workflow, Coverage, Comparative,     |
|                          Longitudinal} workers -> Synthesis  |
|  (agents/base.py contracts reused; new detector plugins)     |
+-----------------------------------------------------------+
        |
        v
+-------------------+       +----------------------+
| satsa.risk         | --->  | satsa.review          |
| dimension vector,   |      | lexicographic queue,  |
| confidence vector    |      | human decisions       |
+-------------------+       +----------------------+
        |                            |
        v                            v
+------------------------------------------------+
| satsa.api (versioned, read-mostly) + examiner UI |
| Overview / Entities / Findings / Review Queue /   |
| Analytics / Benchmarks / Evidence / Reports /     |
| System status  (see ui-ux-architecture.md)         |
+------------------------------------------------+
        |
        v
Signed supervisory report (satsa.reporting) -> Evidence Ledger commitment
```

Every arrow that crosses a trust boundary (ingestion -> snapshot, snapshot -> analytical run, run -> finding, finding -> human decision, decision -> report) is a signed, ledger-committed stage per the lifecycle in [quantum-trust-audit.md](quantum-trust-audit.md) Part H. Arrows within `satsa.analytics` (worker -> synthesis) are typed in-process data, not independently signed per-worker — only published stages are signed, to keep signature cost bounded (see performance note in quantum-trust-audit.md).

## Layering and dependency direction

1. **Foundation** (`core/`, `crypto/`, `evidence/`, `artifacts/`, `database/engine.py`) — reused, hardened, no SAT-SA-specific knowledge.
2. **Domain** (`satsa.domain`) — canonical CSE records (entity, assessment, alert, case, escalation, ...), independent of analytics or UI.
3. **Ingestion** (`satsa.ingestion`) — depends on domain + foundation; produces immutable snapshots.
4. **Analytics** (`satsa.analytics`) — depends on domain snapshots + foundation trust services; produces typed observations. Detectors never call the foundation's signing/mutation APIs directly — only the orchestration/trust boundary publishes.
5. **Risk & review** (`satsa.risk`, `satsa.review`) — depends on analytics output only, never on raw snapshots. This keeps the risk model auditable from stored facts alone (see analytics-architecture.md's "reconstruct any ranking" acceptance criterion).
6. **API & reporting** (`satsa.api`, `satsa.reporting`) — depends on risk/review, never mutates domain state except through recorded review decisions.
7. **UI** — depends only on the versioned API, never on internal modules directly.

This direction is enforced structurally (module boundaries), not just by convention, because the existing codebase already shows what happens without it: `api/app.py` currently mixes read routes with side-effecting evaluation calls (confirmed in existing-architecture.md), which SAT-SA's API layer must not repeat.

## Trust boundaries (target state)

| Boundary | Current state | Target state |
|---|---|---|
| API caller identity | Unauthenticated free-text `actor`/`approver` fields (GAP-07) | Authenticated principal required for every mutating route (review decisions, submission acceptance) |
| Worker capability | N/A (workers do not yet exist) | Workers receive read-only scoped snapshots; only orchestration/trust services hold signing secrets or database write handles (SAT-AG-01) |
| Cross-entity isolation | N/A | Every repository call is scoped by `entity_id`/`assessment_id` in method arguments, not filtered later in the UI (data-architecture.md storage section) |
| Evidence integrity | Local hash chain only, no external anchor (GAP-11) | Signed checkpoints exported to independent custody |
| Data at rest | Generic AES service exists but is not wired as default encryption (quantum-trust-audit.md) | Explicit deployment control, not an assumed default |

## What is deliberately NOT part of the target architecture

Per Part U of the brief and the out-of-scope requirements (SIH-OOS-01..06): no streaming ingestion endpoint, no cross-CSE shared case queue, no chatbot/general-purpose LLM integration, no cloud dependency, no always-on collection agent. The target architecture has no component that would require any of these — this is a structural safeguard, not just a policy statement, because the ingestion API only accepts closed periodic submissions with a declared cutoff and the analytics layer only runs against frozen snapshots (never live data).

## Relationship to the legacy MLOps product

`qsmlops`'s nine agents, supervisor, registry and serving stack remain a complete, separately tested product (451/1/17 test result, [technology-baseline.md](technology-baseline.md)) for **model** lifecycle trust, not CSE supervisory analytics. SAT-SA reuses its foundation layer and its architectural patterns (typed evidence/finding contracts, validated aggregation, signed passports) but does not repurpose its domain logic. Where the brief's Part B2/B3 asked "does this map to an SIH requirement," the honest answer for the nine agents and the supervisor's decision engine is: **no direct mapping** — their value to SAT-SA is as a proof that this team can build trustworthy, tested, explainable automated decision systems, which is the pattern SAT-SA's new synthesis coordinator follows.

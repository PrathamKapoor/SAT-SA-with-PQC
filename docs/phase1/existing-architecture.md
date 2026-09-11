# SAT-SA Phase 1 — Existing architecture

Scope and execution evidence: [technology baseline](technology-baseline.md). This document describes current code, not the desired SAT-SA architecture.

## Actual application and data flow

```text
Click CLI / demo.py                 FastAPI API
        |                              |
        |                         ServiceContainer
        +------------+-----------------+
                     v
             SelfHealingMLOps
      +--------------+---------------------+
      |              |                     |
 Dataset/training  ModelRegistry      Nine agents -> Supervisor
      |              |                     |             |
 serialized model  SQLite model DB    observations     policy/actions
      |              |                                   |
 ArtifactStore <- BOM + signed passport          retrain/rotate/quarantine/
      |              |                         deployment/rollback flows
      +---------- EvidenceLedger JSONL ------------------+

Parallel foundation: settings/context/logging; platform SQLite;
identity, permissions, audit and generic crypto services.
```

The dependency root is [SelfHealingMLOps](../../qsmlops/pipeline/selfheal.py). [ServiceContainer](../../qsmlops/app.py) lazily obtains key services from that pipeline, rather than the pipeline receiving all independent services. The CLI constructs the pipeline directly. Therefore documentation that every entrypoint uses the container is inaccurate. The diagram uses plain text so it remains readable without a hosted diagram renderer.

Training accepts numeric feature/label datasets through [training.py](../../qsmlops/pipeline/training.py) and [adapters.py](../../qsmlops/ml/adapters.py). Registration stores artifacts and a software/data BOM, signs a model passport and inserts model metadata. Evaluation builds mutable context containing registry, keystore and artifacts, executes agents and aggregates a report. Deployment and self-healing can change model state automatically. Monitoring is MLOps performance monitoring, not SOC investigation analytics.

## Module boundaries and reuse decisions

Each row answers current responsibility, SAT-SA usefulness, required change, invariant and new interface. Requirement IDs refer to [traceability](requirements-traceability.md).

| Component | Current responsibility / SAT-SA value | Change / preserve | Proposed interface / requirement |
|---|---|---|---|
| `core/`, `app.py`, `config.py` | Settings, errors, context, logging; useful local foundation | Extract composition from pipeline; preserve explicit configuration/error codes | `AssessmentServices`, validated effective config; SAT-OFF-01, SAT-ENG-01 |
| `artifacts/store.py` | SHA3-addressed bytes; useful immutable source evidence | Validate digest paths, strict reads and crash durability; preserve content addressing | `EvidenceObjectStore.put/get_verified`; SIH-EX-02/03 |
| `passport/passport.py`, `supplychain/bom.py` | Signed model manifest and dependency/data references | Add distinct assessment envelope; preserve old verification and PQC semantics | `SignedAssessmentManifest`; SAT-TR-01 |
| `crypto/`, crypto services | PQC, optional encrypted vault, HSM dispatch | Harden lifecycle/provider security, unify policy; preserve provider abstraction | `Signer`, `Verifier`, `KeyPolicy`; SAT-TR-02/03 |
| `evidence/` | Generic packet CAS and chained event log | Sign domain events, enforce references, durable checkpoint/outbox; preserve ledger history | `ProvenanceWriter`, `VerifyBundle`; SIH-EX-04 |
| `database/` | SQLite schemas and identity/audit repositories | Add CSE assessment repositories/migrations; preserve parameterized queries | Scoped repository ports; SIH-DATA-01..06 |
| `registry/`, `serving/` | Model lifecycle and inference | Keep legacy bounded context; optional approved algorithm/model registry, not CSE registry | `AlgorithmCatalog`; SAT-OFF-02 |
| `ml/drift.py`, `monitoring/` | PSI, KS, metric/prediction drift, windows | Rework statistical assumptions, periodic input; preserve tested math/adapters where correct | `SignalDetector.evaluate(snapshot, baseline)`; SIH-AN-06/07 |
| `agents/base.py`, `supervisor/validation.py` | Evidence, finding, observation contracts; output checks | Add typed source refs, scope, stable IDs, abstention; preserve validation before aggregation | `AnalyticalObservation`; SIH-EX-01..05 |
| Nine agents | MLOps integrity, performance, governance and recovery advice | Reuse infrastructure checks, not names as SOC features | Dedicated analytical workers; SAT-AG-01 |
| `supervisor/`, `scores.py` | Weighted MLOps decisions and automatic actions | Separate non-authoritative supervisory synthesis; preserve legacy tests/API outside SAT-SA | `SynthesisResult`, `ReviewPriority`; SIH-OBJ-01/02 |
| `security/identity`, permissions/audit | Local principal records, role decisions and audit primitives | Authenticate actual callers, enforce scoped authorization everywhere | `AuthenticatedPrincipal`, `ReviewDecision`; SAT-HUM-01 |
| `api/` | JSON platform/model endpoints | Separate versioned SAT-SA API, read-only GETs; preserve backward compatibility intentionally | `/api/v1/assessments`, `/findings`, `/reviews`; SIH-RP-01 |
| `demo.py`, tests | Synthetic MLOps exercise and regression suite | Preserve as legacy tests; new realistic SOC generator and expert validation | Reproducible demo assessment; SAT-DEMO-01 |

## Storage and trust boundaries

Platform migrations define identities, audit, object registry, datasets, experiments/training runs, lineage, deployment events, observations, findings, supervisor decisions, recovery actions, security evidence and provenance edges. **A table is not a completed service.** The audited repositories implement identity/audit operations; searches did not find insertion paths for observations, findings, supervisor decisions or provenance edges. The legacy registry uses its own database and ledger paths.

SQLite engine uses WAL/autocommit and an in-process lock. Migration statements and version insertion are not one explicit atomic migration transaction. A lazy-connect lock path also deserves a targeted regression test: executing on an unconnected engine can reacquire the non-reentrant lock through `connect`; normal repositories connect first. Artifact storage and database transactions do not atomically commit with JSONL ledger writes. These are single-node building blocks, not a proven concurrent durable assessment service.

Trust boundaries requiring correction:

1. API callers supply actor/approver identifiers; the routes do not authenticate them. Local identity/permission classes do not close that boundary by themselves. Creating privileged identities without caller authorization is unacceptable for deployment.
2. Agents receive mutable context and powerful service objects. There is no capability sandbox restricting writes or cross-entity reads.
3. Registry/database metadata and ledger entries can diverge after failure. Integrity checks are partly diagnostic and not consistently enforced before downstream use.
4. Signed model manifests do not make arbitrary model deserialization safe. Non-reference serving paths use pickle, requiring controlled executable-artifact admission.
5. Hashes establish byte integrity relative to a trusted digest, not submission truth, completeness or trustworthy time.

## Confirmed architectural issues and static risks

| Evidence | Finding | Classification / consequence |
|---|---|---|
| `api/app.py`, `api/foundation.py` | Duplicate GET `/health`; verification/agent/compare/validation reads can evaluate or append evidence | Source-confirmed side effects; SAT-SA must separate read and command routes |
| `app.py`, `core/settings.py`, `crypto/agility.py` | Effective pipeline receives home but not all declared crypto settings; strongest suite selected instead | Source-confirmed configuration mismatch; do not display configured value as effective policy |
| `registry/registry.py` | `deploy` obtains validation report without checking eligibility, while deployment service checks it | Static bypass risk for direct callers; targeted regression required before refactoring |
| `registry/registry.py` | Passport/BOM loaders can return raw data after integrity failure | Diagnostic fallback must never supply trusted analytics |
| `serving/service.py` | Cached model lifecycle and passport-to-served-artifact binding need stronger enforcement | Static authorization/provenance risk; not an executed exploit |
| `security/identity/service.py` | Separation-of-duties logic derives owner from split key ID | String convention is not authenticated ownership; hyphenated IDs are fragile |
| `supervisor/learning.py`, supervisor | False-positive count stored but not consumed as claimed by documentation | Do not describe current learning as validated human-feedback adaptation |

## Documentation reconciliation

Existing `ARCHITECTURE.md` and setup material are useful orientation, not proof of enterprise readiness. Some one-line diagrams contain literal escaped newlines and refer to modules not present (`AgentRegistry`, capability/event/workflow abstractions). Setup text marks implemented work as pending and describes declared scikit-learn dependency as optional. Crypto identity examples use role spelling inconsistent with code. Provider reports overstate production readiness and describe a C-backed provider despite the actual pure-Python dependency. Preserve these historical files in Phase 1; add corrective references in a later documentation-only change with explicit historical/current labels.

No frontend or SOC records were found. Consequently there is no usable SAT-SA UI to audit for visual polish, nor existing SOC findings to validate. The meaningful foundation is real trust-aware MLOps engineering; SAT-SA needs a new supervisory bounded context, not renaming its models and agents.

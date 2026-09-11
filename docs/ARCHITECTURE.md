# Architecture: Quantum-Secure Agentic MLOps Pipeline Management System

## Scope

This platform is an enterprise-grade intelligent MLOps operating system with
quantum-safe cryptography, model trust management, agentic verification, and
self-healing operations. It is **not** an AI-workforce orchestration system,
multi-model router, or coding-agent manager.

Phases:

| Phase | Content |
|---|---|
| **Phase 1 (this document)** | Foundation: settings/logging/DI, TrustedObject base, identity + permissions, audit architecture, database abstraction, security service interfaces, foundation API |
| Phase 2 | Quantum security layer (PQC key lifecycle hardening), serving gates, model trust framework, artifact integrity hardening, dashboard |
| Phase 3 | Agentic intelligence layer with governed tool access, adaptive supervisor learning, control center |

## Governance contract (non-negotiable)

Every mutation the platform performs flows through:

```
Agent Observation
  → Evidence Generation
  → Supervisor Evaluation
  → Policy Validation
  → Approved Action
  → Execution
  → Verification
```

Agents never act. They observe, produce structured evidence, and recommend.
The supervisor evaluates the evidence, the policy engine gates the decision,
the registry/ledger record the action and its verification packets.

## Module map

```
qsmlops/
├── app.py                  # application entry point + composition root (build_app/main)
├── cli.py                  # operational CLI (train/verify/deploy/health/status)
├── config.py               # PlatformConfig paths + supervisor weights (legacy compat)
├── scores.py               # security/trust scoring
├── core/                   # PART-1 FOUNDATION
│   ├── settings.py         # typed settings, env profiles (dev/test/prod), env-var overrides
│   ├── logging.py          # structured JSON / human logging
│   ├── errors.py           # platform error hierarchy with stable codes
│   ├── context.py          # ServiceContainer (composition root, lazy singletons)
│   └── trusted_object.py   # base trust abstraction (id/owner/version/hash/signature/status)
├── security/               # PART-1 FOUNDATION
│   ├── identity/           # Identity (TrustedObject) + IdentityService
│   ├── permissions/        # capability vocabulary + built-in roles (least privilege)
│   ├── crypto/             # Encryption/Signature/Integrity/KeyManagement service contracts
│   ├── policies/           # governance policy extension point
│   └── audit/              # AuditEvent model + AuditService (ledger-backed)
├── database/               # PART-1 FOUNDATION
│   ├── engine.py           # DatabaseEngine abstraction (SQLite impl; dialect-neutral URL)
│   ├── migrations.py       # ordered idempotent schema migrations + bookkeeping
│   ├── repositories.py     # repository pattern (identities, audit mirror)
│   └── service.py          # DatabaseService (engine + migrations + repositories)
├── crypto/                 # existing PQC primitives
│   ├── providers.py        # ML-DSA 44/65/87 + ML-KEM 512/768/1024 provider registry
│   ├── hashing.py          # SHA3-256 + canonical JSON digests
│   ├── keys.py             # versioned keystore with rotation/expiry
│   ├── agility.py          # cipher-suite registry + migration planning
│   └── secure_keystore.py  # AES-256-GCM encrypted vault (Phase 2)
├── evidence/               # immutable evidence layer
│   ├── ledger.py           # append-only hash-chained ledger (authoritative store)
│   └── packet.py           # VerificationPacket (tamper-evident decision records)
├── artifacts/              # content-addressed artifact store
├── passport/               # cryptographically signed model passports
├── supplychain/            # QML-BOM (bill of materials)
├── registry/               # model registry + trust lifecycle state machine
├── pipeline/               # self-healing lifecycle orchestrator
├── ml/                     # drift detection + framework adapters
├── serving/                # model serving (Phase 2)
├── supervisor/             # adaptive supervisor + declarative policy engine
├── agents/                 # observation agents (data/perf/security/quantum/redteam)
└── api/
    ├── foundation.py       # PART-1 foundation endpoints
    └── app.py              # dashboard routes
```

## Key architectural decisions

### 1. Ledger is the source of truth; the database is an index
The evidence ledger is an append-only hash chain: any retroactive edit breaks
verification. The platform SQLite database mirrors audit rows and stores
identity records to enable cheap queries — it is never trusted over the
ledger, and mirrors are rebuilt from the chain when they diverge.

### 2. TrustedObject as the universal trust vocabulary
Every governed object (identities today; models, artifacts, passports, BOMs
in later phases) carries: `id, object_type, owner, version, created_at,
updated_at, hash, signature, verification_status, metadata`. Signing and
verification status are separate from existence — an object is only trusted
when `verify()` succeeds against a trust anchor.

### 3. Least-privilege identity and permission model
Human/service/agent identities resolve permissions through named roles plus
explicit grants. Agents are never granted mutation permissions by built-in
roles; `agent.act` exists but is intentionally never granted in Phase 1.
Agent autonomy arrives only through the governed pipeline (observation →
evidence → supervisor → policy → approved action).

### 4. Interface-first security services
`EncryptionService`, `SignatureService`, `IntegrityService` and
`KeyManagementService` are abstract contracts. Phase 1 implementations wrap
AES-GCM, ML-DSA providers, SHA3 hashing, and the existing KeyStore. Later
phases swap implementations (hybrid PQC, HSM-backed KMS) without touching
call sites.

### 5. Dialect-neutral database abstraction
The engine speaks a `sqlite:///<path>` URL today. The interface is the
extension point for the production quantum-safe database (encrypted storage,
integrity-checked channels). Migrations are plain versioned SQL applied
through the engine.

### 6. Single composition root
`ServiceContainer` owns all singletons (pipeline, ledger, registry, database,
identity service, audit service, logging). The API app, CLI, and tests resolve
services through it, preventing state duplication (e.g. two SQLite WAL
connections to the registry file).

## Extension points for later phases

| Future capability | Extension point |
|---|---|
| Quantum security hardening | `qsmlops/crypto/*` providers + `security/crypto` service contracts |
| Model trust framework | `TrustedObject` subclasses for models/passports/BOMs + registries |
| Quantum ML database | `DatabaseEngine` implementation swap behind `create_engine()` |
| Agentic tool access | role grants in `security/permissions` + supervisor policy rules |
| Self-healing operations | agent + supervisor hooks in `pipeline/selfheal.py` |
| Control center UI | existing dashboard API + `/status`, `/audit`, `/identity` |

## Failure modes and hardening posture

- Expired/revoked keys fail closed (both sign and verify).
- Unsigned passports are rejected at registration.
- Deployment gates require APPROVED state + an approving verification packet.
- Separation of duties: the verifier cannot equal the signer.
- Audit denial events (`DENIED`) are first-class records.

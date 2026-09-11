# Quantum Security Architecture

The quantum trust layer protects every AI artifact the platform touches
(datasets, code, models, passports, BOMs, evidence) with post-quantum
cryptography and a tamper-evident audit trail.

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ Agentic layer (agents + supervisor)                          │
│   findings → facts → PolicyEngine → Decision                 │
├──────────────────────────────────────────────────────────────┤
│ Security services (qsmlops/security/)                        │
│   identity · permissions · audit · policies · crypto         │
├──────────────────────────────────────────────────────────────┤
│ Cryptographic primitives (qsmlops/crypto/)                   │
│   ML-KEM-512/768/1024 · ML-DSA-44/65/87 · SHA3-256           │
│   KeyStore / EncryptedKeyStore (AES-256-GCM vault)           │
│   AgilityEngine (suite selection, migration planning)        │
└──────────────────────────────────────────────────────────────┘
```

## Algorithms

| Purpose    | Algorithm | Parameter sets            | Module                       |
|------------|-----------|---------------------------|------------------------------|
| Encryption | ML-KEM (FIPS 203) hybrid with AES-256-GCM | 512 / 768 / 1024 | `crypto/providers.py`, `security/crypto/providers/pqc.py` |
| Signatures | ML-DSA (FIPS 204)         | 44 / 65 / 87     | `crypto/providers.py`       |
| Hashing    | SHA3-256 (FIPS 202)       | —                | `crypto/hashing.py`          |

Hashing is deliberately *not* replaced during the PQC transition; standardized
hashes remain the correct primitive.

## Provider abstraction

Two abstractions coexist by design:

* **Primitive providers** (`qsmlops/crypto/providers.py`) — algorithm-level
  `SignatureProvider` and `KEMProvider` classes resolved from string ids via
  `SIGNATURE_PROVIDERS` / `KEM_PROVIDERS`. This is the cryptographic-agility
  extension point.
* **Service providers** (`qsmlops/security/crypto/providers/`) — the
  `CryptoProvider` contract (`base.py`) with two implementations:
  - `ClassicalProvider`: reference provider; hashing only, other operations
    are routed through the higher-level services.
  - `PQCProvider`: hybrid ML-KEM+AES-GCM sealing, ML-DSA signatures,
    SHA3-256 digests. Keys are referenced opaquely and resolved through
    configurable resolver callables.

## Enforcement points

1. **Registration** — passport signature over canonical JSON; artifact and
   BOM digests recorded in the registry state machine.
2. **Deployment gate** — registry refuses transitions unless signatures
   verify, verification packets close successfully, and separation of duties
   holds (signer ≠ verifier).
3. **Serving** — `ModelDeploymentService.load` re-verifies the passport
   signature and refuses revoked/expired signing keys.
4. **Runtime** — agents observe, the supervisor's policy engine converts
   facts into decisions (QUARANTINE / ROLLBACK / RETRAIN / ROTATE_KEYS …).

See also: [KEY_MANAGEMENT.md](KEY_MANAGEMENT.md),
[TRUST_MODEL.md](TRUST_MODEL.md), [CRYPTOGRAPHIC_IDENTITY.md](CRYPTOGRAPHIC_IDENTITY.md),
[SECURITY_WORKFLOWS.md](SECURITY_WORKFLOWS.md).

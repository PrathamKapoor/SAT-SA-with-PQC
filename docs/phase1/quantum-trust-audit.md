# SAT-SA Phase 1 — Quantum/post-quantum trust audit

## Executive assessment

The repository executes real ML-DSA signatures and ML-KEM operations through Python libraries. It also implements SHA3 content addressing, signed model passports, evidence packets and a hash-chained ledger. These are valuable foundations and must remain. They do **not** establish a production-secure cryptographic implementation, authenticated SOC submissions, a signed end-to-end assessment history, confidentiality of all stored evidence, trusted timestamps or protection against a privileged full-history rewrite.

ML-DSA and ML-KEM are respectively standardized in [NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final) and [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final). Algorithm standardization is not certification of this application or dependency. The upstream [dilithium-py](https://github.com/GiacomoPope/dilithium-py) and [kyber-py](https://github.com/GiacomoPope/kyber-py) projects describe educational pure-Python implementations, not side-channel-hardened production cryptography. Sources checked 2026-09-05. Production provider selection requires an approved security review; preserving the PQC architecture does not require retaining an unsuitable implementation forever.

Accurate description: **experimental post-quantum signature/KEM integration and cryptographic provenance foundations**. No quantum computer, QKD, blockchain consensus or claim of being “quantum proof” is supported. A chained evidence log need not become a distributed blockchain to serve SIH26157.

## Primitive and implementation inventory

| Source | Current implementation | Limit |
|---|---|---|
| `crypto/providers.py` | ML-DSA-44/65/87; ML-KEM-512/768/1024 dispatch | Pure Python dependency execution, not side-channel certification |
| `crypto/agility.py` | Suite registry/selection; strongest supported suite preferred | Default selection ML-DSA-87 + ML-KEM-1024 differs from declared settings 65/768 |
| `crypto/hashing.py` | SHA3-256; sorted compact JSON, UTF-8, disallows NaN | Application canonicalization, not a demonstrated cross-language canonical JSON standard |
| `passport/passport.py` | ML-DSA signs ASCII hexadecimal SHA3 digest of canonical body | A signed digest message is not automatically the standardized HashML-DSA mode; envelope metadata binding needs strengthening |
| `security/crypto/providers/pqc.py` | Standalone hybrid ML-KEM + AES-256-GCM framing; SHA3-derived symmetric key; version/algorithm AAD | Not wired as default artifact/database/evidence encryption |
| `security/crypto/services.py` | Hash, signing, AES-GCM and KEM facades | Generic encryption key can be ephemeral unless supplied; signing facade assumes software secret and rejects HSM-backed key |
| `security/crypto/providers/classical.py` | Hash support; other operations unsupported | Not an equivalent fallback signer |
| `crypto/keys.py` | Public key records, generation, retirement/revocation/expiry metadata; optional HSM dispatch | Software secrets stored plainly without secure-vault configuration; lifecycle enforcement differs by entrypoint |
| `crypto/secure_keystore.py` | PBKDF2-HMAC-SHA3-256, 600,000 iterations, 32-byte salt; AES-256-GCM, 12-byte nonce, version AAD | Generates plaintext temporary secret file; crash exposure and lifecycle issues below |
| `crypto/hsm.py` | PKCS#11 adapter, capability handling, test backends and failure policies | Hardware/provider support is deployment-specific; ECDSA SoftHSM path does not prove hardware ML-DSA support |

## Key management and trust relationships

`KeyStore` is the local source of public records and secrets. No independently authenticated national/CSE trust-root enrollment workflow exists. Startup does not reliably apply configured key lifetime: pipeline key generation omits it. A key marked active is not sufficient proof that its holder is an authorized examiner or CSE submitter.

Source-confirmed concerns to convert into tests before changes:

| ID | Evidence / failure mode | Required correction |
|---|---|---|
| QT-01 | Secure keystore generation stages the complete secret map in `secret_keys.tmp.json`; finally deletion does not cover power loss | Serialize/encrypt in memory, restrictive atomic encrypted writes, crash and permissions tests |
| QT-02 | `lock()` clears secret cache but retains `_last_passphrase`; Python memory is not assuredly zeroized | Remove unnecessary passphrase retention; document process-memory threat; use approved protected key service for production |
| QT-03 | Secure override `active_signing_key` lacks base expiry check and references unimported `ProviderError` on error paths | One enforced lifecycle policy across software and HSM, explicit typed failures, negative tests |
| QT-04 | HSM direct signing does not enforce all record active/expiry/revocation checks; backend revocation is memory state | Persist revocation and enforce before every signing operation; distinguish historical verification policy |
| QT-05 | Rotation retires old record before successful replacement; file writes lack a full transaction | Stage, prove possession, approve, activate atomically; recover interrupted rotation |
| QT-06 | Suite/algorithm labels outside passport body are not all explicitly bound/checked against key policy | Versioned domain-separated envelope signs schema, algorithm, signer identity and parent references |
| QT-07 | Generic application crypto settings are not propagated consistently | Startup effective-policy validation, provider self-test and fail-closed unsupported policy |

`QT-*` are audit issue identifiers, not duplicate SIH requirement IDs. They map to SAT-TR-02/03/05/06 in traceability. No secret key or passphrase was printed during the audit.

## Provenance, ledger and packaging

The artifact store recomputes digests on reads. Existing-file `put` can skip re-verification; digest-derived path helpers/deletion require validation. Atomic replacement is useful but not equivalent to fsync-backed durability. Model passports bind model/BOM references; the pipeline's `code_digest` is the serialized model digest, not an actual source-tree build digest. Framework markers are not a complete executable dependency SBOM.

`VerificationPacket` accepts proof dictionaries. Persistence validates packet bytes and stores the artifact before the ledger reference, but does not automatically sign packets or validate every proof signer. Tests named for wrong-signer packet behavior verify persistence/round-trip rather than actual signature rejection. A field-name secret scan is not evidence classification or DLP, and direct ledger records bypass that scanner.

`EvidenceLedger` chains sequence, timestamp, previous hash and record hash in JSONL. Verification detects local modification against those links. It cannot detect complete recomputation or tail truncation without an independently trusted checkpoint; an empty ledger verifies as intact. Verification of structurally incomplete but valid JSON needs consistent error handling. In-process locks do not protect multiple processes. Duplicate packet check and append are separated by an unlocked interval. Full-history reads per append create poor scaling. There is no cross-database/file atomic commit or independently trusted timestamp.

## Intended SAT-SA lifecycle

```text
Original bytes -> source digest -> receipt/enrollment status
       -> accepted ingestion manifest -> normalized snapshot manifest
       -> run manifest (code/config/baseline/model/input digests)
       -> analytical signals -> synthesized findings
       -> authenticated human decision -> report manifest
Every arrow records typed parent digests; every published stage has a
signed envelope and ledger commitment; checkpoints leave the writer's domain.
```

The ingestion service signs receipt, not the truth of CSE content. Optional CSE signatures are verified against enrolled public keys; unsigned submissions retain an explicit unsigned-source status and may be accepted only under documented operator policy. Receiver signature must never masquerade as submitter signature.

Proposed envelope fields: schema/version, object type/ID, CSE/assessment/run scope, payload digest, parent digests and relation types, algorithm/suite ID, key ID, signer principal/role, policy version, recorded time and sequence, signature. Canonical representation and domain separation must be frozen with cross-version test vectors. Verify trusted key enrollment, permitted purpose, signature, digest, parent resolution, policy and checkpoint independently. Store the detailed verification outcome, not one green boolean.

Source bytes, normalization mappings, algorithm/model/build versions, detector outputs, synthesis configuration, examiner revisions and exports all need this treatment. Data quality, analytical confidence, signature validity and ledger continuity remain separate dimensions. “Verified” means the specified cryptographic checks passed, never that a finding is factually correct.

## Durable publication and verification

Use a single ledger writer with a transactional SQL outbox. Stage artifact durably; commit domain record + outbox atomically; sign/append idempotently; publish only after durable acknowledgement and resolved evidence closure. Unique event IDs prevent replay duplication. Recovery reconciles pending events and orphans, never silently deletes a ledger discrepancy. A read-only verifier must reconstruct the chain and manifest graph without signing secrets.

Export signed periodic checkpoints containing ledger sequence/head, assessment manifest root, signer/policy and previous checkpoint. Retain copies under independent offline auditor custody or approved immutable storage. This external anchor is necessary to detect rollback/rewrite by an operator controlling ordinary storage. Trusted time remains a deployment decision; sequence and recorded local time must not be represented as independent timestamp authority.

## Migration, performance and offline operation

Keep v1 passport/ledger readers and historical key records; introduce explicit v2 assessment envelopes without relabeling old records as newly authenticated. Migration adds signed links to preserved original bytes. Never silently re-sign old evidence to imply original author approval. Require rollback-tested schema migrations, algorithm deprecation policy, old-key verification and new-key signing rules. Compromise revocation must distinguish new signing prohibition from historical evidence whose trustworthy time may be unknown.

Benchmark hashing throughput, signature/verification latency, bundle size, ledger append growth and full verification at target submission sizes on approved hardware. Do not choose per-row signing without measurement: signed manifests can commit to row-digest collections while preserving drill-down proofs. Cache verification only by immutable digest + trust-policy/checkpoint version; invalidate on key-policy changes.

No Internet is needed for these primitives. Offline operation additionally requires locally distributed approved providers, trust-root/revocation bundles, secure entropy, protected key backup, enrollment/rotation ceremonies and removable-media update controls. HSM outage must block required signatures, not silently downgrade to software/hash-only trust. Software-only demo mode must be visibly distinct from production approval.

## Test evidence and release gates

The baseline suite exercised software PQC and numerous mock/fail-closed paths; 17 real-provider-dependent checks skipped. Historical A12/A13 sentinels were preserved. A report called “certification” is not independent accreditation. No throughput, fault-injection, side-channel or real deployment HSM assurance is established here.

Required tests: known-answer vectors for selected provider; tampered payload/parent/envelope/key ID/suite; wrong signer; expired/revoked/unauthorized signing; unknown trust root; truncation against external checkpoint; duplicate concurrent append; crash at each outbox boundary; partial disk write/full disk; key rotation failure; restore; mixed v1/v2; malformed canonical data; offline verification on a second installation. Production gate: approved provider and key policy, not merely the current 451 passing tests.

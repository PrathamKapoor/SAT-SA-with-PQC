# Trust Model

## Roots of trust

1. **Trust anchors** (`trust_anchors.json`) — public keys registered by the
   KeyStore. Verification always resolves keys through
   `trusted_public_key(key_id)`, which refuses revoked or expired anchors.
2. **Content addressing** — the ArtifactStore addresses bytes by their
   SHA3-256 digest; any modification invalidates the address, so declared
   digests are self-verifying references.

## Chain of trust for a model version

```
trust anchor (signer key)
  └─ signs → passport (canonical JSON, ML-DSA)
       ├─ binds → artifact digest   (model bytes)
       ├─ binds → BOM digest        (QML-BOM: dataset/code/framework/artifact)
       └─ binds → training info + metrics + environment
```

Every hop is verified before use:

* **Registration** — `registry.register` records digests; verification
  packets capture per-agent security checks.
* **Deployment gate** — state machine transitions
  (REGISTERED → VERIFIED → APPROVED → DEPLOYED) require signature validity,
  successful verification and **separation of duties**: the verifier must
  differ from the signer.
* **Serving** — `ModelDeploymentService.load` re-verifies the passport on
  every cold load; revoked signing keys raise `ServingError("revoked")`,
  expired ones `ServingError("expired")`.

## Identity trust

Identities (human / service / agent) are TrustedObjects whose status governs
authorization: only `active` identities may act, and revocation is terminal.
See [CRYPTOGRAPHIC_IDENTITY.md](CRYPTOGRAPHIC_IDENTITY.md).

## Policy as trust enforcement

The declarative policy engine converts observed facts into decisions:
broken trust chains block deployment (gate rules), critical non-drift
findings quarantine, critical drift on an active deployment rolls back.
Rules are data — organization policy sets can be edited and hot-reloaded
without code changes (`qsmlops/security/policies/loader.py`).

## Trust boundaries

* The evidence ledger is append-only and hash-chained; tampering with any
  historical entry breaks chain verification.
* Agent findings are evidence-backed; agent crash is itself recorded as a
  failed finding rather than silently ignored.
* PQC guarantees hold only for artifacts that flow through the enforced
  paths above; out-of-band artifact edits are detectable but not preventable.

## SAT-SA / TRUST-SAT — what it trusts, and the tampering matrix

The legacy offline TRUST-SAT path is `satsa/analysis/trust.py` (`TrustService`) plus the
review-decision binding in `satsa/analysis/review.py`
(`ReviewService.verify_binding`, added phase P20). It is **not** the same
mechanism as the qsmlops model-passport chain documented above — SAT-SA
findings and runs are signed independently, with their own receipts in
`satsa_trust_receipts`.

**What the legacy offline path trusts:**

- The ML-DSA-65 keypair persisted at `<key-dir>/satsa_trust_key.json`
  (file-based; POSIX-chmodded owner-only, Windows ACL-inherited — see
  `docs/KEY_MANAGEMENT.md`).
- The `satsa_trust_receipts` table (signature + algorithm id + public key +
  content digest per subject).
- The SQLite database file as the record of truth for every other
  column TRUST-SAT re-derives a live digest from.

**What it explicitly does NOT trust / does not protect against:**

- An attacker with direct filesystem access to the SQLite database file can
  replace *both* the data and its receipt in one write — TRUST-SAT is
  **tamper-evident**, not tamper-proof. Never call it "immutable."
- The pure-Python ML-DSA implementation (`dilithium-py`) is not
  side-channel hardened; no PKCS#11 hardware token supports ML-DSA
  industry-wide (see `docs/HSM_A11_CERTIFICATION.md`).

**Tampering matrix** (✅ = an existing test proves detection; see the file
named):

| Mutation | Detected? | Proven by |
|---|---|---|
| Finding rationale / threshold / confidence / evidence_refs | ✅ digest mismatch → signature fails | `tests/test_phase44_satsa_trust_stress.py` |
| Finding re-pointed to a different observation_id | ✅ | `tests/test_phase44_satsa_trust_stress.py` |
| Run's stored `content_digest` column | ✅ stored-vs-live mismatch | `tests/test_phase44_satsa_trust_stress.py` (P0 fix) |
| Corrupted / zeroed signature bytes | ✅ | `tests/test_phase44_satsa_trust_stress.py` |
| Deleted trust receipt | ✅ "no trust receipt" | `tests/test_phase44_satsa_trust_stress.py` |
| Inserted (fabricated) finding, never signed | ✅ no receipt exists for it | `tests/test_phase66_satsa_tamper_matrix.py` |
| Review decision's `principal_identity_id` (forged/spoofed identity) | ✅ authentication layer rejects before a decision can even be recorded | `tests/test_phase63_satsa_auth_rbac.py` (P18) |
| Finding tampered **after** a human decision was recorded | ✅ decision's captured digest vs. live digest mismatch | `tests/test_phase66_satsa_tamper_matrix.py` (P20; closes a gap `review.py` documented but nothing checked before this phase) |
| Verification reflects live DB state, not a cached pass/fail | ✅ tamper → fails; restore exact original value → verifies again | `tests/test_phase66_satsa_tamper_matrix.py` |
| Legacy on-demand recommendation (`satsa/analysis/recommend.py`) | ⚠️ not independently signed | Computed on demand from the finding at read time — it inherits the finding's own trust coverage (if the finding verifies, its inputs are trusted) but has no receipt of its own because it is never persisted as an independent claim. Documented limitation, not a bug. |
| Record deletion from `satsa_review_decisions` / reordering | ✅ (P26) — deletion and out-of-band insertion both detected | Every decision recorded via `ReviewService.record()` (when constructed with a `decision_ledger`, wired by default from `SatsaService.record_review(trust_key_dir=...)`) is now also mirrored into its own hash-chained `EvidenceLedger` (the same class the qsmlops identity audit trail already used). `ReviewService.verify_ledger_integrity()` cross-checks the DB table against the ledger in both directions. Still bounded by the filesystem-level limitation on the row directly below — an attacker with full filesystem access could edit the DB and the ledger file consistently. `tests/test_phase80_satsa_review_ledger_integrity.py` |
| Whole-database replacement (attacker swaps the `.db` file wholesale, receipts included) | ⚠️ not detected | Requires an external trust root (e.g. the public key anchored outside the SQLite file, which it already is — `<key-dir>/satsa_trust_key.json` — but nothing currently cross-checks "is this database file itself the one this key's history belongs to"). Documented as a residual limitation, not fabricated as solved. |

## Supervisory finalization (Phase 5)

### Exactly what the receipt proves

A version-1 `supervisory_finalization` receipt signs the UTF-8 lowercase hex
SHA3-256 digest of `supervisory_document()` using existing ML-DSA-65. It binds:

- Organization; run/entity/assessment/submission/version identifiers; frozen
  input snapshot digest; code, analytics and model versions.
- The captured complete review-context digest, and immutable run decision ID,
  organization/run/finding links, authenticated
  user and principal identity, confirm/dismiss/escalate action, reason, captured
  finding digest and exact persisted review timestamp.
- Sorted live digest sets (count plus SHA3-256 commitment) for findings,
  observations, recommendations, canonical input records and artifact metadata;
  the recomputed risk profile and algorithm version.
- Record-to-source-to-artifact relationships, original record/file digests,
  locators and findings' evidence references. Every referenced source record
  must belong to the analyzed version. The input snapshot is reconstructed and
  compared with both run and version snapshot digests.

Verification proves integrity of that recorded representation relative to its
stored public key, signature and shared ledger. It does **not** prove the
real-world evidence was truthful, the analytics were correct, the examiner's
judgment was correct, or a regulatory action occurred outside SAT-SA. Artifact
bytes are not reread by this verifier; their server-generated digest and
persisted provenance are bound. Storage-level byte verification remains a
separate operation. Operational queue status/retry timestamps are excluded:
the receipt proves the decision and evidence state, not that a process stayed
alive or that the final queue commit occurred.

### Canonical representation

The existing `qsmlops.crypto.hashing.canonical_json` is unchanged: sorted object
keys, compact separators, UTF-8 with `ensure_ascii=False`, explicit JSON nulls,
and `allow_nan=False`. Unicode code points are preserved (no normalization).
Identifiers are exact strings. Decision epoch timestamps retain their persisted
Python JSON float representation; no rounding or alternate datetime parsing.
Existing analytical numeric representations are preserved. Collections are
sorted by stable record IDs before digesting. Supervisory structured fields
reject malformed JSON, unexpected types, duplicate object keys and non-finite
numbers. Legacy permissive finding parsing remains unchanged for old receipts. Raw database rows are never
signed: fields and JSON payload reconstruction are explicit. Large payloads
are committed through digest sets rather than copied into receipts/checkpoints.

### Persistence and crash recovery

The same `TrustService.finalize()` is used by graph and supervised non-graph
workers, with mandatory organization context. Finalization identity derives
from organization, run, immutable decision ID and schema version 1. One
terminal decision exists per run; different repeat decisions are rejected.
New decisions atomically capture the full reviewed-context digest; changes
between review and signing are rejected. Historical Phase 4 decisions retain
a null review-context field: they still bind their actual recorded decision and
captured first-finding digest, but cannot prove a full review-time snapshot.
They are not backfilled with fabricated historical evidence commitments.
No amendment overwrites the meaning of an issued receipt. A future amendment
workflow must introduce explicit supersession/versioning.

1. Reconstruct live canonical state; insert `prepared` metadata with a unique
   identity. On retry, require an exact match with the frozen representation.
2. Sign outside any DB transaction. If the process dies here, the unrecorded
   signature is discarded; a retry may sign again without a durable duplicate.
3. Lock the finalization row (PostgreSQL `FOR UPDATE`, SQLite write transaction),
   recheck live state, and insert the existing receipt plus link atomically.
   Competing signers adopt the single recorded receipt, never replace it.
4. Append one deterministic `trust.supervisory_finalized` audit event to the
   existing EvidenceLedger. It binds canonical digest, decision, signing-key
   fingerprint, signature digest and receipt time. The existing DB append lock
   coordinates API/workers (PostgreSQL advisory lock, SQLite transaction).
   Ledger writes flush/fsync. If append survives a DB failure, `record_once()`
   finds and verifies the exact existing event before repairing the DB hash
   link; it never appends a conflicting replacement.
5. Reconstruct and verify live data, receipt signature and complete ledger
   chain/event binding; persist verification time, append a deterministic
   `trust.verification_completed` event, then mark `verified`.
6. The worker rechecks the shared finalizer before queue completion. The queue
   refuses supervised completion without a verified linked finalization.

`trust.finalization_started` records preparation. Repeated finalization creates
no duplicate receipt or lifecycle events. The stored verified state is history;
`verify_finalization()` always performs live checks. A crash after verification
but before queue completion is recovered from the existing lease/checkpoint;
completed workers and finalization do not duplicate durable side effects.
Transient trust filesystem errors follow Phase 3 bounded job retries. Integrity
and configuration errors fail explicitly. Cancellation is cooperative at
finalization boundaries. A receipt already recorded before cancellation still
proves the recorded decision; it never claims the cancelled run completed.

A physically torn/corrupted ledger line fails closed. Automatic truncation or
rewriting of audit history is not attempted; operator-led recovery is required.
The indexed audit mirror remains best effort; the ledger is authoritative.

### Service contract and isolation

Backend-only additions (no frontend contract edits or new HTTP routes):

- `create_run(version_id, idempotency_key=..., review_required=True)` opts a
  non-graph run into supervisory review. `graph_enabled=True` implies review.
  Reusing a key with a different execution/review mode is rejected.
- `decide(run_id, action=..., reason=...)` now supports both supervised modes,
  preserving existing terminal action names and authorized supervisor/admin
  membership checks. The graph consumes the persisted decision only.
- `AnalysisExecutionService.get_trust_receipt(run_id)` requires evidence-read
  permission and tenant ownership, returns receipt/reference metadata,
  base64 public key/signature, digest, key fingerprint, state and ledger hash.
- `verify_trust(run_id)` returns `(ok, reason)` from live verification with the
  same authorization. No raw checkpoint or unscoped receipt IDs are exposed.
- `TrustService(engine, None, organization_id=...)` supports verification without
  loading/generating a private key. Worker signing requires the configured key
  directory. All tenant finalization operations check run ownership themselves.

Existing analysis-only non-graph runs remain compatible and may receive legacy
SQLite run/finding receipts. Those receipts do not prove a supervisory outcome.
No legacy canonical schema is silently changed, and old receipts remain valid.

### Keys and residual risks

Keys remain in the existing external `satsa_trust_key.json`, never in DB rows or
logs. First-use creation publishes a complete fsynced candidate atomically;
concurrent workers adopt the single published key. POSIX permissions are
restricted; Windows relies on inherited ACLs. An algorithm/key mismatch fails
closed instead of overwriting the key. Deployment must provision a protected,
shared durable key directory and shared ledger. The receipt carries its public
key plus a SHA3-256 fingerprint; no HSM/KMS, rotation/revocation or externally
anchored ledger head is added here.

An attacker controlling both database and ledger (or replacing the receipt's
public key and re-signing/rechaining everything) can evade this local integrity
model. It is tamper detection, not absolute tamper-proofness or independently
anchored signer authenticity. Existing model-passport anchor policies above do
not automatically apply to SAT-SA supervisory receipts. Live S3 and hosted
production deployment remain unverified.

Tests: `tests/test_phase5_trust_finalization.py` exercises both SQLite and real
PostgreSQL, graph/non-graph review, concurrent finalizers, live tamper detection,
repeated finalization, worker retry/checkpoint recovery and six interruption
boundaries, malformed finding fields, and cancellation during finalization. Run with `SATSA_TEST_POSTGRES_DSN` configured for real PostgreSQL.

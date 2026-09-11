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

TRUST-SAT is `satsa/analysis/trust.py` (`TrustService`) plus the
review-decision binding in `satsa/analysis/review.py`
(`ReviewService.verify_binding`, added phase P20). It is **not** the same
mechanism as the qsmlops model-passport chain documented above — SAT-SA
findings and runs are signed independently, with their own receipts in
`satsa_trust_receipts`.

**What TRUST-SAT trusts:**

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
| Recommendation (`satsa/analysis/recommend.py`) | ⚠️ not independently signed | Computed on demand from the finding at read time — it inherits the finding's own trust coverage (if the finding verifies, its inputs are trusted) but has no receipt of its own because it is never persisted as an independent claim. Documented limitation, not a bug. |
| Record deletion from `satsa_review_decisions` / reordering | ⚠️ not detected | The review-decision table has no hash-chain of its own (unlike the qsmlops evidence ledger above); a deleted or reordered decision row is currently invisible to verification. Genuine gap for future work — same class of limitation as "tamper-evident, not tamper-proof." |
| Whole-database replacement (attacker swaps the `.db` file wholesale, receipts included) | ⚠️ not detected | Requires an external trust root (e.g. the public key anchored outside the SQLite file, which it already is — `<key-dir>/satsa_trust_key.json` — but nothing currently cross-checks "is this database file itself the one this key's history belongs to"). Documented as a residual limitation, not fabricated as solved. |

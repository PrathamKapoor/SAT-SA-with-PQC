# Phase 11 — Trust / Provenance Integration

## Goal

Make the existing post-quantum crypto layer an *integral* part of
the SAT-SA evidence lifecycle, not a one-off signature bolted on
the side.

## What gets signed

After every completed (or partial) analysis run:

* the `AnalysisRun` row is signed — over the live digest
  recomputed from its post-status-update column state, not just
  the value at insert time;
* every persisted `Finding` is signed — over the digest of its
  live row columns;
* the `satsa_trust_receipts` table holds the `{algorithm_id,
  public_key, content_digest, signature, created_at}` for each
  signed subject;
* the run's `summary_json` records the algorithm, the public key
  (base64) and the number of signed findings, so an auditor can
  see at a glance which key was used without joining another
  table.

## What the trust claim actually is

The signatures use the platform's configured PQC primitive
(default `ML-DSA-65`, the Phase 2 runtime default). A receipt
**detects tampering at verification time**, not tamper-proof
storage. Concretely:

* a finding whose `rationale` was rewritten in the DB after
  signing — detected (`digest mismatch`),
* a finding whose `observation_id` was repointed to a different
  observation (broken provenance chain) — detected,
* a row that was deleted — detected (`no trust receipt`),
* a receipt whose own `signature` was corrupted — detected
  (`signature does not verify`).

A sufficiently motivated attacker with full file-system access
can replace both the data and the receipt; the design does not
claim otherwise.

## Key management

`TrustService` generates a PQC keypair on first use in
`<key_dir>/satsa_trust_key.json` (the secret key is stored
plaintext for the same reason `secure_keystore.py` is
deliberately separate: this is a software keystore, the platform
HSM is the production path). A subsequent `TrustService` in the
same directory reuses the same key, so signatures stay
reproducible across runs on the same host. The
`attest_run_outputs` helper is also exposed as
`RunService.attest_run` for re-signing runs that pre-date the
trust layer (or after a key rotation).

## How to use

```python
from pathlib import Path
from satsa.service import SatsaService

service = SatsaService(database)

# 1. run + sign
key_dir = Path("/var/satsa/keys")
result = service.run_analysis(entity_id, assessment_id, trust_key_dir=key_dir)

# 2. verify
report = service.verify_run(result.run_id, key_dir)
# report = {
#   "run": {"ok": True, "reason": "ok"},
#   "findings": [
#     {"finding_id": "...", "rule": "...", "ok": True,  "reason": "ok"},
#     {"finding_id": "...", "rule": "...", "ok": False, "reason": "digest mismatch: ..."},
#   ]
# }
```

## Tests

`tests/test_phase11_satsa_trust.py` — 16 tests:

* `TrustService` unit: key generation, key reuse, sign + verify
  on a digest, receipt persistence;
* `verify_subject` for valid, digest-mismatch, missing-receipt
  cases;
* end-to-end: a real run produces a run receipt and one
  finding receipt, both verifiable, both carrying the same
  public key;
* tamper tests: rewriting the `rationale` and repointing the
  `observation_id` both produce `digest mismatch`;
* re-signing: `RunService.attest_run` works on a run that was
  completed before the trust layer was available;
* key rotation: a new `TrustService` in a new directory issues
  new signatures; old receipts remain self-verifiable because
  they carry their own algorithm id + public key.

The existing Phase 4 fixtures were updated to reflect the new
`trust_key_dir` optional parameter on `RunService.run` and the
new public-facing `SatsaService.verify_run` method.

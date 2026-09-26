# Phase 5 implementation protocol

Extend `TrustService`, canonical reconstruction, the existing receipt table and
AuditService/EvidenceLedger. No second cryptographic implementation or ledger.

The new `supervisory_finalization` subject has schema version 1. Its identity is
derived from organization, run, immutable decision ID and schema version.
It commits to authoritative decision fields, immutable run context, and sorted
digest references for live findings, observations, risk, recommendations and
versioned input/provenance. Operational run status and retry timestamps are
excluded because queue completion follows verification.

Short transactions persist PREPARED, RECORDED and VERIFIED finalization states.
Signing happens outside the transaction. A unique finalization row and unique
supervisory receipt subject prevent conflicting concurrent writes. A deterministic
audit event ID allows recovery of a ledger append that survived a DB rollback.
Verification always reconstructs live data and checks the signature and chain;
VERIFIED is execution history, never a substitute for verification.

Both graph and explicitly supervised non-graph runs pause for the existing
authorized immutable run decision. The worker uses the same finalizer before
queue completion. Existing non-supervised runs retain analytical completion and
legacy SQLite receipts; these do not prove a supervisory outcome.

Implementation order: failing integration tests; migration and canonical
representation; idempotent audit append and finalization; worker integration;
tamper/recovery/isolation tests; regression and quality checks; documentation.

Keys remain in the existing external key directory. Hosted workers require the
same durable ledger and key configuration. No deployment or key-rotation claim.

New supervisor decisions also capture a digest of the complete reviewed context
inside the decision transaction. Finalization rejects changes after review;
legacy Phase 4 decisions retain an explicit null context marker.

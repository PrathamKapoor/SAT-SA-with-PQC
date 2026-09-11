"""SAT-SA trust / provenance: wire the existing post-quantum
crypto layer into the analysis evidence lifecycle.

What this module does
---------------------

After every completed analysis run:

* every persisted Finding is signed with the configured PQC
  signature algorithm (default ML-DSA-65) over the finding's
  ``content_digest`` (the SHA3-256 of its canonical to_dict()),
* every AnalysisRun is signed over its ``content_digest`` (the
  SHA3-256 of its canonical to_dict()),
* the signature + algorithm id + public key are persisted in the
  ``satsa_trust_receipts`` table alongside the signed subject,
* later, a verifier can re-derive the digest from the live record
  and confirm the signature still matches — detecting any
  tampering with the record (a modified finding, a re-assigned
  observation_id, a different snapshot_digest, etc.).

What this module does NOT do
-----------------------------

* It does not claim "quantum proof" storage. The platform's
  storage is a SQLite file; a sufficiently motivated attacker
  with the file can replace both the data and the receipt. The
  trust claim is **detection of tampering** at verification
  time, not tamper-proofness.
* It does not invent a new PQC primitive. The signatures use
  ``qsmlops.crypto.providers`` exactly as the rest of the
  platform does — the same ML-DSA-65 + ML-KEM-768 configuration
  Phase 2 made the runtime default.
* It does not require an HSM. The default keypair is generated
  in-process and persisted to a local JSON file. A future
  phase can swap this for the platform's HSM-backed keystore
  (see ``keys.py::sign_with_hsm``); the public-facing
  TrustService API is unchanged.
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from qsmlops.crypto.providers import (
    SIGNATURE_PROVIDERS,
    KeyPair,
    SignatureProvider,
)


DEFAULT_ALGORITHM = "ML-DSA-65"
RECEIPT_TYPES = ("run", "finding")


@dataclass(frozen=True)
class TrustReceipt:
    """A PQC signature over one record's content digest. Stored
    alongside the record; verification recomputes the digest from
    the live record and checks the signature against the public
    key. The ``algorithm_id`` lets a future phase rotate the
    algorithm without breaking older receipts."""

    subject_type: str
    subject_id: str
    algorithm_id: str
    public_key: bytes
    content_digest: str
    signature: bytes
    created_at: float

    def to_dict(self) -> dict:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "algorithm_id": self.algorithm_id,
            "public_key_b64": base64.b64encode(self.public_key).decode("ascii"),
            "content_digest": self.content_digest,
            "signature_b64": base64.b64encode(self.signature).decode("ascii"),
            "created_at": self.created_at,
        }


class TrustService:
    """Generates (or loads) a PQC keypair and signs/verifies
    evidence digests. The keypair is persisted to
    ``<key_dir>/satsa_trust_key.json`` so the signatures stay
    reproducible across runs on the same host; rotate the file
    to force a re-sign."""

    def __init__(self, engine, key_dir: Path,
                 algorithm_id: str = DEFAULT_ALGORITHM) -> None:
        self._db = engine
        self._key_dir = Path(key_dir)
        self._key_dir.mkdir(parents=True, exist_ok=True)
        self._algorithm_id = algorithm_id
        self._provider: SignatureProvider = SIGNATURE_PROVIDERS[algorithm_id]
        self._keypair: KeyPair = self._load_or_create_keypair()

    def _load_or_create_keypair(self) -> KeyPair:
        path = self._key_dir / "satsa_trust_key.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("algorithm_id") == self._algorithm_id:
                return KeyPair(
                    algorithm_id=data["algorithm_id"],
                    public_key=base64.b64decode(data["public_key"]),
                    secret_key=base64.b64decode(data["secret_key"]),
                )
            # algorithm rotated — generate a new keypair; old
            # receipts remain verifiable (they carry their own
            # algorithm + public key) but no new records can be
            # signed with the old key.
        kp = self._provider.generate_keypair()
        path.write_text(json.dumps({
            "algorithm_id": kp.algorithm_id,
            "public_key": base64.b64encode(kp.public_key).decode("ascii"),
            "secret_key": base64.b64encode(kp.secret_key).decode("ascii"),
            "created_at": time.time(),
        }, indent=2), encoding="utf-8")
        # Best-effort: on POSIX, restrict the file to owner-only. On
        # Windows, the file ACL is inherited from the user's profile
        # and cannot be tightened from Python portably.
        try:
            import os, stat
            if os.name == "posix":
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
                os.chmod(self._key_dir, stat.S_IRWXU)
        except OSError:
            pass
        return kp

    @property
    def algorithm_id(self) -> str:
        return self._algorithm_id

    @property
    def public_key(self) -> bytes:
        return self._keypair.public_key

    # ------------------------------------------------------------------
    # signing
    # ------------------------------------------------------------------
    def _sign_digest(self, content_digest: str) -> TrustReceipt:
        # Sign the literal digest string (UTF-8) — both verifier
        # and signer use the same encoding, so no ambiguity.
        sig = self._provider.sign(self._keypair.secret_key,
                                    content_digest.encode("utf-8"))
        return TrustReceipt(
            subject_type="",    # set by the caller
            subject_id="",      # set by the caller
            algorithm_id=self._algorithm_id,
            public_key=self._keypair.public_key,
            content_digest=content_digest,
            signature=sig,
            created_at=time.time(),
        )

    def sign_run(self, run: dict) -> TrustReceipt:
        receipt = self._sign_digest(run["content_digest"])
        receipt = TrustReceipt(
            subject_type="run", subject_id=run["id"],
            algorithm_id=receipt.algorithm_id,
            public_key=receipt.public_key,
            content_digest=receipt.content_digest,
            signature=receipt.signature, created_at=receipt.created_at,
        )
        self._persist(receipt)
        return receipt

    def sign_finding(self, finding: dict) -> TrustReceipt:
        # The signer and verifier MUST use the same digest
        # computation. We recompute the digest from the row at
        # sign time using the canonical reconstruction function
        # (``live_finding_digest``). This guarantees the signed
        # digest equals the verification-time digest whenever
        # the row's JSON columns are the canonical representation
        # of the finding.
        from satsa.analysis.canonical import live_finding_digest
        digest = live_finding_digest(finding)
        receipt = self._sign_digest(digest)
        receipt = TrustReceipt(
            subject_type="finding", subject_id=finding["id"],
            algorithm_id=receipt.algorithm_id,
            public_key=receipt.public_key,
            content_digest=receipt.content_digest,
            signature=receipt.signature, created_at=receipt.created_at,
        )
        self._persist(receipt)
        return receipt

    def _persist(self, r: TrustReceipt) -> None:
        # idempotent on (subject_type, subject_id, content_digest):
        # a re-sign of the same digest is a no-op (same record, same
        # bytes). A different digest for the same subject replaces
        # the previous receipt.
        self._db.execute(
            "DELETE FROM satsa_trust_receipts"
            " WHERE subject_type=? AND subject_id=?",
            (r.subject_type, r.subject_id))
        self._db.execute(
            "INSERT INTO satsa_trust_receipts"
            " (subject_type, subject_id, algorithm_id, public_key,"
            "  content_digest, signature, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (r.subject_type, r.subject_id, r.algorithm_id,
             r.public_key, r.content_digest, r.signature, r.created_at))

# ------------------------------------------------------------------
    # verification
    # ------------------------------------------------------------------
    def verify_subject(self, subject_type: str, subject_id: str,
                       current_content_digest: str) -> tuple[bool, str]:
        """Returns (ok, reason). The reason is human-readable and is
        suitable for direct inclusion in audit reports."""
        rows = self._db.query_all(
            "SELECT * FROM satsa_trust_receipts"
            " WHERE subject_type=? AND subject_id=?",
            (subject_type, subject_id))
        if not rows:
            return False, f"no trust receipt for {subject_type} {subject_id}"
        r = rows[-1]   # most recent
        if r["content_digest"] != current_content_digest:
            return False, (
                f"digest mismatch: receipt has {r['content_digest'][:16]}…,"
                f" live record is {current_content_digest[:16]}…")
        # For AnalysisRuns, the stored ``satsa_runs.content_digest``
        # column is the seed the receipt was signed over. If that
        # column was tampered, it must not equal the receipt's
        # signed digest; the signature would then no longer verify
        # the row (the row's signed-digest column is not the
        # digest the signature is over). This second check detects
        # the case where an attacker tampers the stored digest
        # column without re-signing.
        # Note: this check is skipped when the row was signed out
        # of band (e.g. a unit test constructing a synthetic run
        # record), in which case there is no row to inspect.
        if subject_type == "run":
            try:
                row = self._db.query_one(
                    "SELECT content_digest FROM satsa_runs WHERE id=?",
                    (subject_id,))
            except Exception:  # noqa: BLE001
                row = None
            if row is not None and row["content_digest"] is not None:
                if row["content_digest"] != r["content_digest"]:
                    return False, (
                        f"digest mismatch: stored column"
                        f" {str(row['content_digest'])[:16]}…, receipt"
                        f" {r['content_digest'][:16]}…")
        provider = SIGNATURE_PROVIDERS.get(r["algorithm_id"])
        if provider is None:
            return False, f"unknown algorithm {r['algorithm_id']!r}"
        ok = provider.verify(r["public_key"],
                               r["content_digest"].encode("utf-8"),
                               r["signature"])
        if not ok:
            return False, "signature does not verify"
        return True, "ok"


# ---------------------------------------------------------------------------
# Convenience: a one-call helper used by RunService
# ---------------------------------------------------------------------------

def attest_run_outputs(engine, key_dir, run: dict,
                       findings: list[dict]) -> dict:
    """Sign a run + its findings and return a small summary for the
    run's `summary_json` field. The signatures are persisted in
    ``satsa_trust_receipts``; the summary just records counts.

    The run's content_digest is *re-computed from its current
    column state* before signing — so the signed digest reflects
    the run at sign-time (status, observation_ids, etc.), not just
    at insert-time. This is the value the verifier reproduces."""
    from qsmlops.crypto.hashing import digest_document
    from satsa.domain.runs import AnalysisRun
    import json
    svc = TrustService(engine, key_dir)
    # Re-compute the run's digest from its current row state
    observation_ids = run.get("observation_ids_json") or "[]"
    if isinstance(observation_ids, str):
        try:
            observation_ids = json.loads(observation_ids)
        except (TypeError, ValueError):
            observation_ids = []
    reconstructed = {
        "id": run.get("id"),
        "entity_id": run.get("entity_id"),
        "assessment_id": run.get("assessment_id"),
        "snapshot_digest": run.get("snapshot_digest"),
        "baseline_digests": {},
        "code_version": run.get("code_version"),
        "analytics_version": run.get("analytics_version"),
        "model_version": run.get("model_version"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "observation_ids": observation_ids,
        "error": run.get("error") or "",
        "schema_version": 1,
    }
    live_run_digest = digest_document(
        AnalysisRun.from_dict(reconstructed).to_dict())
    # sign the live digest directly (rather than via sign_run which
    # uses the stored column)
    sig = svc._provider.sign(svc._keypair.secret_key,
                              live_run_digest.encode("utf-8"))
    from satsa.analysis.trust import TrustReceipt
    run_receipt = TrustReceipt(
        subject_type="run", subject_id=run.get("id"),
        algorithm_id=svc.algorithm_id,
        public_key=svc.public_key, content_digest=live_run_digest,
        signature=sig, created_at=time.time())
    svc._persist(run_receipt)
    finding_receipts = [svc.sign_finding(f) for f in findings]
    return {
        "algorithm_id": svc.algorithm_id,
        "run_signed": True,
        "findings_signed": len(finding_receipts),
        "public_key_b64": base64.b64encode(svc.public_key).decode("ascii"),
        "run_receipt_digest": run_receipt.content_digest,
    }

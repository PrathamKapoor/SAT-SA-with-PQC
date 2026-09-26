"""TRUST-SAT signing and live verification using existing QSMLOps crypto.

Legacy offline run/finding receipts retain their canonical schemas. Tenant-scoped
supervisory receipts bind the immutable decision, reviewed context, analytical
results and source provenance on SQLite and PostgreSQL. Recoverable finalization
uses the existing receipt table and AuditService/EvidenceLedger, not a second
trust system. Signatures use ML-DSA-65 over canonical SHA3-256 digest strings.

Integrity verification does not prove real-world evidence truth or absolute
resistance to coordinated database/ledger/key replacement. Keys remain in the
external protected key directory; verification-only instances need no secret.
See docs/TRUST_MODEL.md for the exact canonical schema and proof boundaries.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path

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
    ``<key_dir>/satsa_trust_key.json`` so runs use the same signing key.
    Verification-only tenant instances do not read private keys."""

    def __init__(
        self,
        engine,
        key_dir: Path | None,
        algorithm_id: str = DEFAULT_ALGORITHM,
        *,
        organization_id: str | None = None,
    ) -> None:
        from satsa.tenancy import require_offline_store

        if organization_id is None:
            require_offline_store(engine)
        self._db = engine
        self._organization_id = organization_id
        if key_dir is None:
            if organization_id is None:
                raise ValueError("legacy signing requires a key directory")
            return  # verification-only service never loads or creates private keys
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
            raise ValueError("configured signing algorithm differs from key file")
        kp = self._provider.generate_keypair()
        # Publish a complete key file atomically. Concurrent first-use workers
        # may generate candidates, but all adopt the single published key.
        import os
        import tempfile

        fd, temporary = tempfile.mkstemp(prefix=".trust-key-", dir=self._key_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(
                    {
                        "algorithm_id": kp.algorithm_id,
                        "public_key": base64.b64encode(kp.public_key).decode("ascii"),
                        "secret_key": base64.b64encode(kp.secret_key).decode("ascii"),
                        "created_at": time.time(),
                    },
                    output,
                )
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                current = json.loads(path.read_text(encoding="utf-8"))
                if current["algorithm_id"] != self._algorithm_id:
                    raise ValueError(
                        "configured signing algorithm differs from key file"
                    )
                kp = KeyPair(
                    algorithm_id=current["algorithm_id"],
                    public_key=base64.b64decode(current["public_key"]),
                    secret_key=base64.b64decode(current["secret_key"]),
                )
        finally:
            Path(temporary).unlink(missing_ok=True)
        # Best-effort: on POSIX, restrict the file to owner-only. On
        # Windows, the file ACL is inherited from the user's profile
        # and cannot be tightened from Python portably.
        try:
            import os
            import stat

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

    def validate_signing_key(self) -> None:
        """Fail closed when provisioned signing material is malformed or mismatched."""
        message = b"satsa-trust-key-self-test-v1"
        signature = self._provider.sign(self._keypair.secret_key, message)
        if not self._provider.verify(self._keypair.public_key, message, signature):
            raise ValueError("configured TRUST-SAT signing key pair is invalid")

    # ------------------------------------------------------------------
    # signing
    # ------------------------------------------------------------------
    def _sign_digest(self, content_digest: str) -> TrustReceipt:
        # Sign the literal digest string (UTF-8) — both verifier
        # and signer use the same encoding, so no ambiguity.
        sig = self._provider.sign(
            self._keypair.secret_key, content_digest.encode("utf-8")
        )
        return TrustReceipt(
            subject_type="",  # set by the caller
            subject_id="",  # set by the caller
            algorithm_id=self._algorithm_id,
            public_key=self._keypair.public_key,
            content_digest=content_digest,
            signature=sig,
            created_at=time.time(),
        )

    def sign_run(self, run: dict) -> TrustReceipt:
        self._legacy_only()
        receipt = self._sign_digest(run["content_digest"])
        receipt = TrustReceipt(
            subject_type="run",
            subject_id=run["id"],
            algorithm_id=receipt.algorithm_id,
            public_key=receipt.public_key,
            content_digest=receipt.content_digest,
            signature=receipt.signature,
            created_at=receipt.created_at,
        )
        self._persist(receipt)
        return receipt

    def sign_finding(self, finding: dict) -> TrustReceipt:
        self._legacy_only()
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
            subject_type="finding",
            subject_id=finding["id"],
            algorithm_id=receipt.algorithm_id,
            public_key=receipt.public_key,
            content_digest=receipt.content_digest,
            signature=receipt.signature,
            created_at=receipt.created_at,
        )
        self._persist(receipt)
        return receipt

    def _persist(self, r: TrustReceipt) -> None:
        self._legacy_only()
        if r.subject_type not in RECEIPT_TYPES:
            raise ValueError("legacy persistence cannot modify supervisory receipts")
        # Preserve legacy replacement semantics. Supervisory finalization
        # never uses this path: its receipt is unique and never replaced.
        self._db.execute(
            "DELETE FROM satsa_trust_receipts WHERE subject_type=? AND subject_id=?",
            (r.subject_type, r.subject_id),
        )
        self._db.execute(
            "INSERT INTO satsa_trust_receipts"
            " (subject_type, subject_id, algorithm_id, public_key,"
            "  content_digest, signature, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                r.subject_type,
                r.subject_id,
                r.algorithm_id,
                r.public_key,
                r.content_digest,
                r.signature,
                r.created_at,
            ),
        )

    # ------------------------------------------------------------------
    # verification
    # ------------------------------------------------------------------
    def verify_subject(
        self, subject_type: str, subject_id: str, current_content_digest: str
    ) -> tuple[bool, str]:
        """Returns (ok, reason). The reason is human-readable and is
        suitable for direct inclusion in audit reports."""
        self._legacy_only()
        if subject_type not in RECEIPT_TYPES:
            raise ValueError("supervisory verification requires tenant context")
        rows = self._db.query_all(
            "SELECT * FROM satsa_trust_receipts WHERE subject_type=? AND subject_id=?",
            (subject_type, subject_id),
        )
        if not rows:
            return False, f"no trust receipt for {subject_type} {subject_id}"
        r = rows[-1]  # most recent
        if r["content_digest"] != current_content_digest:
            return False, (
                f"digest mismatch: receipt has {r['content_digest'][:16]}…,"
                f" live record is {current_content_digest[:16]}…"
            )
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
                    "SELECT content_digest FROM satsa_runs WHERE id=?", (subject_id,)
                )
            except Exception:  # noqa: BLE001
                row = None
            if (
                row is not None
                and row["content_digest"] is not None
                and row["content_digest"] != r["content_digest"]
            ):
                return False, (
                    f"digest mismatch: stored column"
                    f" {str(row['content_digest'])[:16]}…, receipt"
                    f" {r['content_digest'][:16]}…"
                )
        provider = SIGNATURE_PROVIDERS.get(r["algorithm_id"])
        if provider is None:
            return False, f"unknown algorithm {r['algorithm_id']!r}"
        ok = provider.verify(
            r["public_key"], r["content_digest"].encode("utf-8"), r["signature"]
        )
        if not ok:
            return False, "signature does not verify"
        return True, "ok"

    def _legacy_only(self) -> None:
        if self._organization_id is not None:
            raise ValueError("tenant trust requires scoped finalization operations")

    def _finalization(self, run_id: str) -> dict | None:
        from qsmlops.core.errors import PermissionDeniedError

        if not self._organization_id:
            raise ValueError("organization context is required")
        context = self._db.query_one(
            "SELECT run_id FROM satsa_run_context WHERE organization_id=? AND run_id=?",
            (self._organization_id, run_id),
        )
        if context is None:
            raise PermissionDeniedError("trust run does not belong to organization")
        return self._db.query_one(
            "SELECT * FROM satsa_trust_finalizations WHERE organization_id=? AND run_id=?",
            (self._organization_id, run_id),
        )

    def finalize(self, run_id: str, audit, *, boundary=None) -> dict:
        """Idempotently bind a persisted decision, receipt and existing ledger.

        Internal worker operation: caller-facing authorization is enforced by
        AnalysisExecutionService. Context and ownership remain mandatory here.
        boundary is an optional failure-injection hook for recovery tests.
        """
        from qsmlops.crypto.hashing import canonical_json, digest_document
        from qsmlops.security.audit.events import AuditEvent
        from satsa.analysis.canonical import supervisory_document
        from satsa.analysis.execution import _stable_id

        self._finalization(run_id)
        assert self._organization_id is not None
        doc = supervisory_document(self._db, self._organization_id, run_id)
        digest = digest_document(doc)
        identity = _stable_id(
            "final", self._organization_id, run_id, doc["decision"]["id"], "1"
        )
        if boundary:
            boundary("canonicalized")
        with self._db.transaction():
            self._db.execute(
                "INSERT INTO satsa_trust_finalizations"
                " (id,organization_id,run_id,decision_id,schema_version,state,canonical_json,content_digest,created_at)"
                " VALUES (?,?,?,?,1,'prepared',?,?,?) ON CONFLICT DO NOTHING",
                (
                    identity,
                    self._organization_id,
                    run_id,
                    doc["decision"]["id"],
                    canonical_json(doc).decode("utf-8"),
                    digest,
                    time.time(),
                ),
            )
        row = self._finalization(run_id)
        assert row is not None
        if (
            row["id"] != identity
            or row["content_digest"] != digest
            or row["canonical_json"] != canonical_json(doc).decode("utf-8")
        ):
            raise ValueError("prepared finalization differs from live canonical state")
        if boundary:
            boundary("prepared")
        audit.record_once(
            self._progress_event(row, "trust.finalization_started", AuditEvent)
        )
        if row["receipt_id"] is None:
            signature = self._sign_digest(digest)
            if boundary:
                boundary("signed")
            with self._db.transaction():
                suffix = " FOR UPDATE" if self._db.dialect == "postgresql" else ""
                current = self._db.query_one(
                    "SELECT * FROM satsa_trust_finalizations WHERE organization_id=? AND id=?"
                    + suffix,
                    (self._organization_id, identity),
                )
                assert current is not None
                if current["receipt_id"] is None:
                    # Recheck after signing; never silently bind changed data.
                    if (
                        digest_document(
                            supervisory_document(
                                self._db, self._organization_id, run_id
                            )
                        )
                        != digest
                    ):
                        raise ValueError("live canonical state changed during signing")
                    self._db.execute(
                        "INSERT INTO satsa_trust_receipts (subject_type,subject_id,algorithm_id,public_key,content_digest,signature,created_at)"
                        " VALUES ('supervisory_finalization',?,?,?,?,?,?)",
                        (
                            identity,
                            signature.algorithm_id,
                            signature.public_key,
                            digest,
                            signature.signature,
                            signature.created_at,
                        ),
                    )
                    receipt = self._db.query_one(
                        "SELECT id FROM satsa_trust_receipts WHERE subject_type='supervisory_finalization' AND subject_id=?",
                        (identity,),
                    )
                    assert receipt is not None
                    self._db.execute(
                        "UPDATE satsa_trust_finalizations SET receipt_id=?,state='recorded' WHERE organization_id=? AND id=?",
                        (receipt["id"], self._organization_id, identity),
                    )
        row = self._finalization(run_id)
        assert row is not None
        if boundary:
            boundary("recorded")
        receipt = self._db.query_one(
            "SELECT * FROM satsa_trust_receipts WHERE id=?", (row["receipt_id"],)
        )
        if receipt is None:
            raise ValueError("final receipt missing after persistence")
        event = self._final_event(row, receipt, AuditEvent)
        entry_hash = audit.record_once(event)
        if boundary:
            boundary("ledger_appended")
        self._db.execute(
            "UPDATE satsa_trust_finalizations SET ledger_entry_hash=? WHERE organization_id=? AND id=?",
            (entry_hash, self._organization_id, identity),
        )
        ok, reason = self.verify_finalization(run_id, audit)
        if not ok:
            raise ValueError(f"trust verification failed: {reason}")
        if boundary:
            boundary("verified")
        self._db.execute(
            "UPDATE satsa_trust_finalizations SET verified_at=COALESCE(verified_at,?) WHERE organization_id=? AND id=?",
            (time.time(), self._organization_id, identity),
        )
        row = self._finalization(run_id)
        assert row is not None
        audit.record_once(
            self._progress_event(row, "trust.verification_completed", AuditEvent)
        )
        self._db.execute(
            "UPDATE satsa_trust_finalizations SET state='verified' WHERE organization_id=? AND id=?",
            (self._organization_id, identity),
        )
        return self.get_final_receipt(run_id)

    @staticmethod
    def _progress_event(row, action, event_type):
        decision = json.loads(row["canonical_json"])["decision"]
        return event_type(
            event_id=f"{row['id']}:{action}",
            timestamp=row["verified_at"]
            if action == "trust.verification_completed"
            else row["created_at"],
            actor=decision["principal_identity_id"],
            action=action,
            resource=f"analysis_run:{row['run_id']}",
            result="SUCCESS",
            evidence_reference=row["id"],
            metadata={
                "organization_id": row["organization_id"],
                "decision_id": row["decision_id"],
                "canonical_digest": row["content_digest"],
            },
        )

    @staticmethod
    def _final_event(row, receipt, event_type):
        from qsmlops.crypto.hashing import sha3_hex

        doc = json.loads(row["canonical_json"])
        return event_type(
            event_id=row["id"],
            timestamp=row["created_at"],
            actor=doc["decision"]["principal_identity_id"],
            action="trust.supervisory_finalized",
            resource=f"analysis_run:{row['run_id']}",
            result="SUCCESS",
            evidence_reference=row["id"],
            metadata={
                "organization_id": row["organization_id"],
                "decision_id": row["decision_id"],
                "canonical_digest": row["content_digest"],
                "algorithm_id": receipt["algorithm_id"],
                "receipt_created_at": receipt["created_at"],
                "key_id": sha3_hex(bytes(receipt["public_key"])),
                "signature_digest": sha3_hex(bytes(receipt["signature"])),
            },
        )

    def get_final_receipt(self, run_id: str) -> dict:
        row = self._finalization(run_id)
        if row is None or row["receipt_id"] is None:
            raise ValueError("final receipt missing")
        receipt = self._db.query_one(
            "SELECT * FROM satsa_trust_receipts WHERE id=? AND subject_id=? AND subject_type='supervisory_finalization'",
            (row["receipt_id"], row["id"]),
        )
        if receipt is None:
            raise ValueError("final receipt relationship mismatch")
        from qsmlops.crypto.hashing import sha3_hex

        return {
            "id": row["id"],
            "organization_id": row["organization_id"],
            "run_id": run_id,
            "decision_id": row["decision_id"],
            "schema_version": 1,
            "state": row["state"],
            "ledger_entry_hash": row["ledger_entry_hash"],
            "key_id": sha3_hex(bytes(receipt["public_key"])),
            **TrustReceipt(
                **{key: receipt[key] for key in TrustReceipt.__dataclass_fields__}
            ).to_dict(),
        }

    def verify_finalization(self, run_id: str, audit) -> tuple[bool, str]:
        from qsmlops.core.errors import PermissionDeniedError
        from qsmlops.crypto.hashing import canonical_json, digest_document
        from qsmlops.security.audit.events import AuditEvent
        from satsa.analysis.canonical import supervisory_document

        row = self._finalization(run_id)  # ownership failure is not an integrity result
        if row is None:
            return False, "finalization missing"
        assert self._organization_id is not None
        try:
            doc = supervisory_document(self._db, self._organization_id, run_id)
            if (
                canonical_json(doc).decode("utf-8") != row["canonical_json"]
                or digest_document(doc) != row["content_digest"]
            ):
                return False, "live canonical state mismatch"
            if (
                doc["decision"]["id"] != row["decision_id"]
                or row["schema_version"] != 1
            ):
                return False, "decision binding mismatch"
            receipt = self._db.query_one(
                "SELECT * FROM satsa_trust_receipts WHERE id=? AND subject_id=? AND subject_type='supervisory_finalization'",
                (row["receipt_id"], row["id"]),
            )
            if receipt is None or receipt["content_digest"] != row["content_digest"]:
                return False, "receipt digest or relationship mismatch"
            provider = SIGNATURE_PROVIDERS.get(receipt["algorithm_id"])
            if provider is None or not provider.verify(
                bytes(receipt["public_key"]),
                receipt["content_digest"].encode("utf-8"),
                bytes(receipt["signature"]),
            ):
                return False, "signature does not verify"
            ok, reason = audit.verify_event(
                self._final_event(row, receipt, AuditEvent), row["ledger_entry_hash"]
            )
            if not ok:
                return False, reason
        except PermissionDeniedError:
            return False, "canonical ownership mismatch"
        except (ValueError, KeyError, TypeError) as exc:
            return False, f"canonical integrity failure: {exc}"
        return True, "ok"


# ---------------------------------------------------------------------------
# Convenience: a one-call helper used by RunService
# ---------------------------------------------------------------------------


def attest_run_outputs(engine, key_dir, run: dict, findings: list[dict]) -> dict:
    """Sign a run + its findings and return a small summary for the
    run's `summary_json` field. The signatures are persisted in
    ``satsa_trust_receipts``; the summary just records counts.

    The run's content_digest is *re-computed from its current
    column state* before signing — so the signed digest reflects
    the run at sign-time (status, observation_ids, etc.), not just
    at insert-time. This is the value the verifier reproduces."""
    import json

    from qsmlops.crypto.hashing import digest_document
    from satsa.domain.runs import AnalysisRun

    svc = TrustService(engine, key_dir)
    # Re-compute the run's digest from its current row state
    observation_ids = run.get("observation_ids_json") or "[]"
    if isinstance(observation_ids, str):
        try:
            observation_ids = json.loads(observation_ids)
        except (TypeError, ValueError):
            observation_ids = []
    reconstructed: dict = {
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
    live_run_digest = digest_document(AnalysisRun.from_dict(reconstructed).to_dict())
    # sign the live digest directly (rather than via sign_run which
    # uses the stored column)
    sig = svc._provider.sign(svc._keypair.secret_key, live_run_digest.encode("utf-8"))
    from satsa.analysis.trust import TrustReceipt

    run_receipt = TrustReceipt(
        subject_type="run",
        subject_id=run["id"],
        algorithm_id=svc.algorithm_id,
        public_key=svc.public_key,
        content_digest=live_run_digest,
        signature=sig,
        created_at=time.time(),
    )
    svc._persist(run_receipt)
    finding_receipts = [svc.sign_finding(f) for f in findings]
    return {
        "algorithm_id": svc.algorithm_id,
        "run_signed": True,
        "findings_signed": len(finding_receipts),
        "public_key_b64": base64.b64encode(svc.public_key).decode("ascii"),
        "run_receipt_digest": run_receipt.content_digest,
    }

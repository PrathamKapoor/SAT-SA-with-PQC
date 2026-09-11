"""TrustedObject: the base trust abstraction for every platform object.

The platform's end-state treats all ML objects (models, artifacts, passports,
BOMs) and governance objects (identities, permissions, audit events) as
*trusted objects*: each one carries identity, ownership, version, a content
hash, an optional signature, provenance, and an explicit verification status.

Phase 1 defines the vocabulary only. Signing of instances and full provenance
chains are later-phase capabilities; the fields exist now so downstream code
can populate them without schema breaks.

Compatibility contract: :class:`TrustedObject` serializes to the same flat key
set consumed by the evidence ledger, so identity records (which are
TrustedObjects) ride the existing tamper-evident chain without new storage.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from qsmlops.core.errors import IntegrityError
from qsmlops.crypto.hashing import digest_document

# Values are ordered by trust lifecycle stage.
VERIFICATION_UNVERIFIED = "UNVERIFIED"
VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_FAILED = "FAILED"
VERIFICATION_STATUSES = (
    VERIFICATION_UNVERIFIED,
    VERIFICATION_VERIFIED,
    VERIFICATION_FAILED,
)


class TrustedObject:
    """An object the platform can hash, sign, version, and verify.

    Merely instantiating a TrustedObject does NOT make it trusted. Trust is
    established only when ``signature`` is present AND ``verify()`` succeeds
    against a trust anchor.
    """

    def __init__(
        self,
        object_type: str,
        owner: str,
        *,
        id: str | None = None,
        version: int = 1,
        created_at: float | None = None,
        updated_at: float | None = None,
        hash: str = "",
        signature: dict | None = None,
        verification_status: str = VERIFICATION_UNVERIFIED,
        metadata: dict | None = None,
    ) -> None:
        if not object_type:
            raise ValueError("object_type is required")
        if verification_status not in VERIFICATION_STATUSES:
            raise ValueError(f"invalid verification_status {verification_status!r}")
        now = time.time()
        self.id = id or uuid.uuid4().hex
        self.object_type = object_type
        self.owner = owner
        self.version = int(version)
        self.created_at = float(created_at if created_at is not None else now)
        self.updated_at = float(updated_at if updated_at is not None else now)
        self.hash = hash
        self.signature: dict = dict(signature or {})
        self.verification_status = verification_status
        self.metadata: dict = dict(metadata or {})

    # -------------------- composition --------------------
    def body(self) -> dict[str, Any]:
        """Canonical identity document that gets hashed and signed."""
        return {
            "id": self.id,
            "object_type": self.object_type,
            "owner": self.owner,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        """Flat document (identity fields + signature). Ledger-compat shape:
        every field is an identity property; no top-level 'record' wrapper."""
        doc = self.body()
        doc["hash"] = self.hash
        doc["signature"] = self.signature
        doc["verification_status"] = self.verification_status
        return doc

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "TrustedObject":
        return cls(
            object_type=doc["object_type"],
            owner=doc["owner"],
            id=doc.get("id"),
            version=doc.get("version", 1),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            hash=doc.get("hash", ""),
            signature=doc.get("signature"),
            verification_status=doc.get("verification_status", VERIFICATION_UNVERIFIED),
            metadata=doc.get("metadata"),
        )

    # -------------------- hashing --------------------
    def compute_hash(self) -> str:
        """Digest of the canonical body; also stored on ``self.hash``."""
        self.hash = digest_document(self.body())
        return self.hash

    def hash_matches(self) -> bool:
        return bool(self.hash) and digest_document(self.body()) == self.hash

    # -------------------- signing / verification --------------------
    def sign(self, key_id: str, signature_hex: str, suite_id: str) -> None:
        """Attach an externally produced signature over the body digest."""
        if not self.hash:
            self.compute_hash()
        self.signature = {
            "key_id": key_id,
            "signature_hex": signature_hex,
            "suite_id": suite_id,
            "signed_at": time.time(),
        }

    def verify(self, signature_verifier, public_key: bytes) -> bool:
        """Verify the attached signature over the body digest.

        ``signature_verifier`` is a callable ``(public_key, message, sig) ->
        bool`` (e.g. a SignatureProvider). Raises ``IntegrityError`` when the
        hash is absent or stale (the signed body no longer matches).
        """
        if not self.hash or not self.hash_matches():
            raise IntegrityError(f"{self.object_type} {self.id}: hash missing or stale")
        if not self.signature:
            self.verification_status = VERIFICATION_UNVERIFIED
            return False
        message = digest_document(self.body()).encode()
        ok = bool(
            signature_verifier(public_key, message, bytes.fromhex(self.signature["signature_hex"]))
        )
        self.verification_status = VERIFICATION_VERIFIED if ok else VERIFICATION_FAILED
        return ok

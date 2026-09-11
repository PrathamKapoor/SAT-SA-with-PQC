"""Quantum ML Supply-Chain Bill of Materials (QML-BOM).

Tracks complete ML lineage: datasets, preprocessing steps, dependencies,
training code, frameworks, hardware environment and produced artifacts. Each
element is recorded with a SHA3-256 digest; the BOM itself is a canonical
document whose digest is bound into the model passport, so any supply-chain
change invalidates downstream trust.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from qsmlops.crypto.hashing import digest_document


class BOMError(Exception):
    pass


@dataclass
class BOMEntry:
    kind: str  # dataset | preprocessing | dependency | code | framework | hardware | artifact
    name: str
    digest: str
    version: str = ""
    origin: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class QMLBOM:
    bom_id: str
    created_at: float
    entries: list[BOMEntry] = field(default_factory=list)

    @classmethod
    def create(cls) -> "QMLBOM":
        return cls(bom_id=uuid.uuid4().hex, created_at=time.time())

    def add_entry(
        self,
        kind: str,
        name: str,
        digest: str,
        version: str = "",
        origin: str = "",
        metadata: dict | None = None,
    ) -> BOMEntry:
        if kind not in {
            "dataset",
            "preprocessing",
            "dependency",
            "code",
            "framework",
            "hardware",
            "artifact",
        }:
            raise BOMError(f"invalid BOM entry kind {kind!r}")
        if len(digest) != 64:
            raise BOMError(f"digest for {name!r} must be a sha3-256 hex string")
        entry = BOMEntry(kind, name, digest.lower(), version, origin, dict(metadata or {}))
        self.entries.append(entry)
        return entry

    def to_dict(self) -> dict:
        return {
            "bom_id": self.bom_id,
            "created_at": self.created_at,
            "entries": [e.__dict__ for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QMLBOM":
        bom = cls(bom_id=d["bom_id"], created_at=d["created_at"])
        bom.entries = [BOMEntry(**e) for e in d.get("entries", [])]
        return bom

    def digest(self) -> str:
        return digest_document(self.to_dict())

    def by_kind(self, kind: str) -> list[BOMEntry]:
        return [e for e in self.entries if e.kind == kind]

    def verify_artifact(self, artifact_store, digest_hex: str) -> bool:
        """An artifact is trusted only if present in the store AND declared in this BOM."""
        if not artifact_store.verify(digest_hex):
            return False
        return any(e.digest == digest_hex for e in self.entries)

    def diff(self, other: "QMLBOM") -> dict:
        mine = {(e.kind, e.name, e.digest) for e in self.entries}
        theirs = {(e.kind, e.name, e.digest) for e in other.entries}
        return {
            "added": sorted(theirs - mine),
            "removed": sorted(mine - theirs),
        }

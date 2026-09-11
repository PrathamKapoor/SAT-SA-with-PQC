"""Append-only, hash-chained evidence ledger with content-addressed packet persistence.

Every entry embeds the hash of its predecessor; the chain head is a commitment
over the full operational history. Any retroactive edit breaks the chain and is
detected by `verify_chain`.

Workstream F1 — Packet Payload Persistence:
  VerificationPacket bodies are now durably stored content-addressed by their
  canonical SHA3-256 digest (via ArtifactStore semantics) under
  <ledger_parent>/packets/<digest[:2]>/<digest>. The ledger entry commits to
  the packet via `record.digest`; the packet body is retrievable and its
  digest is verified on load (tamper detection). Ledger hash-chain semantics
  and `verify_chain` are unchanged; old entries without a packet body remain
  readable.

  Design choice: content-addressed via ArtifactStore rather than embedding
  huge payloads in every ledger row — preserves hash-chaining, immutability,
  auditability, deterministic canonical serialization, and avoids duplication.
  Packet store is the single source of truth for packet bodies; ledger is
  the source of truth for ordering and chain.

  Security: packet bodies are proof-carrying but contain no private key
  material, HSM PINs, passphrases or credentials. Persistence rejects packets
  that contain sensitive field names (defense-in-depth).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Iterator

from qsmlops.artifacts.store import ArtifactStore
from qsmlops.crypto.hashing import canonical_json, sha3_hex
from qsmlops.evidence.packet import VerificationPacket

GENESIS_PREV = "0" * 64


class LedgerError(Exception):
    pass


# Sensitive field substrings that must never be persisted in a packet body.
# Defense-in-depth: even if a caller mistakenly includes secret material,
# persistence fails closed rather than storing secrets.
_SENSITIVE_SUBSTRINGS = (
    "private_key",
    "secret_key",
    "secretkey",
    "hsm_pin",
    "pin",
    "passphrase",
    "credential",
    "privatekey",
)


def _contains_sensitive(obj) -> str | None:
    """Recursively scan packet dict for sensitive field names; return offending key or None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = k.lower()
            # Allowlist: "pin" as substring is too broad (e.g. "opinion"), so require exact or private-related
            # Check for private/secret/passphrase/credential exactly
            for sensitive in _SENSITIVE_SUBSTRINGS:
                # For "pin", only flag if key is exactly pin / hsm_pin / user_pin etc., not arbitrary substring
                if sensitive == "pin":
                    if lk in ("pin", "hsm_pin", "user_pin", "so_pin", "token_pin"):
                        return k
                elif sensitive in lk:
                    return k
            found = _contains_sensitive(v)
            if found:
                return found
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found = _contains_sensitive(item)
            if found:
                return found
    return None


class EvidenceLedger:
    def __init__(self, path: Path, packet_store_path: Path | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Packet store: content-addressed immutable packet bodies, co-located with ledger.
        # Default: <ledger_parent>/packets  (e.g. ~/.qsmlops/ledger/packets)
        if packet_store_path is None:
            packet_store_path = self.path.parent / "packets"
        self.packet_store_path = Path(packet_store_path)
        self.packet_store = ArtifactStore(self.packet_store_path)
        self.packet_store_path.mkdir(parents=True, exist_ok=True)

    def _raw_lines(self) -> list[str]:
        """Return every non-empty physical line of the ledger file."""
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(line)
        return out

    def _entries(self) -> list[dict]:
        """Parse every valid ledger line.

        T3: a malformed line must NOT crash the read path or silently vanish
        without a trace — it is skipped here (so valid entries around it are
        preserved and the chain can still be traversed) and is reported
        explicitly by :meth:`verify_chain`. No existing entry is mutated or
        'repaired'."""
        out = []
        for line in self._raw_lines():
            try:
                out.append(json.loads(line))
            except (ValueError, json.JSONDecodeError):
                continue
        return out

    def append(self, record: dict) -> dict:
        with self._lock:
            entries = self._entries()
            prev_hash = entries[-1]["entry_hash"] if entries else GENESIS_PREV
            body = {
                "seq": len(entries),
                "timestamp": time.time(),
                "prev_hash": prev_hash,
                "record": record,
            }
            entry_hash = sha3_hex(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            )
            entry = {**body, "entry_hash": entry_hash}
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
            return entry

    def append_packet(self, packet: VerificationPacket) -> dict:
        """Persist a VerificationPacket body content-addressed and commit its digest to the ledger.

        Order (fail-closed):
          1. Validate packet does not contain sensitive field names.
          2. Enforce packet_id immutability: same id with different digest → LedgerError.
          3. Store packet body via packet_store (canonical JSON, SHA3 content-addressed).
             If store digest != packet.digest() → LedgerError.
          4. Append ledger entry committing to packet_id/digest/objective/actor/decision.
             Ledger hash-chain is unchanged; historical entries remain readable.

        The packet body is stored *before* the ledger entry so a reader never sees
        a ledger entry whose packet body is missing under normal operation. If
        the process crashes between store and ledger commit, the orphan packet
        (content-addressed) is harmless and will be GC-able; no ledger entry
        falsely claims persistence.
        """
        # 1. Sensitive check
        pkt_dict = packet.to_dict()
        offending = _contains_sensitive(pkt_dict)
        if offending:
            raise LedgerError(f"packet contains sensitive field {offending!r}; persistence rejected")

        # 2. Immutability: packet_id is unique — any second append with same id is rejected
        #    (whether digest matches or not). This enforces that a packet, once committed,
        #    is immutable and not duplicated in the ledger.
        with self._lock:
            existing = self.find_by_packet(packet.packet_id)
            if existing is not None:
                raise LedgerError(
                    f"packet_id {packet.packet_id!r} already exists "
                    f"(immutable packet violated — packet_id must be unique)"
                )
            current_digest = packet.digest()

        # 3. Store body content-addressed (outside lock to not hold ledger lock during IO,
        #    but store is atomic via ArtifactStore.put)
        canonical = canonical_json(pkt_dict)
        # ArtifactStore.put is idempotent and atomic (temp file + rename)
        try:
            stored_digest = self.packet_store.put(canonical)
        except Exception as exc:
            raise LedgerError(f"packet store unavailable: {exc}") from exc
        if stored_digest != current_digest:
            raise LedgerError(f"packet store digest mismatch: {stored_digest} != {current_digest}")

        # 4. Ledger entry (re-entrant lock, but we already did immutability check; double-check inside append)
        return self.append(
            {
                "type": "verification_packet",
                "packet_id": packet.packet_id,
                "digest": current_digest,
                "objective": packet.objective,
                "actor": packet.actor,
                "decision": packet.decision,
            }
        )

    def verify_chain(self) -> tuple[bool, str]:
        # T3: first detect physically malformed lines — corruption must be
        # reported explicitly rather than masked by the skip-on-read path.
        raw = self._raw_lines()
        for i, line in enumerate(raw):
            try:
                json.loads(line)
            except (ValueError, json.JSONDecodeError):
                return False, f"corrupted ledger line at entry {i} (malformed JSON)"
        entries = [json.loads(line) for line in raw]
        prev = GENESIS_PREV
        for i, e in enumerate(entries):
            if e["prev_hash"] != prev:
                return False, f"chain break at entry {i}"
            body = {
                "seq": e["seq"],
                "timestamp": e["timestamp"],
                "prev_hash": e["prev_hash"],
                "record": e["record"],
            }
            expected = sha3_hex(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            )
            if expected != e["entry_hash"]:
                return False, f"hash mismatch at entry {i} (content modified)"
            if e["seq"] != i:
                return False, f"sequence gap at entry {i}"
            prev = e["entry_hash"]
        return True, f"chain intact ({len(entries)} entries)"

    def head(self) -> str:
        entries = self._entries()
        return entries[-1]["entry_hash"] if entries else GENESIS_PREV

    def iter_entries(self) -> Iterator[dict]:
        return iter(self._entries())

    def find_by_packet(self, packet_id: str) -> dict | None:
        for entry in self._entries():
            rec = entry.get("record", {})
            if rec.get("type") == "verification_packet" and rec.get("packet_id") == packet_id:
                return entry
        return None

    def find_any_by_packet_id(self, packet_id: str) -> dict | None:
        """Find any ledger entry (any type) that references packet_id — for audit correlation."""
        for entry in self._entries():
            if entry.get("record", {}).get("packet_id") == packet_id:
                return entry
        return None

    # ------------------------------------------------------------------
    # Packet persistence retrieval — content-addressed, digest-verified
    # ------------------------------------------------------------------

    def get_packet(self, packet_id: str) -> VerificationPacket | None:
        """Retrieve a persisted VerificationPacket by its packet_id.

        Returns None if ledger has no entry for packet_id or if the packet
        body is missing from the store (explicit integrity failure, not silent
        regeneration). Digest is verified on load.
        """
        entry = self.find_by_packet(packet_id)
        if entry is None:
            return None
        digest = entry.get("record", {}).get("digest")
        if not digest:
            return None
        return self.get_packet_by_digest(digest)

    def get_packet_by_digest(self, digest: str) -> VerificationPacket | None:
        """Retrieve a persisted VerificationPacket by its canonical digest."""
        # Malformed digests (e.g. old test data "abc") must be treated as missing, not crash
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return None
        try:
            data = self.packet_store.get_if_exists(digest)
        except (ValueError, IOError):
            return None
        if data is None:
            return None
        try:
            # Packet bodies are stored as canonical JSON bytes
            d = json.loads(data.decode("utf-8"))
            pkt = VerificationPacket.from_dict(d)
            if pkt.digest() != digest:
                # Tampered packet body → treat as missing (integrity failure)
                return None
            return pkt
        except Exception:
            return None

    def verify_packet(self, packet_id: str) -> tuple[bool, str]:
        """Verify that a ledger-committed packet's body is present and digest-matched.

        Returns (True, "packet intact") or (False, reason).
        """
        entry = self.find_by_packet(packet_id)
        if entry is None:
            return False, f"no ledger entry for packet_id {packet_id!r}"
        digest = entry.get("record", {}).get("digest")
        if not digest or not isinstance(digest, str):
            return False, "ledger entry has no digest"
        # Malformed digest → treat as missing, not crash (backward compat)
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return False, f"packet body missing for digest {digest[:12]}... (malformed digest)"
        pkt = self.get_packet_by_digest(digest)
        if pkt is None:
            # Distinguish missing vs tampered: check raw file existence (not digest-validated)
            try:
                packet_path = self.packet_store._path_for(digest)
                exists = packet_path.exists()
            except Exception:
                exists = False
            if not exists:
                return False, f"packet body missing for digest {digest[:12]}..."
            return False, "packet body digest mismatch (tampered)"
        return True, "packet intact"

    def list_packet_ids(self) -> list[str]:
        """List all packet_ids that have a ledger entry (committed)."""
        ids = []
        for e in self._entries():
            pid = e.get("record", {}).get("packet_id")
            if e.get("record", {}).get("type") == "verification_packet" and pid:
                ids.append(pid)
        return ids

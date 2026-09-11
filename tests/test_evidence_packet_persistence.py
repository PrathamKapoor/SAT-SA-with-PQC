"""F1 — Evidence Packet Payload Persistence (content-addressed via ArtifactStore)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from qsmlops.config import PlatformConfig
from qsmlops.evidence.ledger import EvidenceLedger, LedgerError
from qsmlops.evidence.packet import VerificationPacket, SecurityCheck
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression


# ------------------------------------------------------------------ helpers
def _ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger(tmp_path / "ledger.jsonl")


def _pkt(**kw) -> VerificationPacket:
    return VerificationPacket.create(objective=kw.get("objective", "test"), actor=kw.get("actor", "tester"), **{k: v for k, v in kw.items() if k not in ("objective", "actor")})


# ------------------------------------------------------------------ PACKET PERSISTENCE
class TestPacketPersistence:
    def test_packet_is_persisted(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(security_checks=[SecurityCheck(name="a", passed=True)], decision="VERIFIED")
        ledger.append_packet(pkt)
        assert ledger.get_packet(pkt.packet_id) is not None

    def test_packet_survives_restart(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        ledger = EvidenceLedger(path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        # Simulate process restart: new ledger instance on same path
        ledger2 = EvidenceLedger(path)
        loaded = ledger2.get_packet(pkt.packet_id)
        assert loaded is not None
        assert loaded.packet_id == pkt.packet_id

    def test_packet_can_be_retrieved_by_digest(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        loaded = ledger.get_packet_by_digest(pkt.digest())
        assert loaded is not None
        assert loaded.digest() == pkt.digest()

    def test_packet_digest_matches(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        entry = ledger.find_by_packet(pkt.packet_id)
        assert entry["record"]["digest"] == pkt.digest()
        loaded = ledger.get_packet(pkt.packet_id)
        assert loaded.digest() == entry["record"]["digest"]

    def test_packet_is_immutable(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        # Same packet_id with different digest must be rejected
        pkt2 = _pkt(decision="QUARANTINE")
        pkt2.packet_id = pkt.packet_id  # force collision
        assert pkt2.digest() != pkt.digest()
        with pytest.raises(LedgerError) as exc:
            ledger.append_packet(pkt2)
        assert "already exists" in str(exc.value).lower()

    def test_duplicate_packet_same_digest_idempotent(self, tmp_path):
        # Appending the same packet body twice (same id+digest) via store is idempotent,
        # but ledger will create a second entry with same packet_id — we allow it if digest matches?
        # Current design rejects any second append with same id (even same digest) to enforce packet_id uniqueness.
        # This is intentional for immutability: packet_id is unique. So second append should fail.
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        with pytest.raises(LedgerError):
            ledger.append_packet(pkt)


# ------------------------------------------------------------------ INTEGRITY
class TestPacketIntegrity:
    def test_modified_packet_rejected(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        digest = pkt.digest()
        path = ledger.packet_store._path_for(digest)
        # Tamper: overwrite with different JSON that still parses but has different content
        tampered = json.loads(path.read_bytes())
        tampered["decision"] = "QUARANTINE"
        from qsmlops.crypto.hashing import canonical_json
        path.write_bytes(json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode())
        # Retrieval should fail digest check
        assert ledger.get_packet(pkt.packet_id) is None
        ok, msg = ledger.verify_packet(pkt.packet_id)
        assert ok is False
        assert "tampered" in msg.lower() or "mismatch" in msg.lower()

    def test_mismatched_digest_rejected(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        # Manually corrupt the stored file's name vs content by writing to wrong digest path
        # Instead, directly test get_packet_by_digest with wrong digest
        ledger.append_packet(pkt)
        # Query with a digest that doesn't exist
        assert ledger.get_packet_by_digest("0" * 64) is None
        assert ledger.get_packet_by_digest("bad-digest") is None

    def test_missing_packet_detected(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        # Delete file
        ledger.packet_store._path_for(pkt.digest()).unlink()
        assert ledger.get_packet(pkt.packet_id) is None
        ok, msg = ledger.verify_packet(pkt.packet_id)
        assert ok is False
        assert "missing" in msg.lower()

    def test_corrupted_packet_detected(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        p = ledger.packet_store._path_for(pkt.digest())
        p.write_bytes(b"not json at all")
        assert ledger.get_packet(pkt.packet_id) is None
        ok, msg = ledger.verify_packet(pkt.packet_id)
        assert ok is False

    def test_malformed_ledger_packet_id(self, tmp_path):
        ledger = _ledger(tmp_path)
        assert ledger.get_packet("nonexistent") is None
        ok, msg = ledger.verify_packet("nonexistent")
        assert ok is False

    def test_historical_entry_without_packet_still_verifies_chain(self, tmp_path):
        # Simulate pre-F1 ledger entry created via plain append (no packet body)
        ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
        old = ledger.append({"type": "verification_packet", "packet_id": "old", "digest": "a" * 64, "objective": "old", "actor": "a", "decision": "VERIFIED"})
        # Chain must still be intact
        ok, msg = ledger.verify_chain()
        assert ok is True
        # Packet retrieval should be missing, not crash
        assert ledger.get_packet("old") is None


# ------------------------------------------------------------------ LEDGER
class TestLedgerIntegration:
    def test_ledger_chain_remains_valid(self, tmp_path):
        ledger = _ledger(tmp_path)
        for i in range(5):
            pkt = _pkt(objective=f"obj{i}", decision="VERIFIED")
            ledger.append_packet(pkt)
        ok, msg = ledger.verify_chain()
        assert ok is True
        assert "5 entries" in msg

    def test_packet_reference_committed(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        entry = ledger.append_packet(pkt)
        assert entry["record"]["packet_id"] == pkt.packet_id
        assert entry["record"]["digest"] == pkt.digest()
        assert entry["record"]["type"] == "verification_packet"

    def test_historical_entries_remain_valid(self, tmp_path):
        ledger = _ledger(tmp_path)
        # Mix of old-style plain appends and new packet appends
        ledger.append({"type": "state_transition", "version_id": "v1", "from": "REGISTERED", "to": "VERIFIED", "reason": "test"})
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        ledger.append({"type": "approval_denied", "version_id": "v1", "reason": "x"})
        ok, _ = ledger.verify_chain()
        assert ok is True
        # Old entries still readable
        entries = list(ledger.iter_entries())
        assert len(entries) == 3

    def test_list_packet_ids(self, tmp_path):
        ledger = _ledger(tmp_path)
        ids = []
        for _ in range(3):
            pkt = _pkt(decision="VERIFIED")
            ledger.append_packet(pkt)
            ids.append(pkt.packet_id)
        listed = ledger.list_packet_ids()
        assert set(listed) == set(ids)


# ------------------------------------------------------------------ SECURITY
class TestPacketSecurity:
    def test_secrets_not_persisted(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.inputs = {"safe": "value"}
        # Inject sensitive field
        pkt.proofs = {"hsm_pin": "1234"}
        with pytest.raises(LedgerError) as exc:
            ledger.append_packet(pkt)
        assert "sensitive" in str(exc.value).lower()

    def test_private_key_not_persisted(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.proofs = {"private_key": "deadbeef"}
        with pytest.raises(LedgerError):
            ledger.append_packet(pkt)

    def test_passphrase_not_persisted(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.inputs = {"passphrase": "secret"}
        with pytest.raises(LedgerError):
            ledger.append_packet(pkt)

    def test_nested_sensitive_rejected(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.metrics = {"nested": {"secret_key": "abc"}}
        with pytest.raises(LedgerError):
            ledger.append_packet(pkt)

    def test_normal_packet_passes_sensitive_check(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.proofs = {"suite_id": "QS", "signer_key_id": "k1"}
        pkt.metrics = {"r2": 0.9}
        # Should not raise
        ledger.append_packet(pkt)
        assert ledger.get_packet(pkt.packet_id) is not None


# ------------------------------------------------------------------ COMPATIBILITY
class TestCompatibility:
    def test_old_ledger_file_still_loads(self, tmp_path):
        # Create a ledger file with old entries (pre-F1) and ensure new code loads it
        ledger_path = tmp_path / "ledger.jsonl"
        # Write raw old-style entries directly
        import json as _json
        from qsmlops.crypto.hashing import sha3_hex
        genesis = "0" * 64
        for i in range(2):
            body = {"seq": i, "timestamp": 1000 + i, "prev_hash": genesis if i == 0 else "prev", "record": {"type": "state_transition", "version_id": "v1"}}
            # Compute hash correctly for test
            h = sha3_hex(_json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
            entry = {**body, "entry_hash": h}
            genesis = h
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
        ledger = EvidenceLedger(ledger_path)
        # Should verify (or at least not crash) — chain may be broken due to fake prev, but loading should work
        entries = list(ledger.iter_entries())
        assert len(entries) == 2

    def test_demo_still_works(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QSMLOPS_HOME", str(tmp_path / "home"))
        from qsmlops.pipeline.selfheal import SelfHealingMLOps
        from qsmlops.config import PlatformConfig
        config = PlatformConfig(tmp_path / "home")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(80, seed=1)
        pipe.provision_dataset("d", ds)
        r = pipe.train_and_register("m", "d")
        assert "version_id" in r
        pipe.close()


# ------------------------------------------------------------------ INTEGRATION
class TestIntegration:
    def test_verification_to_ledger_to_retrieval(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QSMLOPS_HOME", str(tmp_path / "home"))
        from qsmlops.config import PlatformConfig

        config = PlatformConfig(tmp_path / "home")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(100, seed=2)
        pipe.provision_dataset("idata", ds)
        r = pipe.train_and_register("model-int", "idata")
        vid = r["version_id"]
        # Verification creates a packet and persists it
        packet = pipe.registry.verify_version(vid, verifier_owner="verifier", checks=[("dummy", True)])
        assert packet.packet_id is not None
        # Ledger must have packet
        loaded = pipe.ledger.get_packet(packet.packet_id)
        assert loaded is not None
        assert loaded.decision == packet.decision
        # Ledger chain must be intact
        ok, _ = pipe.ledger.verify_chain()
        assert ok is True
        # Packet digest must match ledger entry
        entry = pipe.ledger.find_by_packet(packet.packet_id)
        assert entry["record"]["digest"] == packet.digest()
        # Tamper detection: modify stored file and verify fails
        digest = packet.digest()
        ppath = pipe.ledger.packet_store._path_for(digest)
        orig = ppath.read_bytes()
        ppath.write_bytes(b"bad")
        assert pipe.ledger.get_packet(packet.packet_id) is None
        ppath.write_bytes(orig)
        assert pipe.ledger.get_packet(packet.packet_id) is not None
        pipe.close()

    def test_registry_uses_persisted_packets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QSMLOPS_HOME", str(tmp_path / "home"))
        config = PlatformConfig(tmp_path / "home")
        pipe = SelfHealingMLOps(config)
        ds = make_synthetic_regression(100, seed=3)
        pipe.provision_dataset("d2", ds)
        r = pipe.train_and_register("rmodel", "d2")
        vid = r["version_id"]
        packet = pipe.registry.verify_version(vid, verifier_owner="v", checks=[("a", True)])
        # Registry's verify_version already called ledger.append_packet, so packet should be retrievable
        assert pipe.ledger.get_packet(packet.packet_id) is not None
        pipe.close()


# ------------------------------------------------------------------ ADVERSARIAL
class TestAdversarial:
    def test_packet_mutation_after_persistence(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        # Mutate in-memory packet after persistence should not affect stored body
        pkt.decision = "QUARANTINE"
        reloaded = ledger.get_packet(pkt.packet_id)
        assert reloaded.decision == "VERIFIED"

    def test_digest_substitution(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        # Try to fetch via wrong digest
        assert ledger.get_packet_by_digest("f" * 64) is None

    def test_packet_deletion(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        digest = pkt.digest()
        ledger.packet_store._path_for(digest).unlink()
        ok, _ = ledger.verify_packet(pkt.packet_id)
        assert ok is False

    def test_truncated_payload(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        ledger.append_packet(pkt)
        p = ledger.packet_store._path_for(pkt.digest())
        data = p.read_bytes()
        p.write_bytes(data[:10])
        assert ledger.get_packet(pkt.packet_id) is None

    def test_wrong_model_binding(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.inputs = {"version_id": "v1"}
        ledger.append_packet(pkt)
        loaded = ledger.get_packet(pkt.packet_id)
        assert loaded.inputs["version_id"] == "v1"
        # An attacker cannot claim it was for v2 without changing packet_id/digest
        assert loaded.packet_id == pkt.packet_id

    def test_wrong_signer_identity(self, tmp_path):
        ledger = _ledger(tmp_path)
        pkt = _pkt(decision="VERIFIED")
        pkt.proofs = {"signer_key_id": "alice-ML-DSA-87-abc"}
        ledger.append_packet(pkt)
        loaded = ledger.get_packet(pkt.packet_id)
        assert loaded.proofs["signer_key_id"] == "alice-ML-DSA-87-abc"

    def test_concurrent_append_packet_ids(self, tmp_path):
        # Simulate concurrent appends: two packets with different ids
        ledger = _ledger(tmp_path)
        pkts = [_pkt(decision="VERIFIED") for _ in range(5)]
        for pkt in pkts:
            ledger.append_packet(pkt)
        assert len(ledger.list_packet_ids()) == 5
        ok, _ = ledger.verify_chain()
        assert ok is True

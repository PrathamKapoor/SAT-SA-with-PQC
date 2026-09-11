"""Tests for crypto layer: hashing, providers, keys, agility."""
from __future__ import annotations

import pytest

from qsmlops.crypto.hashing import canonical_json, sha3_hex
from qsmlops.crypto.providers import (
    MLDSA44Provider,
    MLDSA65Provider,
    MLDSA87Provider,
    MLKEM512Provider,
    MLKEM768Provider,
    MLKEM1024Provider,
    SIGNATURE_PROVIDERS,
    KEM_PROVIDERS,
)
from qsmlops.crypto.keys import KeyStore
from qsmlops.crypto.agility import AgilityEngine


def test_sha3_hex_deterministic():
    assert sha3_hex(b"hello") == sha3_hex(b"hello")
    assert len(sha3_hex(b"x")) == 64


def test_canonical_json_deterministic():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_json(a) == canonical_json(b)


def test_all_signature_providers():
    for provider in (MLDSA44Provider, MLDSA65Provider, MLDSA87Provider):
        p = provider()
        kp = p.generate_keypair()
        assert kp.algorithm_id == p.algorithm_id
        assert len(kp.public_key) > 0
        assert len(kp.secret_key) > 0
        msg = b"test message"
        sig = p.sign(kp.secret_key, msg)
        assert p.verify(kp.public_key, msg, sig) is True
        assert p.verify(kp.public_key, b"tampered", sig) is False
        assert p.verify(b"wrongpk", msg, sig) is False


def test_all_kem_providers():
    for provider in (MLKEM512Provider, MLKEM768Provider, MLKEM1024Provider):
        p = provider()
        kp = p.generate_keypair()
        assert kp.algorithm_id == p.algorithm_id
        ss1, ct = p.encapsulate(kp.public_key)
        ss2 = p.decapsulate(kp.secret_key, ct)
        assert ss1 == ss2
        assert len(ss1) > 0
        assert len(ct) > 0


def test_signature_provider_registry():
    assert set(SIGNATURE_PROVIDERS.keys()) == {"ML-DSA-44", "ML-DSA-65", "ML-DSA-87"}


def test_kem_provider_registry():
    assert set(KEM_PROVIDERS.keys()) == {"ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"}


def test_keystore_generate_and_list(tmp_path):
    ks = KeyStore(tmp_path / "keys")
    kp = ks.generate_keypair("SIGNER", "ML-DSA-65", owner="tester")
    records = ks.list_records(role="SIGNER")
    assert len(records) == 1
    assert records[0].role == "SIGNER"
    assert records[0].owner == "tester"
    assert records[0].algorithm_id == "ML-DSA-65"
    key_id = records[0].key_id


def test_keystore_rotation(tmp_path):
    ks = KeyStore(tmp_path / "keys")
    ks.generate_keypair("SIGNER", "ML-DSA-65", owner="alice")
    recs_before = ks.list_records(role="SIGNER", include_inactive=True)
    key_id1 = [r for r in recs_before if r.owner == "alice" and r.status == "active"][0].key_id
    new_key_id = ks.rotate_signer("alice", new_algorithm_id="ML-DSA-65")
    recs_after = ks.list_records(role="SIGNER", include_inactive=True)
    rec1 = ks.get_record(key_id1)
    rec2 = ks.get_record(new_key_id)
    assert rec1.status == "rotated"
    assert rec2.status == "active"
    assert rec2.version == 2


def test_keystore_revocation(tmp_path):
    ks = KeyStore(tmp_path / "keys")
    ks.generate_keypair("SIGNER", "ML-DSA-65", owner="bob")
    recs = ks.list_records(role="SIGNER")
    key_id = recs[0].key_id
    ks.revoke(key_id)
    with pytest.raises(Exception):
        ks.trusted_public_key(key_id)


def test_agility_engine_suites():
    ae = AgilityEngine()
    assert ae.default_suite is not None
    suite = ae.select_suite()
    assert suite.signature_algorithm in SIGNATURE_PROVIDERS
    assert suite.kem_algorithm in KEM_PROVIDERS
    assert suite.hash_algorithm == "sha3-256"


def test_agility_assert_usable():
    ae = AgilityEngine()
    suite = ae.select_suite()
    ae.assert_usable(suite)
    ae.mark_deprecated(suite.suite_id)
    # re-fetch to get updated status
    updated = ae.get_suite(suite.suite_id)
    with pytest.raises(Exception):
        ae.assert_usable(updated)


def test_agility_migration_plan():
    ae = AgilityEngine()
    src = ae.select_suite()
    plan = ae.plan_migration(src.suite_id)
    assert plan.from_suite == src.suite_id
    assert len(plan.steps) >= 4


def test_agility_audit_inventory():
    ae = AgilityEngine()
    inventory = {"QS-3ML-KEM-768+ML-DSA-65": 5, "QS-1ML-KEM-512+ML-DSA-44": 2}
    report = ae.audit_inventory(inventory)
    assert all(k in report for k in inventory)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
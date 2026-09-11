"""Gate-D keystore remediation tests.

Proves the security prerequisite "default production path uses the
encrypted keystore":

1. setting QSMLOPS_KEYSTORE_PASSPHRASE routes the platform through
   EncryptedKeyStore (vault created, plaintext secret_keys.json absent);
2. key retrieval / signing / verification work through the encrypted path,
   including across a reopen with the same passphrase;
3. wrong passphrase fails closed (VaultError);
4. unset passphrase preserves the legacy development behavior unchanged.
"""
from __future__ import annotations

import pytest

from qsmlops.config import PlatformConfig
from qsmlops.crypto.secure_keystore import VaultError
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression


def _build(tmp_path, monkeypatch, passphrase):
    if passphrase is None:
        monkeypatch.delenv("QSMLOPS_KEYSTORE_PASSPHRASE", raising=False)
    else:
        monkeypatch.setenv("QSMLOPS_KEYSTORE_PASSPHRASE", passphrase)
    config = PlatformConfig(tmp_path / f"ks_{passphrase or 'legacy'}")
    return SelfHealingMLOps(config), config


class TestEncryptedDefaultPath:
    def test_passphrase_routes_to_vault_and_removes_plaintext(self, tmp_path, monkeypatch):
        pipe, config = _build(tmp_path, monkeypatch, "correct horse battery")
        ds = make_synthetic_regression(120, seed=7)
        pipe.provision_dataset("kd", ds)
        result = pipe.train_and_register("secure-model", "kd")
        evaluation = pipe.evaluate_version(result["version_id"])
        assert evaluation["decision"] == "VERIFIED"

        keys_dir = config.keys_dir
        assert (keys_dir / "secret_keys.vault").exists()
        assert not (keys_dir / "secret_keys.json").exists()
        assert not (keys_dir / "secret_keys.tmp.json").exists()

        passport = pipe.registry.load_passport(result["version_id"])
        assert passport.verify_signature(pipe.keystore) is True
        pipe.close()

    def test_reopen_with_same_passphrase_recovers_keys(self, tmp_path, monkeypatch):
        pipe, config = _build(tmp_path, monkeypatch, "stable-passphrase")
        ds = make_synthetic_regression(80, seed=3)
        pipe.provision_dataset("rd", ds)
        first = pipe.train_and_register("reopen-model", "rd")
        key_id_before = pipe.registry.load_passport(first["version_id"]).signature.signer_key_id
        pipe.close()

        pipe2 = SelfHealingMLOps(config)
        key_id_after, secret = pipe2.keystore.active_signing_key("producer")
        assert key_id_after == key_id_before
        assert secret
        passport = pipe2.registry.load_passport(first["version_id"])
        assert passport.verify_signature(pipe2.keystore) is True
        assert not (config.keys_dir / "secret_keys.json").exists()
        pipe2.close()

    def test_wrong_passphrase_fails_closed(self, tmp_path, monkeypatch):
        _pipe, config = _build(tmp_path, monkeypatch, "right-passphrase")
        from qsmlops.pipeline.selfheal import SelfHealingMLOps as SH

        monkeypatch.setenv("QSMLOPS_KEYSTORE_PASSPHRASE", "wrong-passphrase")
        with pytest.raises(VaultError):
            SH(config)

    def test_legacy_mode_unchanged_when_unset(self, tmp_path, monkeypatch):
        pipe, config = _build(tmp_path, monkeypatch, None)
        ds = make_synthetic_regression(60, seed=5)
        pipe.provision_dataset("ld", ds)
        result = pipe.train_and_register("legacy-model", "ld")
        # legacy development behavior: plaintext store present, vault absent
        assert (config.keys_dir / "secret_keys.json").exists()
        assert not (config.keys_dir / "secret_keys.vault").exists()
        passport = pipe.registry.load_passport(result["version_id"])
        assert passport.verify_signature(pipe.keystore) is True
        pipe.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

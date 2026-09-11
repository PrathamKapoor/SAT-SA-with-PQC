"""Encrypted keystore: at-rest protection for secret key material.

Design:
- Secret keys are sealed in a single encrypted vault file per KeyStore
  directory using AES-256-GCM (AEAD; confidentiality + tamper detection).
- The vault key is derived from an operator passphrase via PBKDF2-HMAC-SHA3-256
  with a per-vault random salt and configurable iteration count.
- The GCM nonce is random per save; the associated data binds the vault
  format version so ciphertexts cannot be replayed across formats.
- Plaintext secrets never touch disk; the legacy plaintext `secret_keys.json`
  is removed when a vault is initialized over it.

Threat model: protects against disk theft / backup leakage of secret signing
keys. It does NOT protect against a compromised running process (the unlocked
key material lives in process memory) — standard for software keystores.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from qsmlops.crypto.keys import KeyStore, STATUS_ACTIVE

VAULT_VERSION = 1
DEFAULT_ITERATIONS = 600_000
_SALT_LEN = 32
_NONCE_LEN = 12
_KEY_LEN = 32


class KeystoreLockedError(Exception):
    pass


class VaultError(Exception):
    pass


def _derive_vault_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA3_256(),
        length=_KEY_LEN,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _open(doc: dict, passphrase: str) -> bytes:
    salt = bytes.fromhex(doc["salt_hex"])
    nonce = bytes.fromhex(doc["nonce_hex"])
    ct = bytes.fromhex(doc["ciphertext_hex"])
    aad = f"qsmlops-vault-v{doc.get('version', 1)}".encode()
    kek = _derive_vault_key(passphrase, salt, int(doc["iterations"]))
    try:
        return AESGCM(kek).decrypt(nonce, ct, aad)
    except InvalidTag as exc:
        raise VaultError("wrong passphrase or corrupted vault") from exc


class EncryptedKeyStore(KeyStore):
    """A KeyStore whose secret-key file is an encrypted AEAD vault.
    
    Supports HSM-backed keys where secret key material never leaves the HSM.
    """

    def __init__(
        self,
        keys_dir: Path,
        passphrase: str | None = None,
        iterations: int = DEFAULT_ITERATIONS,
        hsm_backend=None,
    ) -> None:
        self._iterations = iterations
        super().__init__(keys_dir, hsm_backend=hsm_backend)
        self._vault_path = self.keys_dir / "secret_keys.vault"
        self._secrets_cache: dict | None = None
        self._last_passphrase: str | None = None
        legacy_path = self.keys_dir / "secret_keys.json"
        if not self._vault_path.exists():
            # migrate any legacy plaintext secrets into the new vault
            plaintext = (
                legacy_path.read_text(encoding="utf-8") if legacy_path.exists() else "{}"
            )
            if passphrase is None:
                raise VaultError(
                    "no vault found and no passphrase provided to create one"
                )
            self._create_vault(passphrase, initial_plaintext=plaintext)
        # Remove the plaintext secret file immediately: the base-class
        # constructor materializes one, and it must never outlive this
        # constructor even if a later step (e.g. unlock) raises.
        if legacy_path.exists():
            legacy_path.unlink()
        if passphrase is not None:
            self.unlock(passphrase)

    # ---------------- vault management ----------------
    def _create_vault(self, passphrase: str, initial_plaintext: str = "{}") -> None:
        salt = secrets.token_bytes(_SALT_LEN)
        nonce = secrets.token_bytes(_NONCE_LEN)
        kek = _derive_vault_key(passphrase, salt, self._iterations)
        aad = f"qsmlops-vault-v{VAULT_VERSION}".encode()
        ct = AESGCM(kek).encrypt(nonce, initial_plaintext.encode("utf-8"), aad)
        doc = {
            "version": VAULT_VERSION,
            "kdf": "PBKDF2-HMAC-SHA3-256",
            "iterations": self._iterations,
            "salt_hex": salt.hex(),
            "nonce_hex": nonce.hex(),
            "ciphertext_hex": ct.hex(),
        }
        self._vault_path.write_text(
            json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
        )

    def unlock(self, passphrase: str) -> bool:
        """Decrypt the vault into memory; raises on wrong passphrase."""
        doc = json.loads(self._vault_path.read_text(encoding="utf-8"))
        self._secrets_cache = json.loads(_open(doc, passphrase).decode("utf-8"))
        self._last_passphrase = passphrase
        return True

    def lock(self) -> None:
        self._secrets_cache = None

    @property
    def is_locked(self) -> bool:
        return self._secrets_cache is None

    def change_passphrase(self, old: str, new: str) -> None:
        self.unlock(old)
        self._persist_secrets(new)
        self._last_passphrase = new

    def _ensure_unlocked(self) -> dict:
        if getattr(self, "_secrets_cache", None) is None:
            raise KeystoreLockedError(
                "keystore is locked; call unlock(passphrase) first"
            )
        return self._secrets_cache

    def _persist_secrets(self, passphrase: str | None = None) -> None:
        cache = self._ensure_unlocked()
        pw = passphrase or self._last_passphrase
        if pw is None:
            raise KeystoreLockedError("passphrase required to persist vault")
        self._last_passphrase = pw
        payload = json.dumps(cache, sort_keys=True).encode("utf-8")
        salt = secrets.token_bytes(_SALT_LEN)
        nonce = secrets.token_bytes(_NONCE_LEN)
        kek = _derive_vault_key(pw, salt, self._iterations)
        aad = f"qsmlops-vault-v{VAULT_VERSION}".encode()
        ct = AESGCM(kek).encrypt(nonce, payload, aad)
        doc = {
            "version": VAULT_VERSION,
            "kdf": "PBKDF2-HMAC-SHA3-256",
            "iterations": self._iterations,
            "salt_hex": salt.hex(),
            "nonce_hex": nonce.hex(),
            "ciphertext_hex": ct.hex(),
        }
        self._vault_path.write_text(
            json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
        )

    # ---------------- overridden persistence ----------------
    def generate_keypair(self, role, algorithm_id, owner="", lifetime_days=None):
        if self.is_locked:
            raise KeystoreLockedError(
                "cannot generate keys while keystore is locked; unlock first"
            )
        # The base class expects its plaintext store. Materialize the current
        # unlocked secrets into a temporary plaintext file and point the base
        # class at it, so the official ``secret_keys.json`` never exists on
        # disk at any point during the operation.
        temp_path = self.keys_dir / "secret_keys.tmp.json"
        temp_path.write_text(
            json.dumps(self._ensure_unlocked(), sort_keys=True), encoding="utf-8"
        )
        original_secrets_path = self._secrets_path
        self._secrets_path = temp_path
        try:
            kp = super().generate_keypair(
                role, algorithm_id, owner=owner, lifetime_days=lifetime_days
            )
            # Reload the updated map (including the new secret) into cache.
            self._secrets_cache = json.loads(temp_path.read_text(encoding="utf-8"))
        finally:
            self._secrets_path = original_secrets_path
            # Remove both the temporary and any official plaintext files.
            if temp_path.exists():
                temp_path.unlink()
            official_path = self.keys_dir / "secret_keys.json"
            if official_path.exists():
                official_path.unlink()
        self._persist_secrets()
        return kp

    def active_signing_key(self, owner: str) -> tuple[str, bytes]:
        recs = [
            r
            for r in self.list_records(role="SIGNER")
            if r.owner == owner and r.status == STATUS_ACTIVE
        ]
        if not recs:
            raise ProviderError(f"no active signing key for {owner!r}")
        key_id = recs[0].key_id
        if recs[0].hsm_backed:
            raise ProviderError(f"active signing key {key_id} is HSM-backed; use HSM backend directly")
        sk_hex = self._ensure_unlocked()[key_id]["secret_key_hex"]
        return key_id, bytes.fromhex(sk_hex)

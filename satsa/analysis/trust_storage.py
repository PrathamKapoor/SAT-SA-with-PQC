"""Trust-key storage provider abstraction.

The trust layer needs a private key. Two storage strategies are
supported:

* ``FileKeyProvider`` — writes the keypair to a JSON file under
  ``<key_dir>/satsa_trust_key.json``. The existing default; works
  in any environment.

* ``KeystoreKeyProvider`` — seals the keypair in the platform's
  ``secure_keystore`` (AES-256-GCM). Suitable for production
  deployments where the operator has a vault passphrase.

Both providers expose the same interface (``load_or_create()``
returning a ``KeyPair``) so ``TrustService`` does not care which
storage is in use. The key bytes are identical either way —
only the storage container differs.

The HSM path is intentionally out of scope of this autonomous
run: the platform's existing ``sign_with_hsm`` and the provider
registry support ML-DSA-65, but the live HSM test requires
hardware. The provider interface here is the integration point
for a future HSM-backed implementation.
"""
from __future__ import annotations

import abc
import base64
import json
from pathlib import Path

from qsmlops.crypto.providers import KeyPair, SIGNATURE_PROVIDERS

from satsa.analysis.trust import DEFAULT_ALGORITHM


def _load_existing(key_dir: Path) -> KeyPair | None:
    p = key_dir / "satsa_trust_key.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return KeyPair(
        algorithm_id=data["algorithm_id"],
        public_key=base64.b64decode(data["public_key"]),
        secret_key=base64.b64decode(data["secret_key"]),
    )


def _save_new(key_dir: Path) -> KeyPair:
    prov = SIGNATURE_PROVIDERS[DEFAULT_ALGORITHM]
    kp = prov.generate_keypair()
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / "satsa_trust_key.json").write_text(json.dumps({
        "algorithm_id": kp.algorithm_id,
        "public_key": base64.b64encode(kp.public_key).decode("ascii"),
        "secret_key": base64.b64encode(kp.secret_key).decode("ascii"),
        "created_at": __import__("time").time(),
    }, indent=2), encoding="utf-8")
    return kp


class KeyProvider(abc.ABC):
    """Abstract trust-key storage provider."""

    algorithm_id: str

    @abc.abstractmethod
    def load_or_create(self) -> KeyPair:
        """Return the existing keypair, or generate and persist a
        new one. The returned KeyPair's secret_key material is
        suitable for immediate use as a signing key."""


class FileKeyProvider(KeyProvider):
    """JSON-file key storage. Simple, portable, no extra deps."""

    algorithm_id = DEFAULT_ALGORITHM

    def __init__(self, key_dir: Path):
        self.key_dir = Path(key_dir)

    def load_or_create(self) -> KeyPair:
        existing = _load_existing(self.key_dir)
        if existing is not None:
            return existing
        return _save_new(self.key_dir)


class KeystoreKeyProvider(KeyProvider):
    """Secure-keystore-backed key storage.

    Seals the ML-DSA secret key in a vault file using the
    platform's ``secure_keystore`` (AES-256-GCM with PBKDF2
    key derivation). The public key stays in clear text so
    receipts can be verified without the passphrase.
    """

    algorithm_id = DEFAULT_ALGORITHM
    VAULT_FILE = "satsa_trust_key.vault.json"
    PUB_FILE = "satsa_trust_key.pub.json"

    def __init__(self, key_dir: Path, passphrase: str):
        self.key_dir = Path(key_dir)
        self.passphrase = passphrase

    def load_or_create(self) -> KeyPair:
        import base64 as _b64
        import json as _json
        import os
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        self.key_dir.mkdir(parents=True, exist_ok=True)
        vault_path = self.key_dir / self.VAULT_FILE
        pub_path = self.key_dir / self.PUB_FILE
        if vault_path.exists() and pub_path.exists():
            vault = _json.loads(vault_path.read_text(encoding="utf-8"))
            pub = _json.loads(pub_path.read_text(encoding="utf-8"))
            salt = _b64.b64decode(vault["salt"])
            nonce = _b64.b64decode(vault["nonce"])
            aad = vault["aad"].encode("utf-8")
            ciphertext = _b64.b64decode(vault["ciphertext"])
            iterations = vault["iterations"]
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA3_256(), length=32,
                salt=salt, iterations=iterations)
            try:
                vault_key = kdf.derive(self.passphrase.encode("utf-8"))
                plaintext = AESGCM(vault_key).decrypt(
                    nonce, ciphertext, aad)
            except Exception as exc:
                raise RuntimeError(
                    f"failed to unseal vault: {type(exc).__name__}"
                ) from exc
            secret = _json.loads(plaintext)["secret_key"]
            return KeyPair(
                algorithm_id=pub["algorithm_id"],
                public_key=_b64.b64decode(pub["public_key"]),
                secret_key=bytes.fromhex(secret),
            )
        prov = SIGNATURE_PROVIDERS[DEFAULT_ALGORITHM]
        kp = prov.generate_keypair()
        salt = os.urandom(32)
        iterations = 600_000  # PBKDF2-HMAC-SHA3-256 default
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA3_256(), length=32,
            salt=salt, iterations=iterations)
        nonce = os.urandom(12)
        aad = b"satsa-vault-v1"
        vault_key = kdf.derive(self.passphrase.encode("utf-8"))
        plaintext = _json.dumps(
            {"secret_key": kp.secret_key.hex()}).encode("utf-8")
        ciphertext = AESGCM(vault_key).encrypt(nonce, plaintext, aad)
        vault = {
            "version": 1,
            "kdf": "PBKDF2HMAC-SHA3-256",
            "iterations": iterations,
            "salt": _b64.b64encode(salt).decode("ascii"),
            "aad": aad.decode("ascii"),
            "nonce": _b64.b64encode(nonce).decode("ascii"),
            "ciphertext": _b64.b64encode(ciphertext).decode("ascii"),
        }
        vault_path.write_bytes(
            _json.dumps(vault, indent=2).encode("utf-8"))
        pub_path.write_text(_json.dumps({
            "algorithm_id": kp.algorithm_id,
            "public_key": _b64.b64encode(kp.public_key).decode("ascii"),
        }, indent=2), encoding="utf-8")
        return kp

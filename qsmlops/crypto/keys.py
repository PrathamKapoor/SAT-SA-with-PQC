"""Key management: versioned keystore with roles, rotation, revocation,
expiry and rotation automation.

Trust anchors are stored as public keys with metadata. Secret keys are kept
separately (never in the trust anchor table) and are only used by local
operations such as signing passports.

Phase 2: keys carry an optional expiry timestamp; expired keys cannot verify
signatures or sign new material, and `rotate_due_keys` automates rotation.
For at-rest protection of secret keys use EncryptedKeyStore
(qsmlops.crypto.secure_keystore).

Phase 3 (Workstream A1): HSM backend integration for hardware-backed keys.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from qsmlops.crypto.providers import (
    KEM_PROVIDERS,
    SIGNATURE_PROVIDERS,
    KeyPair,
    ProviderError,
)
from qsmlops.crypto.hsm import HSMBackend, HSMKeyInfo, create_hsm_backend

ROLES = ("SIGNER", "VERIFIER", "KEM", "REDACTED")
STATUS_ACTIVE = "active"
STATUS_ROTATED = "rotated"
STATUS_REVOKED = "revoked"
STATUS_EXPIRED = "expired"


@dataclass
class KeyRecord:
    key_id: str
    role: str
    algorithm_id: str
    public_key_hex: str
    created_at: float
    version: int
    status: str = STATUS_ACTIVE
    owner: str = ""
    expires_at: Optional[float] = None  # unix ts; None = no expiry
    hsm_backed: bool = False  # True if key is stored in HSM

    def to_dict(self) -> dict:
        return asdict(self)

    def is_expired(self, now: float | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now if now is not None else time.time()) >= self.expires_at

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400.0

    def lifetime_days(self) -> float | None:
        return ((self.expires_at - self.created_at) / 86400.0) if self.expires_at else None


@dataclass
class SecretKeyRecord:
    key_id: str
    secret_key_hex: str


class KeyStore:
    """File-backed, versioned key store with trust-anchor semantics.

    Supports both software-backed keys (default) and HSM-backed keys
    when an HSM backend is configured.
    """

    def __init__(
        self, keys_dir: Path, hsm_backend: Optional["HSMBackend"] = None
    ) -> None:
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self._anchors_path = self.keys_dir / "trust_anchors.json"
        self._secrets_path = self.keys_dir / "secret_keys.json"
        if not self._anchors_path.exists():
            self._write_json(self._anchors_path, {})
        if not self._secrets_path.exists():
            self._write_json(self._secrets_path, {})

        # HSM backend for hardware-backed keys
        self._hsm = create_hsm_backend({"use_hsm": hsm_backend is not None}) if hsm_backend is None else hsm_backend

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, obj: dict) -> None:
        path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

    def _get_provider(self, role: str, algorithm_id: str):
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        providers = (
            SIGNATURE_PROVIDERS if role in ("SIGNER", "VERIFIER") else KEM_PROVIDERS
        )
        provider = providers.get(algorithm_id)
        if provider is None:
            raise ProviderError(f"no provider for {algorithm_id}")
        return provider

    def generate_keypair(
        self, role: str, algorithm_id: str, owner: str = "",
        lifetime_days: Optional[float] = None,
    ) -> "KeyPair":
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        provider = self._get_provider(role, algorithm_id)
        if provider is None:
            raise ProviderError(f"no provider for {algorithm_id}")

        # Determine whether HSM is explicitly requested (PKCS11Backend vs software fallback).
        # Only an explicit PKCS11Backend should drive HSM generation and fail-closed
        # semantics; software fallback must never pretend to be HSM-backed.
        is_explicit_hsm = False
        try:
            # Lazy import to avoid circular dependency at module load
            from qsmlops.crypto.hsm import PKCS11Backend  # type: ignore
            is_explicit_hsm = isinstance(self._hsm, PKCS11Backend)
        except Exception:
            is_explicit_hsm = type(self._hsm).__name__ == "PKCS11Backend"

        if is_explicit_hsm:
            # Fail-closed: any HSM failure propagates, never silently falls back
            if role in ("SIGNER", "VERIFIER"):
                key_info = self._hsm.generate_signature_keypair(
                    algorithm=algorithm_id,
                    key_id=f"{owner or 'signer'}-{algorithm_id}-{secrets.token_hex(4)}",
                    label=f"{owner}-{algorithm_id}",
                    owner=owner,
                )
            else:
                key_info = self._hsm.generate_kem_keypair(
                    algorithm=algorithm_id,
                    key_id=f"{owner or 'kem'}-{algorithm_id}-{secrets.token_hex(4)}",
                    label=f"{owner}-{algorithm_id}",
                    owner=owner,
                )
            key_id = key_info.key_id
            hsm_backed = True
            public_key_hex = key_info.public_key_hex
            # For HSM keys, private material never leaves the HSM boundary
            kp = None  # type: ignore
        else:
            # Software fallback path — HSM is intentionally disabled; use software provider
            kp = self._get_provider(role, algorithm_id).generate_keypair()
            key_id = f"{owner or 'signer'}-{algorithm_id}-{secrets.token_hex(4)}"
            hsm_backed = False
            public_key_hex = kp.public_key.hex()

        anchors = self._read_json(self._anchors_path)
        current_version = 1 + max(
            (
                rec["version"]
                for rec in anchors.values()
                if rec["role"] == role and rec["owner"] == owner
                and rec["status"] != STATUS_REVOKED
            ),
            default=0,
        )
        now = time.time()
        record = KeyRecord(
            key_id=key_id,
            role=role,
            algorithm_id=algorithm_id,
            public_key_hex=public_key_hex,
            created_at=now,
            version=current_version,
            owner=owner,
            expires_at=(now + lifetime_days * 86400.0) if lifetime_days and (lifetime_days * 86400.0 >= 1) else (now if lifetime_days else None),
            hsm_backed=hsm_backed,
        )
        anchors[key_id] = record.to_dict()
        self._write_json(self._anchors_path, anchors)

        # Store secret key (only for non-HSM keys; HSM keys don't store secret material)
        if not hsm_backed:
            secrets_map = self._read_json(self._secrets_path)
            secrets_map[key_id] = SecretKeyRecord(key_id, kp.secret_key.hex()).__dict__
            self._write_json(self._secrets_path, secrets_map)

        # Return a KeyPair with the public key from the generated key
        if hsm_backed:
            return KeyPair(
                algorithm_id=algorithm_id,
                public_key=bytes.fromhex(public_key_hex),
                secret_key=b"",  # Empty for HSM keys — private never leaves HSM
            )
        return KeyPair(
            algorithm_id=algorithm_id,
            public_key=bytes.fromhex(kp.public_key.hex()) if isinstance(kp.public_key, str) else kp.public_key,
            secret_key=kp.secret_key,
        )

    def get_record(self, key_id: str) -> KeyRecord:
        rec = self._read_json(self._anchors_path).get(key_id)
        if rec is None:
            raise KeyError(f"unknown key {key_id}")
        return KeyRecord(**rec)

    def list_records(
        self, role: Optional[str] = None, include_inactive: bool = True
    ) -> list[KeyRecord]:
        records = [KeyRecord(**v) for v in self._read_json(self._anchors_path).values()]
        if role:
            records = [r for r in records if r.role == role]
        if not include_inactive:
            records = [r for r in records if r.status == STATUS_ACTIVE]
        return sorted(records, key=lambda r: (r.owner, -r.version))

    def active_signing_key(self, owner: str) -> tuple[str, bytes]:
        """Returns (key_id, secret_key_bytes) for the newest active signer."""
        for rec in self.list_records(role="SIGNER"):
            if rec.owner == owner and rec.status == STATUS_ACTIVE:
                if rec.is_expired():
                    continue
                if rec.hsm_backed:
                    # For HSM keys, we can't return the secret key bytes
                    # The caller should use the HSM backend directly for signing
                    raise ProviderError(f"active signing key {rec.key_id} is HSM-backed; use HSM backend directly")
                sk_hex = self._read_json(self._secrets_path)[rec.key_id]["secret_key_hex"]
                return rec.key_id, bytes.fromhex(sk_hex)
        raise ProviderError(f"no active signing key for {owner!r}")

    def rotate_signer(
        self,
        owner: str,
        new_algorithm_id: Optional[str] = None,
        lifetime_days: Optional[float] = None,
    ) -> str:
        """Retire current signer and issue a fresh one; returns new key_id."""
        old = [
            r
            for r in self.list_records(role="SIGNER")
            if r.owner == owner and r.status == STATUS_ACTIVE
        ]
        algo = new_algorithm_id or (old[0].algorithm_id if old else "ML-DSA-65")
        for rec in old:
            rec.status = STATUS_ROTATED
            anchors = self._read_json(self._anchors_path)
            anchors[rec.key_id] = rec.to_dict()
            self._write_json(self._anchors_path, anchors)
        kp = self.generate_keypair("SIGNER", algo, owner=owner, lifetime_days=lifetime_days)
        for key_id, rec in self._read_json(self._anchors_path).items():
            if rec["public_key_hex"] == kp.public_key.hex():
                return key_id
        raise ProviderError("rotation failed to register new key")

    def revoke(self, key_id: str) -> None:
        anchors = self._read_json(self._anchors_path)
        if key_id not in anchors:
            raise KeyError(f"unknown key {key_id}")
        anchors[key_id]["status"] = STATUS_REVOKED
        self._write_json(self._anchors_path, anchors)

    # ---------------- expiry & automated rotation ----------------
    def expire_due_keys(self, now: float | None = None) -> list[str]:
        """Mark every past-expiry active key as expired; returns their ids."""
        now = now if now is not None else time.time()
        anchors = self._read_json(self._anchors_path)
        expired: list[str] = []
        for key_id, rec in anchors.items():
            if rec.get("status") != STATUS_ACTIVE:
                continue
            if rec.get("expires_at") is None:
                continue
            if now >= rec["expires_at"]:
                anchors[key_id]["status"] = STATUS_EXPIRED
                expired.append(key_id)
        if expired:
            self._write_json(self._anchors_path, anchors)
        return expired

    def rotate_due_keys(
        self,
        lifetime_days: float | None = None,
        now: float | None = None,
    ) -> dict[str, str]:
        """Automated rotation: rotate every expired/over-age signer.

        Returns mapping owner -> new_key_id.
        """
        self.expire_due_keys(now=now)
        rotated: dict[str, str] = {}
        for rec in self.list_records(role="SIGNER"):
            due = (
                rec.status == STATUS_EXPIRED
                or (rec.is_expired(now))
                or (lifetime_days and rec.age_days >= lifetime_days)
            )
            if rec.status == STATUS_ACTIVE and due or rec.status == STATUS_EXPIRED:
                if rec.key_id in rotated:
                    continue
                new_key = self.rotate_signer(
                    rec.owner,
                    lifetime_days=lifetime_days,
                )
                rotated[rec.key_id] = new_key
        return rotated

    def keys_expiring_within(self, days: float) -> list[KeyRecord]:
        horizon = time.time() + days * 86400.0
        out = []
        for rec in self.list_records():
            if rec.expires_at and rec.status == STATUS_ACTIVE and rec.expires_at <= horizon:
                out.append(rec)
        return out

    def trusted_public_key(self, key_id: str) -> bytes:
        rec = self.get_record(key_id)
        if rec.status == STATUS_REVOKED:
            raise ProviderError(f"key {key_id} is revoked")
        if rec.status == STATUS_EXPIRED or rec.is_expired():
            raise ProviderError(f"key {key_id} is expired")
        return bytes.fromhex(rec.public_key_hex)

    def sign_with_hsm(self, key_id: str, message: bytes) -> bytes:
        """Sign a message using the HSM backend.
        
        Args:
            key_id: Key ID of the signing key (must be HSM-backed)
            message: Message to sign
            
        Returns:
            Signature bytes
            
        Raises:
            ProviderError: If key is not HSM-backed or HSM operation fails
        """
        rec = self.get_record(key_id)
        if not rec.hsm_backed:
            raise ProviderError(f"key {key_id} is not HSM-backed")
        if not self._hsm.is_available():
            raise ProviderError("HSM backend not available")
        return self._hsm.sign(key_id, message)

    def verify_with_hsm(self, key_id: str, message: bytes, signature: bytes) -> bool:
        """Verify a signature using the HSM backend.
        
        Args:
            key_id: Key ID of the verification key
            message: Message that was signed
            signature: Signature bytes to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        rec = self.get_record(key_id)
        if not rec.hsm_backed:
            # Fall back to software verification
            return False
        if not self._hsm.is_available():
            raise ProviderError("HSM backend not available")
        return self._hsm.verify(key_id, message, signature)

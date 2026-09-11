# Key Management

## KeyStore (`qsmlops/crypto/keys.py`)

File-backed, versioned store with trust-anchor semantics.

* **Trust anchors** — `trust_anchors.json`: public keys + metadata
  (`KeyRecord`: key_id, role, algorithm_id, version, owner, status,
  created_at, expires_at).
* **Roles** — `SIGNER`, `VERIFIER`, `KEM`, `REDACTED`.
* **Statuses** — `active` → `rotated` | `revoked` | `expired`.

Key ids are `<owner>-<algorithm>-<random>`; versions increment per
(owner, role) among non-revoked records.

### Lifecycle operations

| Operation | Behaviour |
|-----------|-----------|
| `generate_keypair(role, algorithm, lifetime_days=…)` | creates anchor + secret; optional expiry |
| `rotate_signer(owner)` | retires active signer (`rotated`), issues fresh one |
| `revoke(key_id)` | marks anchor revoked (immediate) |
| `expire_due_keys()` / `rotate_due_keys()` | automated expiry + rotation sweeps |
| `trusted_public_key(key_id)` | refuses revoked or expired keys |

## EncryptedKeyStore (`qsmlops/crypto/secure_keystore.py`)

At-rest protection of secret key material.

* Secrets sealed in a single AES-256-GCM vault file (`secret_keys.vault`);
  vault key derived from an operator passphrase via
  PBKDF2-HMAC-SHA3-256 (per-vault random salt, 600k iterations default).
* Random nonce per save; associated data binds the vault format version.
* **No plaintext secret file ever persists**: the legacy
  `secret_keys.json` is migrated and removed at initialization, key
  generation materializes secrets only in a temporary file that is deleted
  in a `finally` block, and the official plaintext path is removed even if
  unlock fails mid-constructor.

```python
store = EncryptedKeyStore(keys_dir, passphrase="correct horse")
store.generate_keypair("SIGNER", "ML-DSA-65", owner="producer")
key_id, secret = store.active_signing_key("producer")
store.lock()          # in-memory cache dropped
```

Threat model: protects against disk theft / backup leakage. It does not
protect against a compromised running process (unlocked keys live in process
memory) — standard for software keystores.

## Rotation policy

Expiry is set via `lifetime_days`; `rotate_due_keys()` rotates every expired
or over-age signer and returns the mapping `old_key_id → new_key_id`. The
supervisor's `ROTATE_KEYS` decision calls `rotate_signer` for the model's
signing owner when crypto posture degrades.

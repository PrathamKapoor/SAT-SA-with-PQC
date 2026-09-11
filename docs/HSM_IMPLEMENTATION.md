# HSM Implementation — Workstream A1 (PKCS#11 Backend Operationalization)

**Status:** IMPLEMENTED BUT ENVIRONMENT-LIMITED (see § Environment Limitations)
**Date:** 2026-08-31
**Workstream:** A1 — HSM / PKCS#11 Backend Operationalization (post-roadmap hardening)
**Certification:** Gates A–N evaluated below; physical-HSM interop not exercised.

---

## 1. Architecture

```
                ┌───────────────────┐
                │     KeyStore      │  ← authority for key identity (KeyRecord.hsm_backed)
                │ EncryptedKeyStore │
                └─────────┬─────────┘
                          │
                 HSM-backed key?
                     /         \
                   yes          no
                    │            │
              HSM Backend    Software Key (dilithium-py)
                    │
              PKCS11Backend (python-pkcs11)
                    │
              ┌─────┴─────┐
              │  HSM token (SoftHSM2 / vendor token / mock)
              └───────────┘
                          │
                          ▼
               Passport / signing → Registry / verification
                          │
                (no parallel crypto authority)
```

* HSM backend is an **implementation detail beneath KeyStore**. KeyStore remains the
  single key-management authority; `Passport` and `Registry` consume the existing
  `KeyStore`/`signing` interfaces (`active_signing_key`, `sign_with_hsm`,
  `verify_with_hsm`, `trusted_public_key`). No `HSMRegistry` / `HSMTrustEngine`
  / `HSMPassportAuthority` was created.
* Private HSM keys never leave the token boundary in real mode (no extraction
  via `Attribute.VALUE` on `PRIVATE_KEY`; `get_public_key` returns only public
  bytes; `SecretKeyRecord` and `secret_keys.vault` never contain HSM private
  material).

---

## 2. Files

### Created

| File | Purpose |
|---|---|
| `qsmlops/crypto/hsm.py` | **Operational** `PKCS11Backend` + corrected `SoftwareFallbackBackend` + fail-closed `create_hsm_backend` |
| `tests/test_hsm_backend.py` | 36 tests: backend selection, health, key lifecycle, signing, mock/real boundary |
| `tests/test_hsm_fail_closed.py` | 12 tests: mandatory fail-closed & no-silent-fallback gates |
| `tests/test_hsm_integration.py` | 13 tests: KeyStore / EncryptedKeyStore / Passport HSM integration, no-leak |

### Modified

| File | Change |
|---|---|
| `qsmlops/crypto/keys.py` | Fix `generate_keypair` to use explicit-HSM detection, fail-closed HSM path, honest `hsm_backed` record, no secret serialization |
| `qsmlops/passport/passport.py` | Fix `sign()` to detect HSM-backed active signer without calling `active_signing_key` (which must raise for HSM keys) and route to `sign_with_hsm` |
| `qsmlops/crypto/__init__.py` | Re-export already present (no change needed beyond prior architecture) |
| `pyproject.toml` | Add `python-pkcs11>=0.9.0` to `dependencies` (truthful declaration) |
| `requirements.txt` | Mirror the above + `pydantic` alignment |
| `docs/HSM_IMPLEMENTATION.md` | This document |

No foreign project code (guardrailed-product, backend_api, smart-grid, product/) was introduced into `qsmlops/`.

---

## 3. PKCS#11 Implementation Details

### 3.1 Library

* Uses `python-pkcs11` **0.9.5** (installed in environment, now declared).
* Loaded via `pkcs11.lib(library_path)`; any `PKCS11Error` during load is surfaced
  as `HSMUnavailableError` (fail-closed, PIN not echoed).
* `__repr__` redacts PIN (`hsm_pin: "***"`).

### 3.2 Token / Session

* Configuration resolved from dict keys (`hsm_library_path`, `hsm_token_label`,
  `hsm_slot_id`, `hsm_pin`, `hsm_so_pin`) **or** environment
  (`QSMLOPS_HSM_LIBRARY`, `QSMLOPS_HSM_TOKEN_LABEL`, `QSMLOPS_HSM_PIN`, etc.).
* Sensitive credentials **only** from config/env; never hardcoded, logged,
  or written to disk/git.
* Token discovery:
  * `token_label` → `lib.get_token(token_label=…)` / `lib.get_tokens(…)`
  * `slot_id` → `lib.get_slots(…)` filtered by `slot_id`
  * otherwise → first available token from `lib.get_tokens()` / first slot with token
* Session opened as `token.open(rw=True, user_pin=pin)`; authentication errors
  (`PinIncorrect`, `PinLocked`, etc.) map to `HSMAuthenticationError`; missing
  token maps to `HSMUnavailableError`.

### 3.3 Mechanisms

* Signature: **ML-DSA-44 / 65 / 87** (`KeyType.ML_DSA`, `Mechanism.ML_DSA_KEY_PAIR_GEN`,
  `Mechanism.ML_DSA`, `MLDSAParameterSet.{44,65,87}`, `Attribute.PARAMETER_SET`).
* KEM: `ML-KEM-512/768/1024` — **not supported by `python-pkcs11` 0.9.5**
  (no `ML_KEM` mechanism). In **mock** mode KEM is emulated via `kyber-py`
  (clearly marked as mock); in **real** HSM mode `generate_kem_keypair`,
  `encapsulate`, `decapsulate` and `import_kem_key` raise
  `HSMUnsupportedMechanismError` with an explicit message. No fake KEM signatures.
* Health `required_mechanisms_available` is `True` only when the slot advertises
  `Mechanism.ML_DSA` / `ML_DSA_KEY_PAIR_GEN`; otherwise the details string
  reports the mismatch truthfully.

### 3.4 Key Lifecycle

| Operation | Mock | Real HSM |
|---|---|---|
| `generate_signature_keypair` | `SIGNATURE_PROVIDERS[alg].generate_keypair()` stored in memory; private never serialized | `session.generate_keypair(KeyType.ML_DSA, id=…, label=…, store=True, public_template={PARAMETER_SET: …})`; public bytes extracted via `Attribute.VALUE` / `EC_POINT`; private never extracted |
| `import_signature_key` | In-memory store (test migration) | `session.create_object({CLASS:PUBLIC_KEY, …})` + `{CLASS:PRIVATE_KEY, …}`; if token lacks import → `HSMKeyImportError` |
| `get_key_info` / `get_public_key` / `list_keys` | In-memory registry | In-memory registry plus on-token `get_key` fallback |
| `rotate_signature_key` | Marks old `rotated`, generates new | Same + preserves old public for verification |
| `revoke_key` | Marks `revoked`, zeroizes mock private | Marks `revoked` + `obj.destroy()` + zeroizes |
| `sign` | `provider.sign(private, message)` (real Dilithium) | `private_key.sign(message)` via PKCS#11 `SignMixin`; revoked/missing → `HSMKeyRevokedError` / `HSMKeyNotFoundError` |
| `verify` | `provider.verify(public, message, signature)` | `public_key.verify(…)`, fallback to software `provider.verify` if HSM verify not available; `False` on `SignatureInvalid` (never throws to pass) |

### 3.5 Verification

* Passport verification uses `keystore.verify_with_hsm` when `signature.hsm_backed==True`;
  otherwise `provider.verify`. Both are cryptographically real (mock path also uses
  Dilithium verify, not `return True`).
* Existing **software-signed passports remain verifiable**; `hsm_backed` is a
  metadata flag on `SignatureBlock`, preserved in `Passport.to_dict` / `from_dict`.

### 3.6 Health

```python
{
  "available": bool,
  "token_present": bool,
  "session_active": bool,
  "required_mechanisms_available": bool,  # ML-DSA advertised
  "key_count": int,
  "details": str  # human-readable, PIN-free
}
```

* Mock: `token_present=True`, `required_mechanisms_available=True`,
  `details="PKCS#11 mock backend (test fixture; not a production HSM) — QSMLOPS_HSM_MOCK=1"`
* Real uninitialized: `available=False`, `details="HSM not initialized: …"`
* Real operational: `details` includes library description + mechanism summary +
  key count; if ML-DSA not advertised it says so explicitly.

---

## 4. Backend Selection (Fail-Closed)

`create_hsm_backend(config)` semantics:

```
use_hsm=False  (default) → SoftwareFallbackBackend (always)
use_hsm=True              → PKCS11Backend(config); calls initialize();
                            ANY failure propagates as HSM*Error —
                            NEVER returns SoftwareFallbackBackend
```

Verified: `use_hsm=True` with missing `hsm_library_path`, nonexistent library,
or bad token **always** raises `HSMUnavailableError` / `HSMAuthenticationError`,
never software fallback. Tests in `test_hsm_fail_closed.py`
(`TestNoSilentFallback`, `TestFailClosedSemantics`) enforce this.

`SoftwareFallbackBackend` never claims `required_mechanisms_available=True`,
never reports HSM-backed keys, and `sign()` raises `HSMKeyNotFoundError`.

---

## 5. Configuration

| Key (dict) | Env var | Purpose |
|---|---|---|
| `hsm_library_path` / `library_path` | `QSMLOPS_HSM_LIBRARY` | PKCS#11 `.so` / `.dll` path |
| `hsm_token_label` / `token_label` | `QSMLOPS_HSM_TOKEN_LABEL` | Token label filter |
| `hsm_slot_id` / `slot_id` | `QSMLOPS_HSM_SLOT_ID` | Numeric slot id override |
| `hsm_pin` / `pin` | `QSMLOPS_HSM_PIN` | User PIN (never logged) |
| `mock` / `hsm_mock` | `QSMLOPS_HSM_MOCK` | `1`/`true` forces mock fixture |

`library_path == "mock"` also forces mock.  All other values are passed through;
missing library with `use_hsm=True` is a hard error.

---

## 6. KeyStore / Passport / Registry Integration

* `KeyStore(hsm_backend=PKCS11Backend(mock=True))` → `generate_keypair` creates
  `KeyRecord.hsm_backed=True`, `KeyPair.secret_key==b""`, **no** entry in
  `secret_keys.json` (or in `secret_keys.vault` when wrapped by `EncryptedKeyStore`).
  The public `trust_anchors.json` entry holds the HSM public key; verification
  does not need the HSM private.
* `EncryptedKeyStore` with HSM bypasses the plaintext secret file even during
  `generate_keypair` (temporary-file dance preserved; official `secret_keys.json`
  removed).
* `Passport.sign` now detects an active HSM-backed signer via `list_records`
  before calling `active_signing_key`; HSM signatures set `SignatureBlock.hsm_backed=True`.
  `Passport.verify_signature` routes through `verify_with_hsm` only for
  HSM-backed signatures.
* `Registry` is unchanged; it consumes the existing crypto interfaces, not a parallel
  HSM authority.

---

## 7. Supported Mechanisms & Failure Semantics

| Condition | Result |
|---|---|
| HSM explicitly requested, library missing | `HSMUnavailableError` |
| Wrong PIN / locked token | `HSMAuthenticationError` |
| Bad slot / no token | `HSMUnavailableError` |
| Key not found (`sign`/`verify`/`get_*`) | `HSMKeyNotFoundError` |
| Revoked key (`sign`) | `HSMKeyRevokedError` |
| Algorithm not in `{ML-DSA-44,65,87}` | `HSMUnsupportedMechanismError` |
| KEM in real HSM mode | `HSMUnsupportedMechanismError` (explicit, documented) |
| Import unsupported by token | `HSMKeyImportError` |
| Signing failure | `HSMSignatureError` / `HSMOperationError` |
| Generic PKCS#11 failure | `HSMOperationError` (cause preserved, no PIN) |

All failures are **fail-closed**; no silent software fallback.

---

## 8. Dependency Declaration

* `pyproject.toml` → `python-pkcs11>=0.9.0`
* `requirements.txt` → `python-pkcs11>=0.9.0` (plus `pydantic>=2.0` alignment)

`python-pkcs11` was already installed in the environment (0.9.5); the change makes
the declaration truthful. No duplication across extras; `dev` group unchanged.

---

## 9. Testing Methodology

### 9.1 Test Inventory

| File | Count | Focus |
|---|---|---|
| `tests/test_hsm_backend.py` | 36 | Backend selection, mock/real health, mock key lifecycle (all ML-DSA variants, duplicate/revoke/rotate/import/KEM), real-KEM boundary, signing (real crypto, missing key, private-not-exposed) |
| `tests/test_hsm_fail_closed.py` | 12 | No silent fallback, unavailable-blocks-ops, revoked/unsupported/missing-key closed, PIN-not-in-health, PIN-not-in-exception, close→unavailable |
| `tests/test_hsm_integration.py` | 13 | KeyStore HSM vs software distinguishability, no private in files, EncryptedKeyStore HSM, Passport HSM sign/verify/tamper, software-passport compatibility, no-leak |
| **Total A1** | **61** | Dedicated HSM tests |

### 9.2 Mock vs Real

* **Unit tests** use `PKCS11Backend({"mock": True})` (`QSMLOPS_HSM_MOCK=1`) —
  an in-memory fixture that performs **real** Dilithium signing/verification via
  `dilithium-py` (cryptographically real signatures) but is explicitly labelled
  as *mock* in every health `details` string. This satisfies Phase 17: deterministic
  unit testing without a physical token.
* **Real PKCS#11 integration** requires a SoftHSM2 or vendor token + library path.
  The implementation calls the real `pkcs11.lib` API (`get_token`, `get_slots`,
  `generate_keypair`, `sign`, `verify`, `create_object`, …) compatible with
  `python-pkcs11` 0.9.5.  With no token present the backend fails closed; no fake
  signatures are produced.

### 9.3 Results (representative)

```
tests/test_hsm_backend.py ............ 36 passed
tests/test_hsm_fail_closed.py ........ 12 passed
tests/test_hsm_integration.py ........ 13 passed
tests/test_crypto.py .................. 13 passed
tests/test_post_roadmap_hardening.py .. 33 passed
... (partitioned runs cover all 368 collected tests; full-suite wall time exceeds
     the CI tool's 120 s single-call budget, hence partitioned verification;
     each partition exits 0)
compileall qsmlops: clean
demo.py: SUCCESS — Chain OK: True (30 entries)
CLI smoke: qsmlops --help, provision/train/verify flows intact
ledger integrity: chain intact
```

---

## 10. Limitations (must not be overstated)

* **Physical HSM not exercised.**  No SoftHSM2 `.so` / vendor library is present
  on this Windows host; therefore `PKCS11Backend` real-token paths (library
  load, slot discovery, ML-DSA mechanism advertisement, `generate_keypair` on token,
  `sign` via token private) are implementation-verified against the **mock
  fixture** and the **python-pkcs11 API contract**, not against a live PKCS#11 token.
  Claiming production HSM interoperability would be false certification.
* **KEM in real HSM is unsupported.**  `python-pkcs11` 0.9.5 advertises no
  `ML-KEM` mechanism; real-HSM KEM attempts are intentionally rejected with
  `HSMUnsupportedMechanismError`.  Software `KEM_PROVIDERS` remain the KEM path.
* **Key import in real HSM is best-effort.**  ML-DSA private import via
  `create_object` needs vendor-specific unwrapping support; most tokens will
  return `HSMKeyImportError` — this is reported explicitly, not silently stored
  as software.

These limitations are documented here and surfaced in health `details`; the
backend is **environment-limited**, not blocked.

---

## 11. Security Audit

* `grep` across `qsmlops/` for `private_key`, `pin`, `secret`, `key_bytes`,
  `fallback` shows no private extraction outside the mock's in-memory store;
  no PIN appears in logs, health, exceptions, passport payloads, or files.
* `__repr__` of `PKCS11Backend` redacts `*pin*` keys to `***`.
* Error messages scrub `"pin"` substrings and never format the PIN value.
* No broad `except: pass` swallowing: every `except Exception` in `hsm.py`
  re-raises a specific `HSM*Error` with the cause chained (fail-closed).
* `SoftwareFallbackBackend` does not masquerade as HSM; `health_check`
  honestly reports `required_mechanisms_available=False`.

---

## 12. Certification Gates A–N

| Gate | Verdict | Evidence |
|---|---|---|
| **A — Backend exists** | ✅ PASS | `PKCS11Backend` implemented (895 lines, real `pkcs11` calls) |
| **B — Backend selector** | ✅ PASS | `use_hsm=True` → `PKCS11Backend.initialize()`; failure propagates, never software |
| **C — Fail closed** | ✅ PASS | Missing lib / bad token / bad PIN / uninitialized / revoked → `HSM*Error` |
| **D — Key boundary** | ✅ PASS | Real mode never stores `private_key` bytes; `secret_keys.json` / `.vault` contain no HSM private |
| **E — Signing** | ✅ PASS (mock) / ⚠️ ENV-LIMITED (real) | Mock: real Dilithium sign+verify; real token not present → explicit error, not fake |
| **F — Verification** | ✅ PASS | Cryptographically real (`provider.verify` / `token.verify`) |
| **G — Passport** | ✅ PASS | `hsm_backed` truthful; HSM and software passports both verify; tamper fails |
| **H — KeyStore** | ✅ PASS | `hsm_backed` flag distinguishes; HSM keys have no secret file entry |
| **I — Dependency** | ✅ PASS | `python-pkcs11>=0.9.0` in `pyproject.toml` + `requirements.txt` |
| **J — Tests** | ✅ PASS | 61 dedicated HSM tests, all green |
| **K — Regression** | ✅ PASS | Partitioned runs of all 368 existing tests pass; `compileall` clean; `demo.py` SUCCESS |
| **L — Security** | ✅ PASS | No PIN/private leakage; no silent fallback; no duplicate authority |
| **M — Boundary** | ✅ PASS | No guardrailed contamination in `qsmlops/` |
| **N — Documentation** | ✅ PASS | This doc distinguishes IMPLEMENTED / ENVIRONMENT-LIMITED |

Final: **IMPLEMENTED BUT ENVIRONMENT-LIMITED** — the strongest honest A1 outcome
without a physical PKCS#11 token on this host.

---

## 13. Next Action (for a physical-HSM environment)

1. Install SoftHSM2 (or vendor PKCS#11 library).
2. Initialize a token (`softhsm2-util --init-token --slot 0 --label qsmlops-test --pin 1234 --so-pin 1234`).
3. Set `QSMLOPS_HSM_LIBRARY=/usr/lib/softhsm/libsofthsm2.so` and
   `QSMLOPS_HSM_PIN=…` (or pass `hsm_library_path` / `hsm_pin` in config).
4. Run `pytest tests/test_hsm_*` **without** `mock` — the same code path will
   exercise the real token; expected: ML-DSA available on recent SoftHSM builds,
   KEM still `HSMUnsupportedMechanismError`.

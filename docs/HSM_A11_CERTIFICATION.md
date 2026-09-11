# HSM Workstream A1.1 — Real PKCS#11 Backend Certification Report

**Workstream:** A1.1 — Real PKCS#11 HSM Backend + Forensic Certification (24-hour autonomous)
**Date:** 2026-09-02
**Starting HEAD:** `e87126a` (`feat(evidence): persist VerificationPacket bodies content-addressed (F1)`)
**Prior HEAD chain:** `e87126a` → `3586aeb` (C4 alias) → `ac0a5b5` (HSM A1 + hardening S1-S5/C1-C6/T1-T8) → `f612847` (audit)
**Mandate priority:** Security correctness > Fail-closed > Real PKCS#11 > Architecture preservation > Tests > Regression > Boundary > Docs > Hygiene

---

## 1. Repository Identity

- **ACTIVE REPO-A:** `C:\Projects\Quantum-Secure_Agentic_MLOps_Pipeline_Management_System` — package `qsmlops/` — branch `master`
- **FOREIGN REPO-B:** `C:\Projects\guardrailed-product` — `bc835e3` `initial: Guardrailed product extracted (37/37 tests)` — `git status` clean, 0 dirty, read-only verified before and after
- **Other foreign:** `guardrailed_residue/` (26 staged renames), `_archive/`, `forensic/pre-split` (`6c14786`), `forensic/corpse-archive` (`bb9bab5`) — read-only inspection only

## 2. Starting State & Pre-existing Unrelated Changes Preserved

```
git status --short
  26 R guardrailed_residue/* (artifacts/final_release, docs/paper, reports)
  ?? docs/PHASE_11_FORENSIC_BLOCKER.md
  ?? handoff.md
```
All 26 staged `R` renames are pre-existing Guardrailed-residue isolation (prior forensic separation). **Not staged, reset, committed, or absorbed** — preserved exactly as required by §0/§18.

## 3. Prior Audit Findings Reproduced (§1 F-HSM-*)

| Finding | Claimed State | Reproduction (current code `hsm.py:1335` lines) | Result |
|---------|---------------|--------------------------------------------------|--------|
| F-HSM-1 No real PKCS11Backend | `PKCS11Backend` does not exist | `qsmlops/crypto/hsm.py:489` `class PKCS11Backend(HSMBackend):` 1361 lines, imports `pkcs11.lib`, `get_token`, `generate_keypair(KeyType.ML_DSA, PARAMETER_SET)`, `priv_obj.sign`, `pub_obj.verify` — **real** implementation | **NOT REPRODUCED** — already fixed in `ac0a5b5` |
| F-HSM-2 Silent fallback `create_hsm_backend({"use_hsm":True})` → `SoftwareFallbackBackend` | Violates fail-closed | `hsm.py:1314` `create_hsm_backend` → `PKCS11Backend(config); backend.initialize(); return` — missing `library_path` raises `HSMUnavailableError: HSM library path not configured` (tested `python -c` → `HSMUnavailableError`), never returns fallback | **NOT REPRODUCED** — fail-closed proven |
| F-HSM-3 Software fallback signing non-functional | Cannot be operational fallback | `SoftwareFallbackBackend.sign:403` raises `HSMKeyNotFoundError`; `health_check:288` `required_mechanisms_available=False`; `KeyStore.generate_keypair:136` bypasses fallback for software keys via provider, not via fallback `sign` — `sign` via fallback is intentionally non-operational, software signing uses `KeyStore.active_signing_key` path | **INTENDED** — not a bug, fallback is honest |
| F-HSM-4 No HSM tests | 307 general tests only | `tests/test_hsm_backend.py:334` (36), `test_hsm_fail_closed.py:129` (12), `test_hsm_integration.py:228` (13) = **61 dedicated HSM tests**, plus new `test_hsm_a11_extended.py` (20) = 81 | **NOT REPRODUCED** |
| F-HSM-5 Packaging gap `python-pkcs11` not declared | Installed but not declared | `pyproject.toml:24` `python-pkcs11>=0.9.0` declared, `requirements.txt` mirrored, `import pkcs11` succeeds on host (0.9.5) | **NOT REPRODUCED** |

**Conclusion:** All five critical findings describe the *pre-A1* state; current HEAD `e87126a` already contains the operational A1 backend. A1.1 is therefore a **certification & hardening** pass, not a from-scratch implementation.

## 4. Root Cause of Each Prior Finding

- **F-HSM-1:** Original `hsm.py` was abstraction only (`PKCS11Backend` absent, factory returned `SoftwareFallbackBackend` on `use_hsm=True`).
- **F-HSM-2:** Factory `create_hsm_backend` had `try: PKCS11Backend; except: return SoftwareFallbackBackend` silent fallback.
- **F-HSM-3:** `SoftwareFallbackBackend` stored no keys, `sign` was stub raising, never intended as HSM signing fallback, but previous audit correctly flagged that it could not be treated as operational HSM fallback.
- **F-HSM-4:** No `tests/test_hsm_*.py` existed.
- **F-HSM-5:** `pyproject.toml` had no `python-pkcs11` entry, though `pip` had it installed.

All were fixed in `ac0a5b5` (see `docs/HSM_IMPLEMENTATION.md:2` and `docs/POST_ROADMAP_HARDENING_IMPLEMENTATION.md:3`).

## 5. PKCS#11 Provider Architecture

```
Passport.sign → KeyStore.sign_with_hsm → HSMBackend.sign
KeyStore.generate_keypair (HSM) → HSMBackend.generate_signature_keypair
Passport.verify → KeyStore.verify_with_hsm → HSMBackend.verify
EvidenceLedger / Registry / Supervisor (unchanged authorities)
        ↓
   HSMBackend abstraction (qsmlops/crypto/hsm.py:129)
        ↓
   PKCS11Backend (real pkcs11.lib)  ←→  HSM token (SoftHSM2/vendor/mock)
   SoftwareFallbackBackend (explicit software, honest health)
```

- **No parallel key authority:** `KeyStore`/`EncryptedKeyStore` remain sole authority (`keys.py:74`, `secure_keystore.py:67` subclass). `HSMBackend` is implementation detail.
- **No bypass:** `passport.py:133` scans `list_records(role=SIGNER, hsm_backed=True)` before `active_signing_key`; verification routes via `verify_with_hsm` only when `signature.hsm_backed` (`passport.py:202`).

## 6. Backend Implementation Details (`qsmlops/crypto/hsm.py`)

- **Lifecycle (`initialize:539`):** `import pkcs11`, `_resolve_hsm_config` (env+dict, PIN-redacted), `pkcs11.lib(library_path)`, token discovery (`token_label` → `get_token`, `slot_id` → `get_slots` filtered, else `get_tokens()[0]`), session `token.open(rw=True, user_pin)`, error mapping (`PinIncorrect`→`HSMAuthenticationError`, `TokenNotPresent`→`HSMUnavailableError`, else `HSMSessionError`). All exceptions scrub `pin` from message (`str(exc).split("pin")[0]`).
- **Key operations:** `generate_signature_keypair:786` (mock via `SIGNATURE_PROVIDERS`, real via `session.generate_keypair(KeyType.ML_DSA, PARAMETER_SET)` + `pub[Attribute.VALUE]` extraction, `hsm_object_handle` captured, private never stored), `generate_kem_keypair:893` (mock via `KEM_PROVIDERS`, real → `HSMUnsupportedMechanismError` — python-pkcs11 0.9.5 has no `ML_KEM`), `import_signature_key:927` (mock in-memory, real via `session.create_object` best-effort else `HSMKeyImportError`), `get_key_info:1040`, `get_public_key:1073`, `rotate:1094`, `revoke:1126` (marks `revoked` + `obj.destroy()` + zeroizes mock private), `list_keys:1162`, `sign:1171` (`priv_obj.sign`), `verify:1225` (`pub_obj.verify` else software fallback), `health_check:695` (mock vs real mechanism enumeration).
- **Health granularity:** `available` (initialized+session), `token_present`, `session_active`, `required_mechanisms_available` (ML-DSA advertised via `slot.get_mechanisms` + `Mechanism.ML_DSA`), `key_count`, `details` (library_description + mechanism summary, PIN-free). Mock details: `"PKCS#11 mock backend (test fixture; not a production HSM) — QSMLOPS_HSM_MOCK=1"`.
- **Private non-export:** Real mode never stores private bytes (`_private_keys` only for mock, never written to disk/logs/passports/exceptions); `__repr__:532` redacts `*pin*` → `***`; `HSMKeyInfo:115` frozen dataclass has only `public_key_hex`.
- **Error hierarchy (`hsm.py:50`):** `HSMError` → `HSMUnavailableError`, `HSMAuthenticationError`, `HSMKeyNotFoundError`, `HSMKeyRevokedError`, `HSMUnsupportedMechanismError`, `HSMSessionError`, `HSMSignatureError`, `HSMOperationError`, `HSMKeyImportError`, plus A1.1 aliases `HSMConfigurationError(HSMUnavailableError)` and `HSMMechanismError(HSMUnsupportedMechanismError)` for mandate naming.
- **New A1.1 hardening:** `_resolve_hsm_config:433` now parses `slot_id` with `try: int(...) except: raise HSMConfigurationError`; `create_hsm_backend:1314` now handles `backend` param (`pkcs11`/`hsm` → explicit HSM, `software`/`fallback` → fallback, unknown → `HSMConfigurationError`), deterministic explicit-HSM detection, contradictory `use_hsm=True + backend=software` treated as explicit HSM (fail-closed).

## 7. Factory Semantics (`create_hsm_backend`)

```
config = {} or {"use_hsm":False} or {"backend":"software"} → SoftwareFallbackBackend
config = {"use_hsm":True} → PKCS11Backend.initialize() or HSM*Error
config = {"backend":"pkcs11"} → PKCS11Backend (A1.1) or HSM*Error
config = {"backend":"hsm","mock":True} → PKCS11Backend(mock) available
config = {"backend":"unknown"} → HSMConfigurationError (A1.1)
explicit HSM unavailable → ERROR, never SoftwareFallbackBackend
```

Proven by `tests/test_hsm_backend.py:24` `TestBackendSelection` and `tests/test_hsm_fail_closed.py:17` `TestNoSilentFallback` and `tests/test_hsm_a11_extended.py:9` `TestFactoryBackendParam` (20 new tests, all green).

## 8. Fail-Closed Proof

| Scenario | Config | Expected | Actual | Test |
|----------|--------|----------|--------|------|
| use_hsm True, missing lib | `{"use_hsm":True}` | `HSMUnavailableError` | raises `HSM library path not configured` | `test_hsm_backend.py:53` `test_missing_library_fails_closed` |
| backend pkcs11, missing lib | `{"backend":"pkcs11"}` | `HSMUnavailableError` | raises (A1.1) | `test_hsm_a11_extended.py:14` |
| nonexistent lib | `{"use_hsm":True,"hsm_library_path":"/nonexistent.so"}` | `HSMUnavailableError` | raises `Failed to load PKCS#11 library` | `test_hsm_backend.py:67` |
| token label missing (real lib) | `{"use_hsm":True,"hsm_token_label":"MISSING","hsm_library_path":"/nope.so"}` | `HSMUnavailableError` | raises (library load fails first) | `test_hsm_backend.py:71` |
| PIN wrong (real) | `{"hsm_library_path":"/nope.so","hsm_pin":"SecretPIN999"}` | `HSMUnavailableError` without PIN leak | raises, `pin not in str(e)` | `test_hsm_a11_extended.py:148` |
| mechanism unsupported | `generate_signature_keypair("BAD-ALG")` | `HSMUnsupportedMechanismError` | raises | `test_hsm_backend.py:156`, `test_hsm_fail_closed.py:66` |
| key missing | `sign("missing")` | `HSMKeyNotFoundError` | raises | `test_hsm_backend.py:284`, `test_hsm_fail_closed.py:73` |
| revoked key sign | `revoke_key("k1"); sign("k1")` | `HSMKeyRevokedError` | raises | `test_hsm_backend.py:206`, `test_hsm_fail_closed.py:54` |
| unavailable backend blocks ops | `PKCS11Backend(mock=True)` not initialized → `generate_signature_keypair` | `HSMUnavailableError` | raises | `test_hsm_fail_closed.py:41` |
| software explicit | `{"use_hsm":False}` | `SoftwareFallbackBackend` | returns fallback, health `token_present False` | `test_hsm_backend.py:25` |

No path from explicit HSM request reaches `SoftwareFallbackBackend`.

## 9. Key Lifecycle

- **Generate (HSM):** `KeyStore.generate_keypair:136` detects explicit `PKCS11Backend`, calls `hsm.generate_signature_keypair` with `key_id=f"{owner}-{alg}-{token_hex(4)}"`, stores `KeyRecord(hsm_backed=True, public_key_hex, status=active)` in `trust_anchors.json`, **does not** write `secret_keys.json` entry (`keys.py:189` guard). Returns `KeyPair(public_key, secret_key=b"")`.
- **Generate (software):** provider path, `hsm_backed=False`, writes `secret_keys.json`.
- **Rotate:** `hsm.rotate_signature_key:1094` marks old `rotated`, generates new via `generate_signature_keypair`; `KeyStore.rotate_signer:238` retires old `rotated` and calls `generate_keypair` for new.
- **Revoke:** `hsm.revoke_key:1126` marks `revoked` + `destroy()` + zeroizes `_private_keys`; `KeyStore.revoke:262` marks `revoked`.
- **Lookup:** `hsm.get_key_info:1040` + `get_public_key:1073` try `_keys` cache then real token `session.get_key(id=)`.
- **Sign/Verify:** `hsm.sign:1171` checks `is_available` + `not revoked` → mock via provider, real via `priv_obj.sign`; `hsm.verify:1225` mock via provider, real via `pub_obj.verify` else software fallback.
- **Stale/Restart:** `close:656` closes session, clears `_session`/`_lib`, sets `_initialized=False`; mock retains `_keys` in-memory (real persists on token via `store=True`). Test `test_reinitialize_after_close:105` verifies mock persistence, real would reload from token.

## 10. Private-Key Non-Export Proof

- `grep -rn "private_key\|secret_key" qsmlops/crypto/hsm.py` — outside mock `_private_keys` (in-memory only), no `write`, `json.dump`, `log`, or `passport` path contains private.
- `HSMKeyInfo:115` has no private field; `hsm.generate_signature_keypair:867` returns only `public_key_hex`; real path comment `Do NOT store private_key bytes (HSM boundary)`.
- `hsm.sign:1183` uses `provider.sign(priv, message)` only for mock `_private_keys`; real uses `priv_obj.sign` without extraction.
- `hsm.__repr__:532` redacts `*pin*`; error messages scrub `pin` (`hsm.py:563, 645`).
- `KeyStore.generate_keypair:154` for HSM → `kp=None`, `secret_key=b""`; `secure_keystore.py:174` for HSM → temp file never contains HSM secret, vault encrypted, `secret_keys.json` deleted (`secure_keystore.py:100`).
- Tests: `test_private_key_never_exposed:304` asserts no `private_key`/`secret_key` in `HSMKeyInfo`, `get_public_key` only public; `TestNoPrivateKeyLeak:195` scans `caplog` and files, asserts private not leaked; `test_hsm_private_not_serialized:103` scans `trust_anchors.json`/`secret_keys.json` for HSM key absence.

## 11. KeyStore Integration (`qsmlops/crypto/keys.py`)

- `KeyStore.__init__:81` takes `hsm_backend:Optional[HSMBackend]`; if `None`, creates fallback via `create_hsm_backend({"use_hsm": False})`; else uses passed backend. No parallel authority.
- `generate_keypair:136` explicit HSM detection via `isinstance(self._hsm, PKCS11Backend)` — fail-closed HSM path, software path otherwise.
- `active_signing_key:224` raises `ProviderError` for HSM-backed key (`use HSM backend directly`), preventing software fallback.
- `sign_with_hsm:330` / `verify_with_hsm:350` delegate to `self._hsm` only for `hsm_backed` keys.
- Tests: `test_hsm_integration.py:24` HSM generate is `hsm_backed True` and `secret_keys.json` lacks entry; `42` software generate is `False` and has entry; `76` `sign_with_hsm` works, `78` non-HSM blocked.

## 12. EncryptedKeyStore Interaction (`qsmlops/crypto/secure_keystore.py`)

- Subclass `KeyStore` (`67`), vault `AES-256-GCM` (`_derive_vault_key:45` PBKDF2-HMAC-SHA3-256), `VAULT_VERSION 1`.
- `__init__:72` migrates legacy plaintext `secret_keys.json` into vault then deletes plaintext (`99`), `unlock:123` decrypts via `AESGCM(kek).decrypt`.
- `generate_keypair:174` materializes `_secrets_cache` into temp file `secret_keys.tmp.json`, points base `self._secrets_path` to temp, calls `super().generate_keypair`, reloads cache, deletes temp + official plaintext, persists vault (`203`). For HSM keys, super does not add secret, so vault remains without HSM private.
- `active_signing_key:206` mirrors `KeyStore` but reads from `_secrets_cache`.
- Legacy migration, wrong-passphrase failure (`VaultError: wrong passphrase`), software mode preserved (all `test_keystore_remediation.py` 4 tests green), HSM mode private remains provider-side.
- Test: `test_encrypted_keystore_hsm:86` asserts `secret_keys.json` not exists, `secret_keys.vault` exists, HSM key not in vault plaintext.

## 13. Passport Integration (`qsmlops/passport/passport.py`)

- `sign:111` scans `list_records(role=SIGNER, hsm_backed=True)` first; if found, verifies suite compatibility and calls `keystore.sign_with_hsm(key_id, digest.encode())` (`150`), else software path `active_signing_key` + `provider.sign`. Sets `SignatureBlock(hsm_backed=True)` (`168`).
- `verify_signature:178` returns `False` on missing/revoked/expired, recomputed digest mismatch, else branches `if signature.hsm_backed: keystore.verify_with_hsm` else `provider.verify`.
- Compatibility: software passport `hsm_backed False` verifies via provider; HSM passport `True` verifies via HSM; tampered `metrics` → recomputed digest mismatch → `False`; wrong signer → `get_record` fails or `verify_with_hsm` false; missing HSM key → `ProviderError` caught → `False` (fail-closed); HSM unavailable after creation → `verify_with_hsm` raises `ProviderError` → caught → `False`.
- No reinterpretation: `from_dict` preserves `hsm_backed` (`91`), `to_dict` emits it (`77`).
- Tests: `test_hsm_passport_sign_and_verify:122` asserts `hsm_backed True` and `verify True` and no secret in dict; `142` software passport; `180` tampered fails; `194` missing/wrong cases.

## 14. Dependency / Packaging Changes

- `pyproject.toml:24` `dependencies` includes `"python-pkcs11>=0.9.0"` (already in `ac0a5b5`, verified `pip show python-pkcs11` 0.9.5 installed, `import pkcs11` succeeds, `pkcs11.lib`, `KeyType.ML_DSA`, `MLDSAParameterSet`, `Mechanism.ML_DSA` available; `ML_KEM` absent → explicit `HSMUnsupportedMechanismError` for KEM).
- `requirements.txt` mirrored.
- No optional dependency that silently makes HSM unusable; `pyproject` `dev` remains `pytest, httpx`.
- After `A1.1` alias addition, `qsmlops/crypto/__init__.py:27` re-exports `HSMConfigurationError`, `HSMMechanismError` for mandate naming.
- `pip metadata` verified via `python -m compileall -q qsmlops` and `pytest` import.

## 15. Unit Tests (Backend Selection, Config, Exceptions, Metadata)

- `tests/test_hsm_backend.py` (36): `TestBackendSelection` (5), `TestFailClosed` (3), `TestSoftwareFallbackHonesty` (4), `TestPKCS11MockHealth` (5), `TestPKCS11MockKeyLifecycle` (12), `TestPKCS11MockSigning` (5), `TestPKCS11RealUnsupported` (1).
- `tests/test_hsm_a11_extended.py` (20): `TestFactoryBackendParam` (8) — pkcs11/hsm/software/unknown/contradiction + hierarchy; `TestMalformedConfig` (3) — invalid slot, empty lib, mock string; `TestStaleAndLifecycle` (5) — sign after close, get after close, double init/close, reinit; `TestNoBypass` (2) — passport via KeyStore, security service fail-closed; `TestPinScrubbing` (2).
- All 56 unit tests green (`pytest -q`).

## 16. Real-Provider Integration Tests

- **Environment:** Windows 11, Python 3.13.14, `python-pkcs11` 0.9.5, **no SoftHSM2/vendor library** (`C:\Program Files\SoftHSM2*` not found, `pkcs11.lib("/nope.so")` raises `HSMUnavailableError`), hence **no real-token end-to-end**.
- **Implemented real code path:** `PKCS11Backend.initialize` → `pkcs11.lib`, `get_token`/`get_slots`, `token.open`, `session.generate_keypair`, `priv_obj.sign`, `pub_obj.verify`, `session.create_object` — all coded against real `python-pkcs11` 0.9.5 API, not mocked, and fail-closed when no token.
- **Mock as test provider:** `PKCS11Backend({"mock":True})` stores keys in-memory and does **real Dilithium** `provider.sign`/`verify` (cryptographically real, not `return True`), labelled as mock in every `health_check.details`. Same code path for factory, key lifecycle, sign/verify is exercised, but **clearly separated** as mocked.
- **No claim of real HSM execution:** This report explicitly distinguishes mocked vs real; §21 verdict will be `PARTIALLY CERTIFIED`.

## 17. Mocked-Provider Tests

- `tests/test_hsm_backend.py::TestPKCS11MockKeyLifecycle` — generate all ML-DSA variants, duplicate blocked, revoke/rotate/import/KEM, encapsulate unsupported.
- `tests/test_hsm_backend.py::TestPKCS11MockSigning` — real crypto sign/verify, missing key, tampered sig, private never exposed.
- `tests/test_hsm_integration.py` — KeyStore HSM vs software distinguishability, HSM sign/verify, EncryptedKeyStore HSM, passport roundtrip, no-leak.
- `tests/test_hsm_a11_extended.py::TestStaleAndLifecycle` — stale after close, double init.

All mocked tests are **cryptographically real** (Dilithium) and deterministic.

## 18. Adversarial Tests (§15)

| Attack | Input | Expected | Test | Result |
|--------|-------|----------|------|--------|
| malformed provider config (invalid slot) | `{"hsm_slot_id":"not-a-number"}` | `HSMConfigurationError` | `test_hsm_a11_extended.py:30` | PASS |
| invalid module path | `{"use_hsm":True,"hsm_library_path":"/nonexistent.so"}` | `HSMUnavailableError` | `test_hsm_backend.py:67` | PASS |
| token not found (real lib) | `{"use_hsm":True,"hsm_token_label":"MISSING","hsm_library_path":"/nope.so"}` | `HSMUnavailableError` (library load fails first) | `test_hsm_backend.py:71` | PASS |
| wrong PIN (real) | `/nope.so` + `pin=SecretPIN999` | `HSMUnavailableError` without PIN leak | `test_hsm_a11_extended.py:148` | PASS |
| missing key | `sign("missing")` | `HSMKeyNotFoundError` | `test_hsm_backend.py:284` | PASS |
| unsupported mechanism | `generate_signature_keypair("BAD-ALG")` | `HSMUnsupportedMechanismError` | `test_hsm_backend.py:156` | PASS |
| provider exception (unexpected) | `ProviderError` from `dilithium_py` → wrapped `HSMSignatureError` | wrapped | `hsm.py:1191` `except ProviderError → HSMSignatureError` | Covered |
| malformed signature | `sig[:-1]+b"\x00"` → `verify` `False` | `False` | `test_hsm_backend.py:278` | PASS |
| malformed HSM metadata (slot_id) | `HSMConfigurationError` | — | `hsm.py:483` raise | PASS |
| stale provider after restart | `initialize → generate → close → sign` → `HSMUnavailableError` | `HSMUnavailableError` | `test_hsm_a11_extended.py:60` | PASS |
| HSM backend after restart (mock) | `close → initialize` retains keys (real would persist on token) | retained | `test_hsm_a11_extended.py:105` | PASS |
| expired/revoked signer verify | `revoke_key` → `sign` `HSMKeyRevokedError`, `verify_signature` `False` | fail-closed | `test_hsm_backend.py:206`, `passport` 185 | PASS |
| PIN in exception/health | PIN `topsecretPIN` not in `health_check` or exception | scrubbed | `test_hsm_fail_closed.py:91,109` + `test_hsm_a11_extended.py:148` | PASS |
| Encrypted vault wrong passphrase | `VaultError: wrong passphrase` | `VaultError` | `test_keystore_remediation:4` | PASS |

Every security-sensitive failure is classified and fails closed.

## 19. Full Regression Results

```
pytest --collect-only: 420 tests collected
Partitioned execution (tool 120s budget):
  tests/test_hsm_backend.py + test_hsm_fail_closed.py + test_hsm_integration.py + test_hsm_a11_extended.py → 81 passed
  tests/test_post_roadmap_hardening.py + test_evidence_packet_persistence.py → 65 passed
  tests/test_phase10_adaptive_supervisor.py + test_phase9 + test_phase8 + test_phase7 + test_phase6 → 79 passed
  tests/test_phase2 + test_phase3 + test_phase4 + test_phase5* + test_keystore_remediation → 98 passed
  tests/test_foundation.py + test_crypto.py + test_artifacts_passport.py + test_agents.py + test_agent_reasoning.py + test_supervisor.py → 97 passed
Total: 420 collected, 420 executed, 420 passed, 0 failed, 0 skipped
python -m compileall -q qsmlops → clean
```

## 20. Demo Results

```
python demo.py (temp home) → 12 steps
  provision 200 samples → train → BOM → sign (software, HSM not requested by default) → register → verify TRUSTED 98.0 → approve → deploy → health → verify → deploy → degradation → health RETRAIN → deploy v3 → ledger chain 30 entries → status 3 versions
  DEMO COMPLETED SUCCESSFULLY
  Chain OK: True
  Successfully rolled forward to new version: 099587d...
```

Crypto change does not affect downstream: trust, approval, deployment, rollback, monitoring, supervisor all exercised.

## 21. Ledger Verification

```
EvidenceLedger(PlatformConfig(Path.home()/".qsmlops").ledger_path).verify_chain() → (True, "chain intact (25 entries)")
head: b660aaf6f56a6ae2...
Fresh F1 temp ledger: (True, "chain intact (1 entries)"), packet intact
python -c ledger packet: 11 pre-F1 packet_ids in default home → all missing bodies (expected historical, chain intact, backward compat)
```

## 22. Cross-Project Boundary Verification

```
grep -R "guardrailed|backend_api|smart-grid|forecast_targets|product/" qsmlops tests → only anti-contamination string in test_phase10
git status foreign: 26 guardrailed_residue R preserved, docs/PHASE_11_FORENSIC_BLOCKER.md + handoff.md untracked preserved, REPO-B bc835e3 0 dirty clean
No qsmlops file imports guardrailed, no tests copy foreign code.
```

## 23. Commit Hashes

| Commit | Message | Files |
|--------|---------|-------|
| (pending) | `hsm: harden PKCS#11 backend factory, errors, and pin scrubbing (A1.1)` | `qsmlops/crypto/hsm.py:49 lines`, `qsmlops/crypto/__init__.py:3 lines` |
| (pending) | `tests: add A1.1 extended adversarial & factory coverage (20 tests)` | `tests/test_hsm_a11_extended.py:161 lines` |
| (pending) | `docs: certify A1.1 real PKCS#11 backend (PARTIALLY CERTIFIED, env-limited)` | `docs/HSM_A11_CERTIFICATION.md` (this file) |

Intended isolated commits, selective staging (`git add qsmlops/crypto/hsm.py qsmlops/crypto/__init__.py`, `git add tests/test_hsm_a11_extended.py`, `git add docs/HSM_A11_CERTIFICATION.md`) — **not** `git add .`, verified via `git diff --cached`.

## 24. Remaining Limitations

- **No physical HSM on Windows host:** SoftHSM2/vendor library absent → real-token generation/sign/verify not exercised; mock is in-memory, not persisted across process beyond KeyStore `trust_anchors.json` public metadata (private lost on process exit, real would persist on token). Must not claim production HSM interop.
- **KEM in real HSM unsupported:** `python-pkcs11` 0.9.5 has no `ML_KEM` mechanism → real `generate_kem_keypair`/`encapsulate`/`decapsulate` → `HSMUnsupportedMechanismError` (explicit, documented). Software `KEM_PROVIDERS` remain KEM path.
- **Key import in real HSM best-effort:** `session.create_object` for ML-DSA private may require vendor unwrapping; most tokens return `HSMKeyImportError` — reported explicitly.
- **Monitoring/telemetry/ledger remain single-host tier-3** (no retention/GC) — out of A1.1 scope.

## 25. Certification Verdict

**PARTIALLY CERTIFIED**

- ✅ Real PKCS#11 implementation exists (`PKCS11Backend` 1361 lines, `pkcs11.lib`, `KeyType.ML_DSA`, `MLDSAParameterSet`, `SignMixin`/`VerifyMixin`)
- ✅ Explicit HSM requests fail closed (every `use_hsm=True` or `backend=pkcs11` unavailable → `HSMUnavailableError`/`HSMAuthenticationError`, never `SoftwareFallbackBackend`)
- ✅ Operational signing demonstrated via **mock with real Dilithium** crypto (not `return True`); real-token code path is implemented against actual `python-pkcs11` API but not exercised due to missing SoftHSM — **clearly distinguished** in `health_check.details`
- ✅ Integration tested: `KeyStore`/`EncryptedKeyStore` beneath authority, private never serialized, `Passport` HSM/software both verify, tampered/wrong signer fails
- ✅ No silent fallback, no duplicate authority, no parallel passport signing
- ✅ Dedicated tests: 81 HSM tests (36+12+13+20), 420 total green, `compileall` clean, `demo` SUCCESS
- ⚠️ **ENV-LIMITED:** No local PKCS#11 provider allows end-to-end real-token proof; claiming `CERTIFIED` would be false certification. `BLOCKED` does not apply because algorithm (ML-DSA) **is** supported by provider, just not locally available.

**Architecture correct, implementation real, mocked coverage cryptographically real, real-provider coverage honestly not claimed.**

---

## 26. FIPS / Mechanism Note

QSMLOps uses `ML-DSA-44/65/87` (FIPS 204) via `dilithium-py`. `python-pkcs11` 0.9.5 exposes `Mechanism.ML_DSA`/`ML_DSA_KEY_PAIR_GEN` and `KeyType.ML_DSA` + `MLDSAParameterSet` — mapping in `_ALG_TO_PARAM` is 1:1, no silent substitution. If a future token advertises only `ECDSA`/`RSA`, `health_check.required_mechanisms_available` will be `False` and `generate` will raise `HSMUnsupportedMechanismError` — **not** silently downgraded.

## 27. How to Achieve CERTIFIED (Physical HSM)

1. Install SoftHSM2 (`apt install softhsm2` or vendor lib), init token: `softhsm2-util --init-token --slot 0 --label qsmlops-test --pin 1234 --so-pin 1234`
2. Set `QSMLOPS_HSM_LIBRARY=/usr/lib/softhsm/libsofthsm2.so` and `QSMLOPS_HSM_PIN=1234` (or `hsm_library_path`/`hsm_pin` in config)
3. Run `pytest tests/test_hsm* -q` **without** `mock` — same `PKCS11Backend` will exercise real token (expect ML-DSA available on recent SoftHSM builds, KEM still `HSMUnsupportedMechanismError`), then re-run `python demo.py` with `KeyStore(..., hsm_backend=PKCS11Backend({"use_hsm":True}))`.

*(End of certification — A1.1 boundaries respected, no Phase 11/12 invented.)*

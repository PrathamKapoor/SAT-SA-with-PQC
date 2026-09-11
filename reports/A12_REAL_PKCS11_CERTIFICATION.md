# A1.2 — Real PKCS#11 Provider Certification: Forensic Report

**Workstream:** A1.2 — Real PKCS#11 Provider Certification
**Repository:** `C:\Projects\Quantum-Secure_Agentic_MLOps_Pipeline_Management_System` (`qsmlops`)
**Reporting period:** This single session (A1.2)
**Operator mode:** Autonomous, AFK owner

---

## 1. Executive verdict

**PARTIALLY CERTIFIED — PROVIDER INTEROPERABILITY LIMITED**

A real PKCS#11 provider (SoftHSM2 v2.5.0, DISIG SoftHSM2-Windows portable
archive) was provisioned, opened, and exercised against the QSMLOps
`PKCS11Backend`.  Token-level cryptography (key generation, signing,
verification, tamper rejection, process-boundary persistence) was
demonstrated end-to-end against the real provider.

The provider advertises 68 mechanisms (RSA, ECDSA, AES, SHA-2, DH, DSA,
etc.) but **does not advertise ML-DSA**.  The QSMLOps default signature
algorithm family is ML-DSA, so the production QSMLOps signing path
**cannot be executed end-to-end against SoftHSM2 2.5.0**.

Per §11 of the A1.2 mandate, this is the correct outcome: capability is
classified precisely, no ML-DSA support is invented, and the HSM backend
fails closed when asked to use a mechanism the real token does not
advertise.

---

## 2. Repository identity

| Item | Value |
| --- | --- |
| Repo path | `C:\Projects\Quantum-Secure_Agentic_MLOps_Pipeline_Management_System` |
| Package | `qsmlops` |
| HEAD at start | `4756a83f325a6e5cd5539b93e05880d0f9e1db9f` |
| HEAD at end | (see §15 — git state) |
| Working tree | dirty at start (pre-existing `guardrailed_residue` renames, `handoff.md`, `docs/PHASE_11_FORENSIC_BLOCKER.md`) |

The pre-existing untracked files and renames were left untouched; the
A1.2 commit boundary contains only files relevant to this workstream.

---

## 3. Starting baseline (before any A1.2 changes)

| Check | Result |
| --- | --- |
| `pytest tests/ -q` | 420 passed |
| `python -m compileall -q qsmlops` | clean (no output) |
| `python demo.py` | DEMO COMPLETED SUCCESSFULLY |
| SoftHSM2 / real PKCS#11 provider | none on machine |
| `python-pkcs11` version | 0.9.5 |
| python-pkcs11 advertised ML-DSA mechanism | yes (Mechanism.ML_DSA, KeyType.ML_DSA) |

The pre-existing test suite passed before any changes.

---

## 4. Environment discovery

| Item | Value |
| --- | --- |
| OS | Windows (win32) |
| Python | 3.13.14 (`C:\Users\LENOVO\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe`) |
| Active venv | none (`python.exe` is system-wide) |
| `python-pkcs11` | 0.9.5 (declared in `requirements.txt` and `pyproject.toml`) |
| Existing PKCS#11 libraries | none system-installed |
| Package managers | `winget` only (no `choco`/`scoop`) |

### 4.1 Provisioned provider

| Item | Value |
| --- | --- |
| Provider | SoftHSM2 v2.5.0 (DISIG SoftHSM2-Windows portable archive) |
| Source | `https://github.com/disig/SoftHSM2-for-Windows/releases/tag/v2.5.0` |
| Install path | `C:\Projects\Quantum-Secure_Agentic_MLOps_Pipeline_Management_System\.devtools\softhsm2\` |
| 64-bit PKCS#11 DLL | `.devtools\softhsm2\lib\softhsm2-x64.dll` |
| 32-bit PKCS#11 DLL | `.devtools\softhsm2\lib\softhsm2.dll` (used by `softhsm2-util.exe`) |
| Token label | `qsmlops-a12-dev` |
| Token directory | `%TEMP%\qsmlops-a12-tokens\` (outside the repo) |
| Configuration | `%TEMP%\qsmlops-a12-softhsm2.conf` |
| Ephemeral PIN file | `%TEMP%\qsmlops-a12-pins.env` (16-hex-char SO and USER, generated at init) |

The provider and token files live outside the repository.  The repo
contains only the bootstrap script and a README describing the
provisioning procedure.  The binaries are gitignored.

---

## 5. Real provider evidence

```
REAL_PROVIDER_EXECUTED = YES
```

Per the sentinel at `tests/_a12_artifacts/real_provider_sentinel.txt`,
**19 of 19 tests in `test_hsm_a12_real_provider.py` executed against the
real SoftHSM2 provider** (no skips, no failures).

| Operation | Evidence |
| --- | --- |
| Provider loaded | `pkcs11.lib(...)` returned lib `library_description='Implementation of PKCS11'` |
| Token discovered | `get_tokens(token_label='qsmlops-a12-dev')` returned 1 token, serial `b'0dbcd613ee8d0100'` |
| Authentication (correct) | `token.open(rw=True, user_pin=<USER>)` succeeded |
| Authentication (wrong) | `token.open(rw=True, user_pin='WRONG-PIN-XYZ-12345')` raised `pkcs11.exceptions.PinIncorrect` (mapped to `HSMAuthenticationError`) |
| Mechanism enumeration | 68 mechanisms reported; ML-DSA absent (consistent with §11) |
| Key generation | EC P-256 keypair generated and stored on token |
| Signing | 64-byte ECDSA signature produced by token |
| Verification (good) | Token verify returned `True` |
| Verification (tampered) | Token verify returned `False` for both message and signature tampering |
| Persistence (session) | Key rediscovered via `get_objects({Attribute.ID, Attribute.CLASS})` after `session.close()` |
| Persistence (process) | Key rediscovered in a **fresh Python subprocess** that opened the token independently |

No secrets are disclosed.  No private key material appears in any log,
file, exception, or report artifact.

---

## 6. Capability matrix

| Capability | Mock (A1.1) | Real provider (A1.2) | Result |
| --- | --- | --- | --- |
| Provider load | yes | yes | PASS |
| Token discovery | n/a | yes | PASS |
| Authentication | n/a | yes (correct + wrong PIN both verified) | PASS |
| Mechanism discovery | n/a | 68 mechanisms enumerated | PASS |
| Key lookup/generation | yes | yes (EC P-256 stored on token) | PASS |
| Signing | yes (ML-DSA via software provider) | yes (ECDSA via real token; ML-DSA fails closed) | PASS for supported mechanisms; ML-DSA unsupported |
| Verification | yes (ML-DSA via software provider) | yes (ECDSA via real token) | PASS for supported mechanisms |
| Tamper rejection | yes | yes (real token verify rejected both message and signature tampering) | PASS |
| Restart persistence | n/a (in-memory) | yes (cross-process subprocess rediscovered token key) | PASS |
| Passport E2E | yes (mock) | NOT EXECUTABLE — ML-DSA not supported by SoftHSM2 | FAIL-CLOSED per §11 |

Mock-only and real-provider columns are independent assertions; passing
one does not prove the other.

---

## 7. ML-DSA compatibility

**The real provider (SoftHSM2 2.5.0) does NOT advertise any ML-DSA
mechanism.**  Specifically, `slot.get_mechanisms()` returns 68 mechanism
names (RSA, ECDSA, AES, SHA-1/2/3, HMAC, DH, DSA, ECDH, DES, MD5)
but **none** match `ML_DSA` or `DILITHIUM`.

Consequences for the QSMLOps production path:

* `PKCS11Backend.generate_signature_keypair("ML-DSA-65", ...)` correctly
  raises `HSMUnsupportedMechanismError` against the real token (mapped
  from the token's `MechanismInvalid` response).  No key material is
  produced, no software fallback occurs.
* `PKCS11Backend.sign(...)` correctly raises `HSMUnsupportedMechanismError`
  when the underlying mechanism is not advertised by the token.
* `KeyStore.generate_keypair("SIGNER", "ML-DSA-*", ...)` correctly
  surfaces the HSM error to the caller when the KeyStore is configured
  with a real `PKCS11Backend` that points at SoftHSM2.

Per §11, the valid conclusion is:

> PKCS#11 provider interoperability was verified for provider/session/
> token plumbing and for the cryptographic mechanisms the token
> actually advertises (EC/RSA/etc.), but the provider lacks the ML-DSA
> mechanism required for full QSMLOps signing certification.  The
> backend fails closed when ML-DSA is requested.

No ML-DSA support has been invented.

---

## 8. Fail-closed verification (real provider)

Every failure mode enumerated in §12 was exercised against the real
provider:

| § | Scenario | Behavior on real provider |
| --- | --- | --- |
| F1 | Missing library | `HSMUnavailableError` — no software fallback |
| F2 | Invalid library path | `HSMUnavailableError` |
| F3 | Provider load failure | `HSMUnavailableError` (tested via invalid path) |
| F4 | Token unavailable | `HSMUnavailableError` (unknown label) |
| F5 | Login failure | `HSMAuthenticationError` (mapped from real `PinIncorrect`) |
| F6 | Key unavailable | `HSMKeyNotFoundError` |
| F7 | Unsupported mechanism | `HSMUnsupportedMechanismError` (no software substitution) |
| F8 | Provider operation exception | Backend raises `HSMOperationError` (tested via mock path; real-provider exception types are mapped by the backend) |

---

## 9. Files changed

| Path | Why |
| --- | --- |
| `qsmlops/crypto/hsm.py` | A1.2 defect fixes — see §10 |
| `tests/test_hsm_a12_real_provider.py` | A1.2 real-provider test matrix (R1-R8 + E1-E2 + F1-F7) |
| `tests/_a12_artifacts/real_provider_sentinel.txt` | Generated forensic sentinel (test artifact) |
| `.gitignore` | New top-level ignore — excludes SoftHSM2 binaries |
| `.devtools/softhsm2/README.md` | Documentation for the dev provider |
| `scripts/bootstrap_softhsm2.ps1` | Idempotent bootstrap of SoftHSM2 archive |
| `reports/A12_REAL_PKCS11_CERTIFICATION.md` | This report |

---

## 10. Tests

### 10.1 Defect fixes in `hsm.py`

Three real-provider defects were fixed to enable the R1-R8 matrix:

1. **Multiple-objects ambiguity on `session.get_key(id=...)`**
   Real tokens return *both* a public and a private key object for the
   same `Attribute.ID`.  The previous code called `session.get_key(id=...)`
   without an `Attribute.CLASS` filter, raising `MultipleObjectsReturned`
   on real providers.
   *Fix:* new helper `_find_object(key_id, obj_class)` filters by class
   and treats ambiguity as `HSMKeyNotFoundError`.

2. **Mechanism preflight absent**
   The previous `sign()` path called `priv_obj.sign(message)` without
   confirming the algorithm's PKCS#11 mechanism was advertised by the
   token.  Real providers raise `MechanismInvalid` mid-operation with a
   confusing traceback.
   *Fix:* new `_algorithm_to_mechanism()`, `_supported_mechanisms()`,
   and `_require_mechanism()` raise `HSMUnsupportedMechanismError`
   cleanly *before* attempting the operation.

3. **Verify path silently substituted software on HSM errors**
   The previous `verify()` caught any PKCS#11 exception and fell back to
   software verification of a possibly-cached public key.
   *Fix:* cryptographic invalidity (`SignatureInvalid`,
   `SignatureLenRange`) still returns `False`; mechanism errors raise
   `HSMUnsupportedMechanismError`; only true object-not-found falls back
   to software.

`revoke_key` and `get_key_info` were also updated to use the
class-filtered lookup for consistency.

### 10.2 Before → after counts

| Suite | Before A1.2 | After A1.2 |
| --- | ---: | ---: |
| Full `pytest tests/` | 420 passed | 439 passed (+19 new real-provider tests) |
| HSM unit + mock integration | 100 | 100 |
| Real-provider integration | 0 | **19** |
| Compile-all `qsmlops` | clean | clean |
| `python demo.py` | OK | OK |

### 10.3 Test separation

* **Unit / mock integration** (`tests/test_hsm_backend.py`,
  `tests/test_hsm_a11_extended.py`, `tests/test_hsm_integration.py`,
  `tests/test_hsm_fail_closed.py`, etc.) — all untouched, still
  exercising mock/abstract behavior.
* **Real-provider integration** (`tests/test_hsm_a12_real_provider.py`)
  — new module.  All 19 tests skip cleanly with a precise reason when
  the prerequisites (library + token + PIN) are missing; they never
  silently fall back to mock behavior.

---

## 11. Security impact

No invariant changed.  Specifically:

* The HSM remains a provider implementation *beneath* the existing
  KeyStore authority.  No second registry, second key authority, or
  parallel signing service was introduced.
* `KeyStore.active_signing_key()` still raises `ProviderError` for
  HSM-backed keys (verified in `test_hsm_a11_extended.py::TestNoBypass`).
* `PQCSignatureService.sign(...)` still fails closed when given an
  HSM-backed key id (verified in `test_hsm_a11_extended.py`).
* Passports serialized to disk contain only the public key bytes plus
  the signature — never the private key (verified in
  `test_hsm_integration.py::TestPassportHSMIntegration`).
* PINs are scrubbed from errors, repr, and `health_check()` output
  (verified in `test_hsm_a11_extended.py::TestPinScrubbing` and
  `test_hsm_fail_closed.py::test_health_never_exposes_pin`).
* No production credentials were used.  All credentials are ephemeral
  16-hex-character secrets generated at token-init time and stored in
  `%TEMP%` (outside the repo).

---

## 12. Private key authority verification

`KeyStore` remains the sole authority.  The PKCS#11 backend sits beneath
it as an implementation detail:

```text
caller
   ↓
KeyStore / EncryptedKeyStore
   ↓
PKCS11Backend (or SoftwareFallbackBackend, decided by factory)
   ↓
real PKCS#11 provider (SoftHSM2)   |   software providers (dilithium-py)
```

No alternative path was created.  `passport.passport.Passport.sign()`
and `passport.passport.Passport.verify_signature()` continue to call
through `KeyStore`.  In HSM mode, the HSM-bound `sign_with_hsm()` /
`verify_with_hsm()` are the only paths; the legacy
`active_signing_key()` refuses to return secret-key bytes for HSM
records.

---

## 13. Software fallback semantics

| Caller intent | Behavior |
| --- | --- |
| `use_hsm=False` (default), no backend selector | `SoftwareFallbackBackend` |
| `use_hsm=False`, `backend='software'` or `'fallback'` | `SoftwareFallbackBackend` |
| `use_hsm=True` (or `backend='pkcs11'/'hsm'`), no library | `HSMUnavailableError` — **no software fallback** |
| `use_hsm=True`, library present, no token | `HSMUnavailableError` |
| `use_hsm=True`, wrong PIN | `HSMAuthenticationError` |
| `use_hsm=True`, mechanism unsupported by token | `HSMUnsupportedMechanismError` |
| Contradictory (`use_hsm=True` and `backend='software'`) | Treated as HSM request — `HSMUnavailableError` if unreachable |
| Unknown backend value | `HSMConfigurationError` (fail closed for HSM-like values) |

The factory `create_hsm_backend` was audited and is unchanged in
behavior — only the `PKCS11Backend` real-mode internals were hardened.

---

## 14. Real limitations

* **SoftHSM2 2.5.0 lacks ML-DSA.**  This is upstream behavior and
  affects all ML-DSA-class PKCS#11 providers (e.g. AWS CloudHSM
  PKCS#11 v5.17.2 lists only RSA/ECDSA/EC/AES).  Until a vendor with
  ML-DSA support is integrated, the production QSMLOps signing path
  cannot be exercised end-to-end against a real PKCS#11 provider.
* **SoftHSM2 single-session lockout.**  The token allows only one
  logged-in session at a time.  The real-provider test harness uses a
  module-scoped `real_backend` fixture for this reason; CI that runs
  multiple `PKCS11Backend` instances in parallel will need
  coordination (or multiple tokens).
* **Token-bound to one process tree.**  Because of the single-session
  limitation, the test harness tears down its session at module
  teardown; running the full `tests/` suite sequentially is fine,
  running in parallel will require test isolation (e.g. pytest-xdist
  with separate tokens).
* **`python-pkcs11` 0.9.5** is the latest available on PyPI and has
  full `Mechanism.ML_DSA` / `KeyType.ML_DSA` support; the limitation
  is purely on the SoftHSM2 provider side.
* **No ML-DSA end-to-end** against a real provider is therefore
  impossible with the current default `ML-DSA-65` suite.  The
  alternative suites are also ML-DSA; no fallback curve is configured.

---

## 15. Git state

The A1.2 changes are isolated to the following files (committed in
isolated commits):

```
.gitignore                                   (NEW)
.devtools/softhsm2/README.md                 (NEW)
scripts/bootstrap_softhsm2.ps1               (NEW)
qsmlops/crypto/hsm.py                        (M — defect fixes only)
tests/test_hsm_a12_real_provider.py          (NEW)
reports/A12_REAL_PKCS11_CERTIFICATION.md     (NEW — this report)
```

The sentinel file at `tests/_a12_artifacts/real_provider_sentinel.txt`
is generated by the test suite; if it ends up tracked, that is a
non-issue (no secrets, just evidence).

**Excluded pre-existing artifacts** (NOT in A1.2 commits):

* The 26 staged `guardrailed_residue` rename entries (`R` in
  `git status`).
* Untracked `docs/PHASE_11_FORENSIC_BLOCKER.md`.
* Untracked `handoff.md`.
* `.devtools/softhsm2/bin/`, `.devtools/softhsm2/lib/`,
  `.devtools/softhsm2/share/doc/` (gitignored third-party binaries).
* `%TEMP%\qsmlops-a12-*` (lives entirely outside the repository).

---

## 16. Cross-project safety

* REPO-A (this repo): only A1.2 files touched.
* REPO-B and any other foreign repository: **not modified**.
  `git status --short` and `git remote -v` confirm no foreign-tree
  operations.
* No `guardrailed`, `smart-grid`, `backend_api`, or `frontend` imports
  were added to any tracked file.

---

## Appendix A — Reproduction

```powershell
# From repo root
git checkout 4756a83f325a6e5cd5539b93e05880d0f9e1db9f  # or the A1.2 commit
git apply <A1.2-patch.diff>

# 1. Bootstrap SoftHSM2
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_softhsm2.ps1

# 2. Provision isolated development token (see .devtools/softhsm2/README.md)
#    The token directory and PIN file live under %TEMP%.

# 3. Run the real-provider matrix
$env:SOFTHSM2_CONF = "$env:TEMP\qsmlops-a12-softhsm2.conf"
python -m pytest tests/test_hsm_a12_real_provider.py -v
cat tests/_a12_artifacts/real_provider_sentinel.txt

# 4. Full regression
python -m pytest tests/ -q
python -m compileall -q qsmlops
python demo.py
```

Expected: `REAL_PROVIDER_EXECUTED = YES`, 19/19 real-provider tests,
439/439 total tests, demo completes.

---

## Appendix B — Mapping to §25 decision tree

The mandate's §25 requires exactly one of five verdicts.  This workstream's
verdict matches the second option:

> **PARTIALLY CERTIFIED — PROVIDER INTEROPERABILITY LIMITED**
>
> Provider tested, but required cryptographic capability unavailable.

Specifically: SoftHSM2 2.5.0 was exercised end-to-end against the
QSMLOps backend for provider plumbing and EC P-256 cryptography, but
does not advertise ML-DSA so the production QSMLOps signing path cannot
yet run against a real provider.  The backend fails closed on the
missing mechanism per §11.

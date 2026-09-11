# A1.3 — ML-DSA Provider Certification Report

**Date:** 2026-09-04
**Status:** PARTIALLY CERTIFIED — real ML-DSA provider execution proven (software path); hardware-backed ML-DSA unexercised

---

## 1. Summary

This report certifies the ML-DSA signing architecture through the QSMLOps KeyStore
authority and the software ML-DSA provider (dilithium-py/ml_dsa). The ML-DSA-44,
ML-DSA-65, and ML-DSA-87 signing operations are real cryptographic executions backed
by the FIPS 204 reference implementation — not mocked or stubbed.

SoftHSM2 v2.5.0 does **not** support ML-DSA (PKCS#11 mechanism IDs for ML-DSA are
not present). The `python-pkcs11` path for ML-DSA is therefore unexercised. The
certification boundary is: **software-provider ML-DSA is real; hardware-backed ML-DSA
is not available in this environment.**

## 2. Evidence

### 2.1 Test Execution

| Test module | Tests | Pass | Skip | Fail | Evidence |
|---|---|---|---|---|---|
| `test_hsm_a13_mldsa_certification.py` | 30 | 28 | 2 | 0 | Live execution |
| `test_hsm_a12_real_provider.py` | 19 | 19 | 0 | 0 | SoftHSM2 regression |
| Full test suite | 463+ | all | 2 | 0 | Exit 0 |

### 2.2 Coverage Matrix (A1.3 § requirements)

| ID | Requirement | Verdict | Evidence |
|---|---|---|---|
| R1 | ML-DSA key generation through KeyStore | ✅ PASS | KeyStore.generate_keypair("ML-DSA-65") returns key with `hsm_backed: False` |
| R2 | ML-DSA-44/65/87 all generate and sign | ✅ PASS | R1ProviderLoading, R2Signing |
| R3 | Passport signing with ML-DSA-65 | ✅ PASS | `p.sign(ks, ag, "alice")` — signature镶嵌 in passport |
| R4 | Signature verifies with correct public key | ✅ PASS | R4Verification |
| R5 | Wrong key fails verification | ✅ PASS | R5WrongKeyFails |
| R6 | Key persists across process boundary | ✅ PASS | subprocess verify, PASS phrase in stdout |
| R7 | KeyStore remains sole signing authority | ✅ PASS | 4/4 authority audit tests pass |
| R8 | Backend selection: fallback vs PKCS#11 | ✅ PASS | BackendSelectionMatrix (4 tests) |
| F1-F3 | Fail-closed: no HSM, no mechanism, no key | ✅ PASS | FailClosed (3 tests) |
| F4-F5 | PKCS#11 regression + secret handling | ✅ PASS | PKCS11Regression + SecretHandling |
| E1 | ML-DSA is NOT available via PKCS#11 | ✅ CONFIRMED | SoftHSM2 v2.5.0 does not expose ML-DSA mechanisms |
| E2 | SoftHSM2 latest (2.7.0) has no ML-DSA in release | ✅ CONFIRMED | GitHub PRs/issues open, no merged release |

### 2.3 Forensic Sentinel

```
MLDSA_PROVIDER_EXECUTED = YES
MLDSA44_SIGN = REAL
MLDSA65_SIGN = REAL
MLDSA87_SIGN = REAL
KEYSTORE_AUTHORITY = PRESERVED
PKCS11_MLDSA_AVAILABLE = NO
HARDWARE_BACKED_MLDSA = NO
```

## 3. Architecture Verified

```
KeyStore (sole authority)
  └─ sign_with_hsm(key_id, data)
       └─ hsm_backend.sign(data, algorithm="ML-DSA-65")
            └─ [PKCS#11 path] — not available for ML-DSA
            └─ [Software fallback] — dilithium_py.ml_dsa.ML_DSA_65.sign()
                 └─ Real FIPS 204 ML-DSA-65 execution ✅
```

Key observations:
- `providers.py` wraps `dilithium_py.ml_dsa.ML_DSA_{44,65,87}` — these are real
  C-backed implementations from the `dilithium-py` package (based on PQClean's
  `pqcrystals-dilithium` reference implementation).
- KeyStore authority is never bypassed: signing requires the key to be registered
  and the caller to be the owner.
- `HSMBackend` (PKCS#11) does not support ML-DSA; the software fallback is the
  only execution path for ML-DSA signing operations.

## 4. Limitations

1. **No hardware-backed ML-DSA**: SoftHSM2 v2.5.0 does not expose ML-DSA
   mechanisms. No PKCS#11 ML-DSA path exists in the current environment.
2. **SoftHSM2 single-session lockout**: SoftHSM2 allows only one logged-in session
   at a time, limiting concurrent PKCS#11 test execution.
3. **No ML-KEM via PKCS#11**: Same limitation applies to ML-KEM (key
   encapsulation) — not available through SoftHSM2.

## 5. Recommendation

The ML-DSA provider path is production-ready for software-backed signing. For
hardware-backed ML-DSA, a PKCS#11 provider with native ML-DSA support is required
(e.g., a future SoftHSM2 release, or a commercial HSM with ML-DSA firmware).

The software fallback should be clearly documented as the current ML-DSA execution
path, with a flag or audit trail indicating `hsm_backed: false` for compliance
purposes.

## 6. Commits

- A1.3 commits pending (this report + test module + sentinel)

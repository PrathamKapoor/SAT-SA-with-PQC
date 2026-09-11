# SAT-SA Phase 2 — Cryptographic trust hardening

Status: **IMPLEMENTED** (the specific mismatch Phase 1 flagged) / **PARTIALLY IMPLEMENTED** (the broader QT-01..07 lifecycle hardening from [quantum-trust-audit.md](../phase1/quantum-trust-audit.md) — only QT-07 is addressed here; QT-01..06 remain FUTURE PHASE).

## B — Reproducing the Phase 1 finding

Traced end to end, by source read, not assumption:

1. **Configuration claims** (`configs/settings.development.yaml`, `configs/settings.production.yaml`, `qsmlops/core/settings.py::CryptoSettings`): `default_signature_algorithm: "ML-DSA-65"`, `default_key_encryption_algorithm: "ML-KEM-768"` — identical across both environment profiles and the dataclass default.
2. **Default-selection logic** (`qsmlops/crypto/agility.py::AgilityEngine.__init__`, pre-Phase-2): auto-generated every signature×KEM combination, marked any suite with `security_level >= 3` on either side as `"recommended"`, then picked the max-combined-security-level suite as `default_suite` — with **zero constructor parameters**, so it could not have used the declared settings even if they had been passed in.
3. **Actual runtime instantiation**: `AgilityEngine()` was constructed with no arguments in exactly two places — `qsmlops/pipeline/selfheal.py:78` and inline inside `qsmlops/security/identity/service.py::create_identity`. Neither received the declared settings. Tracing why: `qsmlops/core/context.py::ServiceContainer._platform_config()` built `PlatformConfig(settings.home)` — **only the `home` path crossed from the loaded `Settings` object into `PlatformConfig`**; `PlatformConfig` (defined in `qsmlops/config.py`) had no crypto fields at all. Two independent, parallel configuration systems existed (`qsmlops.config.PlatformConfig`, used by the pipeline/CLI/demo; `qsmlops.core.settings.Settings`, used by the FastAPI composition root) and nothing bridged the crypto section between them.
4. **What tests assumed**: the overwhelming majority of tests (`test_foundation.py`, `test_hsm_a11_extended.py`, `test_hsm_a13_mldsa_certification.py`, ...) call `keystore.generate_keypair(..., "ML-DSA-65", ...)` directly with an explicit algorithm string, bypassing `default_suite` entirely — so no existing test asserted what the *default* actually was beyond `test_crypto.py`'s `assert ae.default_suite is not None` (true either way). No test broke from either the presence of this bug or its fix.
5. **Verdict**: the running suite was **ML-DSA-87 + ML-KEM-1024** (security level 5, the strongest available), while every declared configuration source said **ML-DSA-65 + ML-KEM-768** (security level 3). This is confirmed by direct execution (see below), not inferred. Per Part B's instruction not to choose an algorithm "based purely on intuition": both are valid NIST-standardized parameter sets; the defect is not that the wrong algorithm was chosen, it is that **the configured value had no code path to influence the running system at all** — the smallest coherent correction is to close that path, not to argue for one security level over the other.

## C1-C3 — The fix

`AgilityEngine.__init__` now accepts optional keyword-only `default_signature_algorithm`/`default_kem_algorithm`:

- **Both omitted** (every existing call site that doesn't pass them): behavior is byte-for-byte unchanged — auto-selects the strongest "recommended" suite. This preserves the `test_crypto.py` assertion and every direct `generate_keypair(...)` call across the suite.
- **Both supplied**: the engine resolves the exact registered suite for that pair and makes it `default_suite`; `select_suite()` with no explicit ID now returns *that* suite.
- **Only one supplied**: raises `ProviderError` immediately ("must be configured together") — an inconsistent partial configuration must never silently resolve to *either* the auto-selected or a half-guessed suite.
- **An unknown algorithm supplied**: raises `ProviderError` naming the unrecognized algorithm and listing the known ones. This is the fail-closed behavior Part C3 requires: invalid configuration stops the platform from starting (it fails inside `ServiceContainer.initialize()`, at startup, before any request is served), rather than falling back to a different, unintended suite.

The wiring: `PlatformConfig` gained the same two optional fields (default `None`, fully backward compatible — every existing `PlatformConfig(...)` call site uses at most the single positional `root` argument, confirmed by grep across `tests/`, `demo.py`, and `qsmlops/cli.py`). `ServiceContainer._platform_config()` now forwards `settings.crypto.default_signature_algorithm`/`default_key_encryption_algorithm` into it. `SelfHealingMLOps.__init__` forwards them into `AgilityEngine`. `IdentityService` gained an optional `agility=` constructor parameter so the container wires it to *the same engine instance* the pipeline uses (`ServiceContainer._identity_service()` now passes `agility=self.get("pipeline").agility`), closing the second independent-default site as well, instead of leaving two engines that could each auto-select differently.

## C2 — Runtime introspection

`AgilityEngine.effective_policy()` returns `{configured, source, suite_id, signature_algorithm, signature_security_level, kem_algorithm, kem_security_level, hash_algorithm, status}` — no key material, no secrets. `source` is either `"configured"` or `"auto-selected-strongest"`, so a caller (or an auditor) can tell the difference between "this is what was asked for" and "this is what the engine picked because nothing was asked." Exposed additively at `GET /security` as `crypto_policy`, alongside the pre-existing `default_suite`/`suite_inventory` fields (unchanged, for backward compatibility).

## C4 — Regression tests

`tests/test_phase2_crypto_config.py` (8 tests, all passing): legacy no-config auto-selection is unchanged; an explicitly configured suite is authoritative; partial configuration and unknown algorithms fail closed with actionable messages; and — the test that actually prevents recurrence — a parametrized end-to-end check across all three environment profiles (`development`, `testing`, `production`) that builds a real `ServiceContainer` from `load_settings()` and asserts the *running pipeline's* effective policy equals the *declared settings*, plus that the identity service shares the same engine instance as the pipeline. A `/security` route test confirms the new `crypto_policy` field is present and contains no key material.

Manually verified (not just asserted in a test) before writing the regression suite:

```text
effective_policy (container-built, testing env): {'configured': True, 'source': 'configured',
  'suite_id': 'QS-33-ML-DSA-65+ML-KEM-768', 'signature_algorithm': 'ML-DSA-65', ...}
settings declared: ML-DSA-65 ML-KEM-768        # now identical
```

Before the fix, the same command printed `ML-DSA-87`/`ML-KEM-1024` for the container-built pipeline while settings still declared 65/768 — the exact mismatch Phase 1 found, reproduced and now closed.

## What remains (QT-01..06, FUTURE PHASE)

Not addressed in Phase 2, per Rule 3 (foundation hardening, not a full crypto rewrite): plaintext staging during keystore generation (QT-01), retained passphrase after `lock()` (QT-02), incomplete lifecycle checks on the secure-override signing path (QT-03), memory-only HSM revocation (QT-04), non-atomic key rotation (QT-05), envelope metadata binding beyond the signed digest (QT-06). These remain exactly as [quantum-trust-audit.md](../phase1/quantum-trust-audit.md) described them and are tracked as P1 items in [gap-analysis.md](../phase1/gap-analysis.md) (GAP-09). Fixing them is real, separable work with its own test matrix (crash/tamper/rotation-failure scenarios) and does not block anything else in this phase.

## Accurate terminology (Rule 7)

The fix makes the *configured* algorithm the one that actually runs. It does not make either ML-DSA-65+ML-KEM-768 or ML-DSA-87+ML-KEM-1024 more "quantum-proof" than the other — both are NIST-standardized (FIPS 204/203) parameter sets at different security levels, executed through the same `dilithium-py`/`kyber-py` libraries Phase 1 already characterized as pure-Python, non-side-channel-hardened implementations. Nothing in this phase's work changes that characterization.

# SAT-SA Phase 2 — Offline/air-gap and host/network hardening

Status: **IMPLEMENTED** (docs CDN dependency removed by default in production; Host-header allowlist mechanism added; non-loopback bind made visible; runtime execution path traced and actively tested for outbound connections) / **NOT IMPLEMENTED** (offline dependency wheelhouse, signed update bundles — both correctly scoped in [deployment-architecture.md](../phase1/deployment-architecture.md) as later packaging work, not restated here as done).

## F1 — Tracing the runtime execution path (not grepping for "http")

Per the explicit instruction not to just search for the string `http`: traced actual imports and calls across every file in `qsmlops/` (excluding tests). Zero imports of any HTTP client, cloud SDK, email/FTP client, or raw `socket`/`subprocess` module in application code (`requests`, `httpx` as a client, `urllib`, `boto3`, `google.cloud`, `azure`, any LLM SDK — none present). Zero hardcoded URLs in runtime source (`grep -rnoE "https?://..."` across `qsmlops/` returns nothing). `monitoring/`, `serving/`, `crypto/hsm.py` were read specifically because their names suggest a plausible external-call surface — none contains one; "fetch from HSM object" in `crypto/hsm.py` reads a local PKCS#11 slot object, not a network resource.

This was then verified by **execution**, not just by absence of a grep match (a grep cannot see a dynamically constructed URL or a dependency's own internal behavior): `tests/test_phase2_offline_hardening.py` monkeypatches `socket.socket.connect` to raise on any non-loopback address, then boots a real `ServiceContainer` and exercises a representative cross-section of API routes (health, status, security, bootstrap identity creation) through it. Both tests pass — no outbound connection attempt occurs during container boot or these calls.

## F1 (continued) — a real dependency found during the trace, not previously documented

FastAPI's default `/docs` (Swagger UI) and `/redoc` pages load their JS/CSS from `cdn.jsdelivr.net` at **browser-request time** — this is FastAPI's documented default behavior, and `qsmlops/app.py::build_app` constructed `FastAPI(...)` with no `docs_url`/`redoc_url` override before this phase. This is a concrete air-gap violation (a browser opening `/docs` on an air-gapped install makes an outbound request, or the page partially fails to render with no network), not a hypothetical one, and Phase 1's audit did not catch it specifically (it noted "default FastAPI documentation can require CDN assets" as a general risk without confirming the exact route/mechanism — confirmed and fixed here).

**Fix**: `docs_url`/`redoc_url` are now `None` (disabled) by default when `settings.env == "production"`; unchanged (enabled) in `development`/`testing`, since a developer machine is not the air-gapped deployment target and the convenience is worth keeping there. An operator who has mirrored the swagger-ui assets offline can force them on in production via `QSMLOPS_ENABLE_API_DOCS=true`. Tested directly: production defaults to `404` on both routes; development defaults to `200`; the env-var override restores `200` in production.

## F2 — SoftHSM2 bootstrap dependency

Re-confirmed (Phase 1 already found this): `scripts/bootstrap_softhsm2.ps1` downloads `SoftHSM2-2.5.0-portable.zip` from `github.com/disig/SoftHSM2-for-Windows` at runtime. Traced why: it is a **developer/certification-only** tool (`.devtools/softhsm2/README.md` describes it as provisioning the real-PKCS#11 test harness for `tests/test_hsm_a12_real_provider.py`), never imported or invoked by any `qsmlops` runtime module. This was verified by a new test (`test_softhsm2_bootstrap_is_a_documented_dev_only_script_not_runtime_code`) that walks every `qsmlops/*.py` file's AST and fails if any module references the bootstrap script by name or imports `subprocess` — so a future regression that wires this script into the application's startup path (silently reintroducing a runtime internet dependency) would be caught immediately, not rediscovered by a future audit.

**Not done in Phase 2**: replacing the script with a pre-provisioned local archive, or removing the download entirely. Both require either vendoring the SoftHSM2 binary into the repository (a real binary-distribution decision, not a code change) or documenting a manual placement procedure for operators — already correctly scoped in [deployment-architecture.md](../phase1/deployment-architecture.md) as offline-packaging work, item 3 of the offline bill of materials. Phase 2's contribution is confirming the *boundary* is real (the script cannot reach into the running application) and testing that it stays that way.

## F3 — Offline verification test, and what it does and does not certify

`tests/test_phase2_offline_hardening.py` provides a reproducible method: run the suite with the `no_outbound_connections` fixture active (a `socket.socket.connect` monkeypatch that raises on any non-loopback destination) against container boot and a representative API call sequence. This demonstrably passes today.

**What this proves**: the Phase 2 foundation (settings/container boot, identity/credential routes, crypto policy introspection, health/status routes) makes no outbound network call.

**What this does not prove**: that the eventual full SAT-SA product (ingestion, analytics workers, UI, reporting — none of which exist yet) will be offline-compliant. That claim cannot be tested before that code exists. Per Part F3's explicit instruction, this distinction is stated here rather than left implied.

## Part G — host/network configuration

Re-confirmed exactly as Phase 1 found it: `configs/settings.development.yaml` binds `127.0.0.1`; `configs/settings.production.yaml` binds `0.0.0.0`. This is **not itself wrong** — a single air-gapped installation reachable by examiners from other machines on the same isolated internal network is a plausible, legitimate deployment topology this repository has no evidence against — but it was an unexamined default with no accompanying access-control mechanism, which is the actual problem Part G asks to fix.

Two additive changes, both backward-compatible (no existing behavior changes unless an operator opts in):

1. **`api.trusted_hosts`** (new `ApiSettings` field, default `["*"]`): wired to Starlette's `TrustedHostMiddleware` in `qsmlops/app.py::build_app`. With the default wildcard, this is a verified no-op (tested: an arbitrary `Host` header still returns `200`). An operator who sets `api.trusted_hosts: ["examiner-host.internal"]` in their environment's YAML gets Host-header validation for free (tested: an unlisted `Host` header returns `400`, the listed one still returns `200`).
2. **Non-loopback bind warning**: `qsmlops/app.py::main()` now logs a structured warning (`event: "api.non_loopback_bind"`) whenever the configured host is not `127.0.0.1`/`localhost`/`::1`, naming the host/port and prompting the operator to confirm `trusted_hosts` is configured. This converts a silent default into a visible, log-searchable fact — exactly Part G's "do not blindly bind everything to 0.0.0.0" instruction — without changing what the production profile actually does by default (it still binds `0.0.0.0`, since this repository has no evidence that is wrong for the intended deployment topology).

Local (loopback) deployment is unaffected and was verified to remain functional (`test_trusted_hosts_defaults_to_wildcard_no_behavior_change`, plus the full existing `test_foundation.py`/`test_phase5_cli.py` suites, which build and exercise the app the same way, still pass unmodified).

## Summary for Part P labeling

- Runtime network-dependency audit: **IMPLEMENTED** (traced + actively tested, not grep-only).
- API docs CDN dependency: **IMPLEMENTED** (fixed; disabled by default in production).
- SoftHSM2 bootstrap boundary: **DOCUMENTED + TESTED** (confirmed it cannot reach the running app; the download itself is not removed — that is packaging work, tracked in deployment-architecture.md).
- Host/trusted-origin configuration: **IMPLEMENTED** (opt-in `TrustedHostMiddleware` wiring + visible non-loopback warning).
- Offline dependency wheelhouse / signed update bundles: **FUTURE PHASE**, per deployment-architecture.md.

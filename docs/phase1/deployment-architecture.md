# SAT-SA Phase 1 — Deployment and offline architecture

Audit basis: [technology-baseline.md](technology-baseline.md) execution evidence, verified contents of `configs/settings.*.yaml`, `qsmlops/core/settings.py`, `.devtools/softhsm2/README.md` and `scripts/bootstrap_softhsm2.ps1`. This document proposes the SAT-OFF-01/02 target ([requirements traceability](requirements-traceability.md)); GAP-16 in [gap-analysis.md](gap-analysis.md) is the tracked gap it closes.

## Current state (verified, not proposed)

| Item | Evidence | Implication |
|---|---|---|
| Dependency installation | `pyproject.toml`/`requirements.txt` list unlocked, lower-bounded packages (`kyber-py>=1.2.0`, `dilithium-py>=1.4.0`, `fastapi>=0.110`, `python-pkcs11>=0.9.0`, ...); no lockfile | `pip install` resolves online today; a fresh air-gapped machine cannot install as-is |
| PKCS#11 provider bootstrap | `scripts/bootstrap_softhsm2.ps1` downloads `SoftHSM2-2.5.0-portable.zip` from `github.com/disig/SoftHSM2-for-Windows` at runtime | HSM-backed signing path requires internet access to set up today; this is a development/certification bootstrap, not a deployment artifact |
| API network binding | `configs/settings.development.yaml`: `api.host: 127.0.0.1`; `configs/settings.production.yaml`: `api.host: "0.0.0.0"` | Production config binds all interfaces by default — not itself an air-gap violation (air-gap is about the network's *reachability*, not the bind address), but it is not a deployment safety control either, and should not be read as one |
| Container/CI tooling | No Dockerfile, no `.github/`, no `Makefile`, no `.yml`/`.yaml` outside `configs/` found anywhere in the tree | No existing packaging artifact to build from; deployment packaging is entirely new work |
| Local runtime | SQLite (stdlib), JSONL evidence ledger, content-addressed artifact store, pure-Python/`cryptography`-backed PQC | These are genuinely offline-capable once installed — no network calls are made during normal operation (verified: no HTTP client import outside the FastAPI/Uvicorn server stack itself) |
| Default data home | `~/.qsmlops` (from `PlatformConfig`, confirmed in technology-baseline.md) | Single-user local install pattern already exists; SAT-SA should follow the same convention (`~/.satsa` or a configurable equivalent) rather than inventing a new one |

## Target offline bill of materials

1. **Pinned dependency wheelhouse.** Freeze exact versions (the technology-baseline.md "observed environment" column is the starting pin list) into a local wheel cache; installation on the air-gapped target reads only from that cache. A version-locked `requirements.lock` (or equivalent) is new work — none exists today.
2. **Vendored PQC/crypto stack.** `dilithium-py`, `kyber-py`, `cryptography` are pure-Python/pip-installable and vendor cleanly into the wheelhouse; no native build step is required for the software PQC path.
3. **Local PKCS#11 provider (optional, hardware-backed deployments only).** The SoftHSM2 archive (or a real HSM vendor's provider) must be placed manually from removable media — the existing bootstrap script's GitHub download is a *developer convenience for certification testing*, not a deployment mechanism, and must not be reused as one. Document the manual placement procedure explicitly; do not silently make the download optional-but-attempted.
4. **Local reporting.** No external rendering service; report generation (SIH-RP-02) runs entirely with locally available libraries.
5. **Local frontend.** The UI ([ui-ux-architecture.md](ui-ux-architecture.md)) is served by the same local process — no CDN-hosted JS/CSS. This is a specific, checkable constraint: any UI build step that pulls fonts/icons/charting libraries from a CDN at runtime (common in quick prototypes) violates the air-gap requirement and must be caught in review before it reaches a demo or deployment build.
6. **Local configuration.** Extend the existing `configs/settings.*.yaml` layering (`built-in defaults < file < QSMLOPS_* env vars < explicit overrides`, confirmed in `configs/settings.development.yaml` comment) with SAT-SA-specific sections rather than inventing a second configuration system.
7. **Local update mechanism.** No update mechanism exists today (confirmed: no CI, no release pipeline). Target: signed update bundles applied via removable media, verified against the same key-policy/checkpoint model used for evidence ([quantum-trust-audit.md](quantum-trust-audit.md) migration section) — an update must not be trusted merely because a file was copied onto the machine.

## AI/ML offline requirements (per Part L)

Any optional local model (similarity/anomaly detection, [analytics architecture](analytics-architecture.md) statistical-governance section) must specify, before it is enabled by default:

1. **Architecture** — tabular isolation forest or sparse TF-IDF + cosine nearest-exemplar, CPU-only; no transformer/LLM component anywhere in the analytics path (explicit brief constraint, Part U).
2. **Hardware requirements** — must run within the resource envelope of a standard NTRO-provisioned workstation; no GPU requirement, since none is assumed available in an air-gapped SOC-assessment context.
3. **Offline training** — trained only on approved local development snapshots, split by entity/time to avoid leakage, with the training manifest (data digest, feature list, code version) signed and stored the same way a model passport is today (`passport/passport.py` pattern, ADAPTed).
4. **Offline inference** — no network call of any kind at inference time; this is inherited for free if the model is a plain scikit-learn-style estimator loaded from a local artifact.
5. **Model update mechanism** — same signed-bundle mechanism as item 7 above; a model update is a specific instance of the general update mechanism, not a separate pathway.
6. **Explainability** — a model may only ever *support* a finding whose rationale is stated in terms of measured features and exemplars (per analytics-architecture.md); it must not become the sole justification for a finding, consistent with SIH-EX-05.
7. **Auditability** — model version and feature-set version are mandatory fields on any finding a model contributed to, so a later reviewer can determine exactly what produced it.

No external AI API is required anywhere in this architecture, and none should be introduced later without the same offline/local-model justification applied above (Part U explicitly lists "unnecessary LLM integration" as something to avoid).

## Deployment readiness checklist (Part R of the brief)

| Question | Target answer |
|---|---|
| Installation | Operator copies the signed offline bundle (wheelhouse + application + config templates) from approved removable media; a local install script verifies bundle signature before extracting |
| Configuration | Layered YAML + env vars, same pattern as today; SAT-SA adds an `assessment:` and `crypto:` (extended) section, validated at startup with fail-closed on unknown/missing required keys |
| Data ingestion | Local operator uploads a CSE submission through the ingestion transaction ([data architecture](data-architecture.md)); no network listener accepts external submissions directly |
| Processing | An assessment run executes on-demand (CLI or API-triggered by an authenticated operator), never on a schedule that implies continuous monitoring (SIH-OOS-02) |
| Analysis | Bounded workers run against the frozen snapshot; run manifest records code/config/model/baseline digests for reproducibility |
| Review | Examiner UI, authenticated, append-only decisions |
| Evidence | Content-addressed store + signed ledger; checkpoint export to offline custody (GAP-11) |
| Trust | Local PQC verification, no external CA/OCSP-style network dependency |
| Reporting | Signed local report generation |
| Updates | Signed removable-media bundle, verified before install |
| Recovery | Ledger-driven reconciliation on restart; a crashed run leaves an explicit failed/partial state, never a silent gap (per [agent architecture](agent-architecture.md) execution-and-failures section) |
| Audit | An independent verifier (no signing secrets required) reconstructs the full chain and manifest graph from the ledger and checkpoints alone |

## What "deployment-ready" explicitly does not mean here

It does not mean containerized/Kubernetes-orchestrated — no evidence in this repository suggests NCIIPC's air-gapped environment supports or requires that, and introducing it without that evidence would be scope creep (Part U). It does not mean cloud-hosted anything. It does not mean a CI/CD pipeline running in this phase's deliverable — CI is a development-process concern, not a property of the shipped offline product, though GAP-15 (engineering quality) still calls for a test suite that *could* run in CI once one exists.

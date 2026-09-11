# Claims table

Every major claim made in `README.md` (and the claims added by this
session's own work), mapped to its evidence and an honest status.
Status values:

- **verified** — proven by an executable test or a live run performed
  in a session, reproducible by anyone with this repo.
- **synthetic evidence** — proven against synthetic/generated data,
  not real-world data; real, reproducible, but not evidence about
  real-world accuracy.
- **simulated** — an explicitly-labeled simulation (see the term used
  in the artifact itself), not a claim about real analyst behavior.
- **pending** — requires an external dependency this repository cannot
  supply (real expert review, real institutional deployment, real
  hardware).
- **unverified (this session)** — written/built but not actually
  exercised in the environment this session ran in, disclosed rather
  than silently assumed working.

| Claim | Evidence | Status |
|---|---|---|
| Offline / zero network calls in the full pipeline | `tests/test_phase18_satsa_offline_hardening.py` — blocks DNS/TCP, runs ingest→analyze→risk→prioritize→UI under the block | verified |
| Post-quantum trusted: every run/finding signed with ML-DSA-65 | `tests/test_phase44_satsa_trust_stress.py` (11), `tests/test_phase66_satsa_tamper_matrix.py` (6) — real sign/verify, real tamper detection | verified |
| Hash-chained evidence ledger, tamper-evident (not tamper-proof) | `docs/TRUST_MODEL.md` tampering matrix; explicitly NOT claimed immutable | verified (claim itself is bounded correctly) |
| Human supervisor is terminal authority; recommendation ≠ decision | `tests/test_phase66_satsa_tamper_matrix.py::test_review_binding_...`, `tests/test_phase64_...` — recommendation and recorded decision proven as separate, non-overwriting objects | verified |
| Review-decision audit trail bound to authenticated identity | `tests/test_phase63_satsa_auth_rbac.py` (13) — unauthenticated/wrong-role/forged/revoked all rejected; valid credential's real identity_id is what gets recorded | verified |
| 32 agents (9 MLOps + 23 SAT-SA), each with a real implementation | `docs/AGENT_INVENTORY.md` — per-agent implementation file + representative tests; 23 orchestrated by SAT-SA's own engine (3 of the 23 invoked from inside `compute_entity_risk` / a UI route / a CLI command rather than the default worker set — noted, not hidden), 9 run under the separate qsmlops pipeline (precisely distinguished, not conflated) | verified |
| Execution-gap detection (6 detectors) | `tests/test_phase5_satsa_execution_gaps.py`, and caught a real cross-cutting ingestion bug (`tests/test_phase65_satsa_partial_ref_resolution.py`) that was producing false execution-gap findings before this session's fix | verified |
| Negative-space detection (6 rules) | `tests/test_phase6_satsa_negative_space.py`; also the subject of a real post-P17 bug fix (asset_id CSV alias) documented in `docs/roadmap-status.md` P6 | verified |
| Peer benchmarking is robust / cohort-gated | `tests/test_phase8_satsa_peer_benchmark.py`, `test_phase30_...`, `test_phase47_...` — `min_peers=3` gate exists and is tested | verified (statistical rigor beyond the existing gate — larger cohorts, sensitivity analysis — is **pending**, see `docs/roadmap-status.md` P22) |
| 7-dimension decomposable risk model | `tests/test_phase9_satsa_entity_risk.py` | verified as *implemented*; risk weights are explicitly disclosed as "a starting hypothesis pending expert calibration," not scientifically validated — **pending** real calibration |
| Detection efficacy (does SAT-SA actually find real supervisory weaknesses) | Synthetic ground truth (`satsa/analysis/synth.py`, `satsa/analysis/compval.py`), fresh-database E2E proof (`tests/test_phase64_satsa_fresh_database_e2e.py`) | synthetic evidence — no real CSE/examiner data exists to validate against |
| An operator can submit their own real CSE data — via CLI **and** browser — not just the committed demo | `sat-sa ingest` (CLI) and `POST /ingest` (browser upload, added this session) both call the identical `SatsaService.submit()` + `run_analysis()` path. Proven live: a hand-crafted submission using non-canonical column names (`AlertID`/`priority`/`host` instead of `native_id`/`severity`/`asset_id`) was ingested with 0 rejections and produced real, evidence-cited findings (`execution_gap.fast_closure`, `execution_gap.critical_without_escalation`, `case_similarity.template_cluster`, etc.) neither hand-coded nor present in any test fixture. `tests/test_phase69_satsa_ui_ingest_upload.py` (6) locks this in: unauthenticated/wrong-role upload rejected, missing-required-file rejected, a real upload produces a real computed finding, duplicate entity names are reused not duplicated | verified |
| Expert validation infrastructure | `satsa/analysis/validate.py` (YES/NO/UNLABELED semantics, phase P22), `docs/demo/expert-labels.sample.json` explicitly tagged `reviewer: "sample-template"` | infrastructure verified; **real expert labels are pending** — never fabricated |
| Workload / prioritization reduction | `evaluation/workload/`, `tests/test_phase67_satsa_workload_reduction.py` — measured (not assumed) 3.75x lift at top-10% on a synthetic population | simulated — explicitly labeled `"simulated_workload_reduction"`, not a claim about real analyst time saved |
| HSM / hardware-backed ML-DSA | `qsmlops/crypto/hsm.py` fails closed when unsupported; `docs/HSM_A11_CERTIFICATION.md` | verified as *honestly absent* — no PKCS#11 token supports ML-DSA industry-wide; the software fallback is what actually signs everything |
| Scalability (10/25/50 CSE measured) | `scripts/benchmark_scaling.py` | verified up to 50 CSE; 100/1000 CSE targets are **pending** (`docs/roadmap-status.md` P24) |
| CI passes | `.github/workflows/ci.yml` | **unverified (this session)** — written, consistent with every command run locally, but never executed on GitHub Actions (git-safety rule: no push performed) |
| Docker deployment works | `Dockerfile` | **unverified (this session)** — no Docker daemon available in the environment this session ran in; disclosed in the file's own header comment |
| Backup/restore preserves the full trust chain | `tests/test_phase68_satsa_doctor_and_backup_restore.py` | verified |
| `sat-sa doctor` diagnoses a real install | Live run in this session (16 passed / 1 warned / 0 failed against a fresh install) plus `tests/test_phase68_...` (5) | verified |
| Cross-detector corroboration (Correlation & Signal Fusion) | `satsa/analysis/correlation.py`, `tests/test_phase74_satsa_correlation_fusion.py` (12) — deterministic, structural clustering by shared `scoped_subjects`, wired additively into `EntityRiskProfile.correlation_clusters` | verified |
| Governed detector-threshold calibration (propose → test → approve → deploy) | `satsa/analysis/calibration.py`, `qsmlops/security/permissions/model.py`'s `calibration.approve` permission, `tests/test_phase75_satsa_calibration.py` (21), `tests/test_phase76_satsa_calibration_cli.py` (6) — a proposal is scored against real labels, never its own output; approve/deploy require the supervisor-only permission | verified; scoped to one worker (`fast-closure`) today — extending to more workers is a registry addition, not a redesign (`docs/roadmap-status.md` P26 addendum) |
| CSRF protection on cookie-authenticated state-changing routes | `satsa/security.py`'s `verify_csrf()` (double-submit cookie, header-auth exempt), `tests/test_phase63_satsa_auth_rbac.py`'s 3 CSRF tests | verified for `/findings/{id}/review` and `/ingest`; **not** applied to `/login` (self-limiting login CSRF, deferred) or `/logout`/`/demo/load` (not meaningful attacks) — disclosed, not hidden |
| Login rate limiting | `satsa/security.py`'s `LoginRateLimiter`, `tests/test_phase79_satsa_security_hardening.py` (7) | verified; in-memory/single-process, does not survive a restart or scale across workers — disclosed |
| TLS / encryption at rest / session (credential) expiry | none | **pending** — air-gapped LAN deployment relies on filesystem/OS protection and credential revocation instead; not fabricated as done (`docs/roadmap-status.md` P26 addendum, checklist item 7) |
| Review-decision deletion / out-of-band insertion detection | `satsa/analysis/review.py`'s `verify_ledger_integrity()` (independent hash-chained ledger, reusing `qsmlops.evidence.ledger.EvidenceLedger`), `tests/test_phase80_satsa_review_ledger_integrity.py` (8) — deletion, forged insertion, and ledger-file tampering each proven detected | verified; closes the exact gap `docs/TRUST_MODEL.md` previously disclosed as "⚠️ not detected"; still bounded by filesystem-level trust (no external anchor) |
| Test coverage / type-check baseline | `pyproject.toml`'s `[tool.coverage.*]`/`[tool.mypy]`, `CHANGELOG.md`, live-measured this session: `coverage report` → 92.5% across `satsa/`+`evaluation/` (5,372 stmts, 405 missed); `mypy` → 0 errors in every P26-addendum module individually | verified (measured, reproducible commands in `docs/roadmap-status.md` P26 addendum); **not** wired as a CI gate; 30 pre-existing mypy errors in older, untouched modules disclosed, not fixed |
| Public-benchmark (BOTS/CIC-IDS2017) validation **framework** — see `docs/PUBLIC_BENCHMARKS.md` for the full, authoritative claims boundary | `public_benchmarks/`, 98 tests across `tests/test_phase81_...` through `test_phase85_...` — all 12 workflow scenarios proven end to end through the real `satsa.ingest` → `RunService` → detector pipeline (each scenario's declared family is present, not proven exhaustively exclusive of every other detector signal), with `expects_signal_families` measured via live `satsa_findings` queries | verified for what the layer actually claims (schema-compatible adapter framework + ingestion mechanics + the 12 controlled scenarios, all against hand-built/`TEST-SOURCE` rows); **NOT** validated against actual downloaded BOTS/CIC-IDS2017 files (registration-gated, unobtainable in this environment — adapters are schema-conformant, tested against hand-built sample rows only); **NOT** a claim about real SOC investigation/escalation behavior (workflow layer is synthetic by construction) — never cite this row as "validated on BOTS/CIC-IDS data," "validated against real CSE operations," or "NCIIPC-approved" |
| Independent practitioner review instrument | `public_benchmarks/review_packet.py`, `tests/test_phase85_public_benchmarks_review_packet.py` (16) — reviewer-role allowlist rejects any NCIIPC-affiliated role at construction time; aggregate scoring never produces a ground-truth/NCIIPC-validated key | infrastructure verified; **no real reviewer responses collected yet** — this is the instrument, not the data; see `docs/PUBLIC_BENCHMARKS.md`'s "what you must NOT claim" |
| Baselines vs. SAT-SA (z-score/MAD/IQR/random/severity-only) | `evaluation/baselines/` (`statistical.py`, `compare.py`), `tests/test_phase77_evaluation_baselines.py` (20) — every baseline checked against a stated ground truth, a real `FastClosureWorker` run compared head-to-head on the same data | verified on a small, deliberately-clean hand-constructed scenario; **pending** against the larger independently-generated cohorts / real per-record labels (same real-data dependency as checklist item 1) |
| Ablation studies (disable one worker, remeasure) | `evaluation/ablation/runner.py`, `tests/test_phase78_evaluation_ablation.py` (5), `sat-sa ablate` CLI command | verified — removing `fast-closure` measurably loses its own finding family; removing an unrelated worker does not |
| Statistical rigor (larger cohorts, confidence intervals, sensitivity analysis) | partial (workload experiment uses 500-trial empirical baselines) | **pending** for peer benchmarking / risk weights / baselines-at-scale specifically |

## How to keep this table honest

Every row above cites either a test file (run it: `python -m pytest
<file> -q`) or an explicit "unverified"/"pending" label. When a new
claim is added anywhere in this repository's documentation, it must
either get a row here with real evidence, or not be made. This is the
table `docs/FINAL-READINESS-AUDIT.md` (when written) should cite
rather than re-deriving its own claims from scratch.

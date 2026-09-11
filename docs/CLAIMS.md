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
| 26 agents (9 MLOps + 17 SAT-SA), each with a real implementation | `docs/AGENT_INVENTORY.md` — per-agent implementation file + representative tests; 17 orchestrated by SAT-SA's own engine, 9 run under the separate qsmlops pipeline (precisely distinguished, not conflated) | verified |
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
| Baselines vs. SAT-SA (z-score/MAD/IQR/random/severity-only) | none yet | **pending** — not started (`docs/roadmap-status.md` P22 limitations) |
| Ablation studies (disable one worker, remeasure) | none yet | **pending** — not started |
| Statistical rigor (larger cohorts, confidence intervals, sensitivity analysis) | partial (workload experiment uses 500-trial empirical baselines) | **pending** for peer benchmarking / risk weights specifically |

## How to keep this table honest

Every row above cites either a test file (run it: `python -m pytest
<file> -q`) or an explicit "unverified"/"pending" label. When a new
claim is added anywhere in this repository's documentation, it must
either get a row here with real evidence, or not be made. This is the
table `docs/FINAL-READINESS-AUDIT.md` (when written) should cite
rather than re-deriving its own claims from scratch.

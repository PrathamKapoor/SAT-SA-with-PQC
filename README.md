# SAT-SA — Supervisory Analytics Tool for SOC Assessment

**SIH 26157 · NCIIPC.** A periodic, offline, evidence-driven supervisory
analytics system supporting human examiners in identifying entities,
controls, processes, investigations, and alert samples requiring
supervisory attention.

SAT-SA turns structured CSE (Constituent Security Entity) submissions
into evidence-backed supervisory intelligence: who needs attention, why,
on what evidence, with what confidence — terminating in a human
supervisor's recorded decision over cryptographically verified evidence
(**TRUST-SAT**).

## What this is — and is not

SAT-SA is:

- a **periodic, offline, evidence-driven supervisory analytics** system;
- a **human-supervised** instrument: agents observe and recommend, a
  human examiner decides (terminal authority, append-only audit);
- **post-quantum trusted**: every run and finding signed with ML-DSA-65,
  hash-chained evidence ledger, deterministic content digests;
- **air-gapped by design**: zero network calls in the full pipeline.

SAT-SA is **not** a SIEM, a SOC replacement, a real-time monitor, a
national monitoring system, a continuous telemetry collector, or an
autonomous supervisory authority.

## Architecture

```
                         SAT-SA
                           │
               ┌───────────┴───────────┐
               │                       │
        SECURITY DATA             ML / ANALYTICS
               │                       │
               └───────────┬───────────┘
                           │
                  SUPERVISORY AGENTS
                           │
             ┌─────────────┼─────────────┐
             │             │             │
          DETECT       CORRELATE    ASSESS/REASON
             │             │             │
             └─────────────┼─────────────┘
                           │
                  THREAT / RISK FINDING
                           │
                     RECOMMENDATION
                           │
                   HUMAN SUPERVISOR
                           │
                     ACTION / DECISION
                           │
                        TRUST-SAT
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   PQC SIGNATURES      PROVENANCE       HASH-CHAIN
                                             │
                                      EVIDENCE INTEGRITY
```

The diagram is the product: Security Data + ML/Analytics feed the
supervisory agent fabric → Detect/Correlate/Assess → risk findings →
bounded recommendations → **human decision** → recorded action, all over
the TRUST-SAT integrity foundation.

## The 32-agent model

32 agents is a consequence of responsibility separation, not a target
(grown from 26 in phase P25, then 31 to 32 in phase P26 — see
`docs/AGENT_INVENTORY.md` for the full roster and why each addition
was real, not decorative):

- **9 retained MLOps agents** (`qsmlops/`): Data, Performance, Security,
  QuantumSecurity, RedTeam, Governance, IncidentResponse, Optimization,
  TrainingOptimization. Unchanged; they govern the ML platform itself.
- **23 SAT-SA supervisory agents** (`satsa/`): EntityAssetResolution,
  Ingestion, Normalization, ExecutionGap, NegativeSpace,
  WorkflowReconstruction, Anomaly, PeerBenchmark, CoverageGap,
  Drift, CrossEntityInsights, CaseSimilarity, EvidenceCompleteness,
  CorrelationSignalFusion, EntityRiskScoring (formerly "Fusion"),
  Prioritization, Recommendation, ReviewWorkflow, TrustProvenance,
  EvidenceAssembly, MetaAudit, ReportGeneration, Validation.

Every agent implements the common contract `observe(context) →
Observation` with severity, confidence, scope, subjects, evidence_refs,
rationale, statistics, threshold, limitations, recommended_action,
analysis_period, and provenance. Agents **must not** make irreversible
supervisory decisions independently.

One generalized supervisor engine (`satsa/supervisor/engine.py`) runs
**Observe → Reason → Act → Verify → Learn** with two pluggable,
lexically disjoint decision vocabularies:

- SAT-SA: `SATSA_SURFACE / SATSA_INSPECT / SATSA_REQUEST_EVIDENCE /
  SATSA_ESCALATE_FOR_REVIEW / SATSA_DEFER / SATSA_ACCEPT /
  SATSA_CLOSE_REVIEW` — all require human authority;
- MLOps: `ACCEPT / DEPLOY / RETRAIN / QUARANTINE / ROTATE_KEYS /
  BLOCK_DEPLOYMENT / ESCALATE / ROLLBACK` — policy-driven proposals.

## Security data layer

Six evidence categories per CSE submission: **alerts, cases,
investigation steps, escalations, dispositions, assets** — plus source
records, provenance, submissions, assessments, multiple CSEs, multiple
periods. Offline SQLite store; the hash-chained ledger remains source of
truth. Ingestion supports **CSV, JSON, JSONL, and SQLite**
(`satsa/ingest/db_adapter.py`); equivalent evidence from different
sources normalizes to equivalent canonical records.

## ML / analytics layer

14 analytical workers in the default run: 6 execution-gap detectors
(fast closure, ack-without-investigation, critical-without-escalation,
repeated investigation, recurring-without-remediation, metric gaming),
negative space (6 rules), robust anomaly statistics, peer benchmarking
(trimmed statistics), coverage gap, drift, cross-entity insights, case
similarity, evidence completeness. Plus: 7-dimension decomposable risk
(`execution_gap, peer_deviation, detection_gap, negative_space, anomaly,
investigation_quality, escalation_discipline`), lexicographic
prioritization, and the bounded recommendation engine
(`INSPECT_INVESTIGATION, CHECK_ESCALATION_PATH,
VERIFY_MONITORING_COVERAGE, COMPARE_WITH_PEERS,
REQUEST_MISSING_EVIDENCE, REVIEW_METRIC_DEFINITION,
INSPECT_ROOT_CAUSE_REMEDIATION, REVIEW`).

Statistical analytics are valid. Deterministic rules are valid. Robust
statistics are valid. ML only where it adds actual value.

## Human supervision

Review queue → evidence inspection → accept / reject / defer / request
evidence / escalate / mark false positive → rationale → recorded
decision → audit trail. Every decision binds the finding's content digest
at decision time; corrections append, history is never rewritten.

## TRUST-SAT

- **PQC signatures**: ML-DSA-65 over canonical SHA3-256 digests;
- **Provenance**: source → record → observation → finding → risk →
  recommendation → decision;
- **Hash-chain ledger**: append-only, tamper-evident evidence ledger;
- **Evidence integrity**: verification re-derives digests from live rows;
  any tamper (including of the stored digest column itself) is detected.

Trust claim is **detection of tampering at verification time, not
tamper-proofness**.

## Installation (offline / air-gapped)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python -m compileall satsa qsmlops
python -m pytest tests/ -q
```

Python ≥ 3.10. No network calls anywhere in the pipeline (verified by
`tests/test_phase18_satsa_offline_hardening.py`, which blocks DNS/TCP
and runs the demo + every UI page). No CDN, remote fonts, telemetry.

## Usage

### Demo (the judge path)

```bash
python demo.py            # full SAT-SA story: 5 CSEs → findings → risk → trust → review
sat-sa demo               # same via CLI (requires --db)
```

Then serve the UI —

```bash
python scripts/serve_ui.py --db ./satsa.db --trust-key-dir ./keys --port 8000
```

— open `http://127.0.0.1:8000/` (loads the demo dataset automatically
on first run), and follow: Overview → entity → risk → evidence →
Detect/Correlate/Assess → recommendation → TRUST-SAT → review →
decision → architecture/agents. To submit your own CSE data instead
of the demo, sign in at `/login` (see "Authentication" below) and use
`/ingest`.

### CLI (same service layer as the UI — no duplicated logic)

```bash
sat-sa --db ./satsa.db --trust-key-dir ./keys ingest CSE-X ./sub \
  --period-start 1735689600 --period-end 1738281600
sat-sa --db ./satsa.db --trust-key-dir ./keys analyze <entity> <assessment>
sat-sa --db ./satsa.db risk <entity>
sat-sa --db ./satsa.db prioritize [--run-id <run>]
sat-sa --db ./satsa.db findings <run> [--state signal]
sat-sa --db ./satsa.db --trust-key-dir ./keys verify <run>
sat-sa --db ./satsa.db review --finding-id <f> --action confirm --reason "..."
sat-sa --db ./satsa.db report <entity> [--out report.html]
sat-sa --db ./satsa.db validate
sat-sa agents
sat-sa --db ./satsa.db decision <run> --vocabulary satsa
```

### Python API

```python
from satsa.service import SatsaService
svc = SatsaService(engine)                 # DatabaseService or bare engine
e = svc.register_entity("CSE-X", sector="defence", environment_class="on-prem")
a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
svc.submit(a.id, "./submission-dir")       # or {category: path}
run = svc.run_analysis(e.id, a.id, trust_key_dir="./keys")
risk = svc.compute_risk(e.id)
report = svc.verify_run(run.run_id, "./keys")
svc.record_review(finding_id=..., principal_identity_id="examiner-1",
                  action="confirm", reason="...",
                  finding_content_digest=..., previous_revision_id=None)
```

## Validation

Per-layer + composition, never one accuracy number:

- **synthetic ground truth**: 10 deterministic scenarios (healthy,
  execution-gap, negative-space, anomaly, peer-deviation, mixed,
  borderline, noisy, missing-evidence, conflicting-evidence) generated
  outside the analytical execution, compared after the fact
  (`satsa/analysis/validate.py`, `satsa/analysis/synth.py`);
- **expert labels**: layer, is_signal, category, severity, expected
  action, rationale, confidence, reviewer, timestamp;
- **offline guarantee**, **scaling benchmark** (5/10/25/50 CSE),
  **peer robustness**, **trust stress** (every mutation rejected or
  classified).
- **public-dataset benchmark framework** (`public_benchmarks/`): 12
  controlled scenarios, each proven to trigger its declared detector
  family through the real pipeline (known/permitted cross-detector
  side effects are documented, not suppressed — see
  `docs/PUBLIC_BENCHMARKS.md`). The adapters are schema-compatible
  with CIC-IDS2017/Splunk BOTS but have **not** been run against the
  actual downloaded dataset files in this environment — every
  scenario here runs on hand-built, explicitly-labeled sample rows.
  Read `docs/PUBLIC_BENCHMARKS.md` before citing this — it draws the
  exact line between "validated ingestion/detection mechanics on
  schema-compatible sample data" and "validated against real SOC
  investigation behavior" (the latter remains explicitly not
  claimed).

## UI

FastAPI + Jinja2 + vanilla JS, all local: Overview (command center) ·
Entities · Entity detail · Findings · Finding detail (WHAT/WHY/EVIDENCE/
CONFIDENCE/LIMITATIONS/NEXT/TRUST) · Review queue · Benchmarks ·
Analytics pipeline · Security data · Decisions · TRUST-SAT · Agents (26) ·
Architecture · System · Reports · Ingest (submit your own CSE data).

## Authentication

Recording a review decision, or submitting new CSE data via `/ingest`,
requires a real, server-verified identity — not a caller-supplied
header. This reuses the existing qsmlops identity/credential system
(salted API-key credentials); see `docs/deployment.md`'s "Authentication
bootstrap" section for how to create the first identity on a fresh
install. Roles: `satsa_viewer` (read-only), `satsa_analyst` (run
analytics/ingest), `satsa_supervisor` (also records review decisions),
`satsa_auditor` (read + platform audit log), `satsa_admin` (full
control). Sign in at `/login` (browser) or pass
`--credential`/`SATSA_CREDENTIAL` (CLI). The 16 read-only dashboard
pages remain open without a credential; every state-changing action is
gated.

## Project structure

```
satsa/                 # SAT-SA supervisory analytics (the product)
  ingest/              # CSV/JSON/JSONL/SQLite readers, normalization, service
  store/               # SQLite repositories, canonical dataset
  domain/              # entities, evidence, runs, workflow records
  contracts/           # worker + orchestration contracts
  analysis/            # 16 workers, run service, risk, prioritize,
                       # recommend, review, trust, drift, insights,
                       # similarity, synth, validate, benchmark, report
  supervisor/          # 32-agent registry + Observe→Reason→Act→Verify→Learn
  security.py          # identity/RBAC wiring for the UI + CLI
  ui/                  # FastAPI app, templates (incl. /login, /ingest), demo loader
  cli.py               # sat-sa entry point (incl. `doctor`)
qsmlops/               # reusable MLOps trust infrastructure (retained):
                       # crypto (ML-DSA/ML-KEM/SHA3), evidence ledger,
                       # passports, registry, identity/RBAC, 9 agents,
                       # supervisor, pipeline
evaluation/            # workload-reduction/prioritization-lift experiment,
                       # baselines (z-score/MAD/IQR/random/severity-only),
                       # ablation study -- all independent of the detectors
                       # they measure
public_benchmarks/     # CIC-IDS2017/Splunk BOTS schema-compatible
                       # adapter framework + 12 workflow scenarios
                       # -- see docs/PUBLIC_BENCHMARKS.md for
                       # exactly what this does and does not validate
tests/                 # per-layer, e2e, offline, trust stress, auth/RBAC,
                       # tamper matrix, fresh-database reality tests,
                       # public-benchmark scenario proofs -- see `pytest
                       # tests/ -q` for the current count (see Testing)
scripts/               # demo dataset builder, scaling benchmark, SoftHSM2
                       # bootstrap, serve_ui.py (real UI launcher)
docs/                  # phase docs, roadmap status, deployment, demo runbook,
                       # claims table, requirements traceability, trust model
demo.py                # SAT-SA end-to-end demonstration
.github/workflows/     # CI (dependency install, full suite, offline/trust/
                       # auth suites, CLI smoke, demo — see Limitations)
Dockerfile             # single-process container (see Limitations)
```

`qsmlops/` provides reusable infrastructure (crypto, evidence, logging,
errors, the 9 retained agents). SAT-SA never repurposes its MLOps domain
logic.

## Limitations (honesty discipline)

- **Risk weights are a starting hypothesis** pending domain-expert
  calibration — never a claimed-final model;
- **PQC is pure-Python** (dilithium-py / kyber-py), not side-channel
  hardened; liboqs migration is the stated path;
- **No PKCS#11 token supports ML-DSA/ML-KEM** — industry-wide hardware
  limitation; the platform fails closed and self-certifies;
- **SQLite single-writer boundary** — documented, not hidden;
- **Expert validation scaffolded** — framework + synthetic ground truth
  complete; production expert-label volume pending;
- **Cross-entity insights + drift** are wired into the supervisor
  context (`previous_period`, `cross_entity_aggregate`); they still
  honestly abstain (`insufficient_data`) for an entity's first
  assessment (no prior period to diff against) or the first entity
  processed in a shared assessment (no peers yet) — never fabricate.
- **Composition validation is now pipeline-bound**
  (`satsa/analysis/compval.py`): synthetic scenarios run through the
  real ingestion + analytics pipeline rather than comparing ground
  truth to itself; 5 of the 10 scenarios genuinely cannot be
  reproduced in a single-entity fixture (peer cohort / multi-period
  baseline / threshold-edge scenarios) and are reported as
  `not_executed` with a specific reason.
- **CI and the Dockerfile are unverified** — both are written and
  consistent with the commands verified working locally, but neither
  has actually executed on GitHub Actions or a real Docker daemon.
  The native (non-container) install/run path in `docs/deployment.md`
  *has* been verified live. See `docs/FINAL-READINESS-AUDIT.md`.

## Testing

```bash
python -m pytest tests/ -q        # full suite (1000+, ~5-10 min)
python -m compileall satsa qsmlops scripts tests
```

Never weaken tests; never delete tests to make the suite pass.

## License

MIT License. Author: Pratham Kapoor.

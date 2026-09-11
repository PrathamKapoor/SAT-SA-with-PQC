# SAT-SA Roadmap Status — P0 → P17

Machine-readable phase tracker. A phase is COMPLETE only when its
acceptance criteria are demonstrated by real code / tests / artifacts.

Status values: COMPLETE · PARTIAL · IN PROGRESS · BLOCKED · NOT STARTED

## P0 — Foundation hardening + trust remediation

- status: COMPLETE
- implementation: `satsa/analysis/canonical.py` (single canonical
  reconstruction, `live_run_seed`), `satsa/analysis/trust.py`
  (stored-column tamper check in `verify_subject`),
  `satsa/analysis/run.py` (post-completion seed refresh in `set_status`
  path), `satsa/analysis/repository.py` (seed = digest of everything
  except the digest column)
- tests: `tests/test_phase44_satsa_trust_stress.py` (11/11, incl.
  `test_tampered_run_digest_fails_verification`),
  `tests/test_phase11_satsa_trust.py`,
  `tests/test_phase27_satsa_trust_determinism.py`,
  `tests/test_phase27_satsa_trust_stress.py`
- acceptance: tampering the stored `content_digest` column fails
  verification with a "mismatch" reason; valid runs verify
- evidence: full suite green; demo produces 0 digest mismatches on
  fresh data
- demo value: TRUST-SAT verification is real, not decorative
- limitations: trust = tamper *detection*, not tamper-proofness
  (SQLite file holder can replace data + receipts)

## P1 — Agent architecture (9 retained + 17 new = 26)

- status: COMPLETE
- implementation: `satsa/supervisor/agents.py` (canonical 26-agent
  registry), `satsa/supervisor/context.py` (`SupervisorContext`),
  `satsa/supervisor/engine.py` (generalized engine)
- tests: `tests/test_phase53_supervisor_engine.py` (13)
- acceptance: 9 MLOps + 17 SAT-SA = 26, unique ids, required fields,
  disjoint vocabularies
- evidence: registry importable; UI agent explorer renders all 26
- demo value: agent explorer + architecture pages
- limitations: MLOps agents retained as specs (their runtime lives in
  `qsmlops/`); cross-scope aggregates (drift / cross-entity) abstain
  until wired

## P2 — Generalized supervisor (Observe → Reason → Act → Verify → Learn)

- status: COMPLETE
- implementation: `satsa/supervisor/engine.py` — five explicit stages
  + `SupervisorEngine.run()` + append-only lineage log; dict- and
  object-finding compatible
- tests: `tests/test_phase53_supervisor_engine.py`
- acceptance: SAT-SA signal → non-SURFACE action, requires_human=True;
  empty scope → SATSA_SURFACE; unknown vocabulary rejected; lineage has
  all five stages
- evidence: `python demo.py` step 10 emits SATSA_INSPECT on live findings
- demo value: supervisor decision shown in demo + CLI `decision`
- limitations: no automatic retraining from decisions (by design)

## P3 — Ingestion + normalization + DB adapter

- status: COMPLETE
- implementation: `satsa/ingest/` (CSV/JSON/JSONL readers, normalization,
  service) + `satsa/ingest/db_adapter.py` (read-only SQLite source:
  `read_sqlite_table`, `read_sqlite_categories`)
- tests: `tests/test_phase3_satsa_ingestion.py`,
  `tests/test_phase55_satsa_db_adapter_validation.py`
- acceptance: equivalent evidence from CSV/JSON/SQLite normalizes to
  equivalent canonical records; source DB never written to
- evidence: DB adapter tests read a synthetic source DB
- demo value: `sat-sa ingest` accepts any supported format
- limitations: no live collectors (periodic submissions only, by design)

## P4 — Analysis run engine (14 workers)

- status: COMPLETE
- implementation: `satsa/analysis/run.py` (`RunService`, 14-worker
  default set, single-transaction persistence, PQC attestation)
- tests: `tests/test_phase4_satsa_analysis_run.py`,
  `tests/test_phase57_satsa_new_workers.py`
- acceptance: 14 observations per run; every signal finding cites
  evidence + confidence; crashed workers isolated
- evidence: full suite green with 14-worker default
- demo value: demo runs 5 CSEs × 14 workers
- limitations: none known

## P5 — Execution gaps (6 detectors)

- status: COMPLETE
- implementation: `satsa/analysis/workers/` fast_closure,
  ack_without_investigation, critical_without_escalation,
  repeated_investigation_pattern, recurring_without_remediation,
  metric_gaming
- tests: `tests/test_phase5_satsa_execution_gaps.py`
- acceptance: per-detector thresholds, signal + no_signal paths
- demo value: CSE-EXEC fires fast_closure + critical_without_escalation
- limitations: thresholds are operational defaults, not calibrated SLAs

## P6 — Negative space (6 rules, hardest problem)

- status: COMPLETE
- implementation: `satsa/analysis/workers/negative_space.py` with
  data-completeness separation (missing-file ≠ missing-evidence);
  low-activity signal now cites alert refs + asset ids (fixed
  silent-drop bug)
- tests: `tests/test_phase6_satsa_negative_space.py`
- acceptance: absence-from-submission distinguished from
  absence-in-reality; every signal cites evidence
- demo value: CSE-NEG fires missing monitoring/investigation/disposition
- limitations: expectation graph is submission-declared, not
  externally authoritative
- fixed post-P17: `satsa/ingest/spec.py` `ALERT_FIELDS` did not
  recognize a CSV column literally named `asset_id` (only `assets`,
  `asset`, `host`, `hostname`) as an alias for the `asset_ids` list
  field, so every alert's asset reference was silently dropped
  during normalization — the `missing_monitoring` rule then treated
  *every* critical/high asset as unmonitored regardless of real
  alert activity. Found by `tests/test_phase61_satsa_composition_validation.py`'s
  healthy-control gate (a genuinely clean submission must emit zero
  negative-space signals) running the full CSV ingestion path — the
  existing unit tests for this rule build normalized domain objects
  directly and never exercised the CSV alias resolution. Fixed by
  adding `asset_id` to the alias tuple; 882 passed, 0 failed after
  the fix (full regression, no regressions introduced).

## P7 — Anomaly (robust statistics)

- status: COMPLETE
- implementation: `satsa/analysis/workers/anomaly.py`
  (median/MAD/percentile, 8 metrics)
- tests: `tests/test_phase7_satsa_anomaly.py`
- acceptance: no p-value-as-confidence; effect + sample size exposed
- demo value: CSE-ANOM fires investigation-duration outlier
- limitations: single-entity distributions; no cross-period baselines yet

## P8 — Peer benchmark (robust, cohort-gated)

- status: COMPLETE
- implementation: `satsa/analysis/workers/peer_benchmark.py`
  (trimmed statistics, cohort manifest, min_peers gate)
- tests: `tests/test_phase8_satsa_peer_benchmark.py`,
  `tests/test_phase30_satsa_peer_robust.py`,
  `tests/test_phase47_satsa_peer_robustness.py`
- acceptance: incomparable cohorts suppressed; tiny cohorts abstain
- demo value: CSE-PEER deviates on escalation/alert rates
- limitations: cohort = sector + environment only; maturity/scale
  matching is future work

## P9 — Risk (7 dimensions, decomposable)

- status: COMPLETE
- implementation: `satsa/analysis/risk.py` (7 dimensions, bounded
  weights, confidence vector, versioned)
- tests: `tests/test_phase9_satsa_entity_risk.py`
- acceptance: decomposable, explainable, evidence-backed,
  confidence-aware, versioned; no double counting
- demo value: entity detail shows WHY per dimension
- limitations: **weights are a starting hypothesis pending expert
  calibration** — disclosed, never claimed final

## P10 — Prioritization (lexicographic, explainable)

- status: COMPLETE
- implementation: `satsa/analysis/prioritize.py` (entity + finding
  ranking with rationale)
- tests: `tests/test_phase10_satsa_prioritize.py`,
  `tests/test_phase10_adaptive_supervisor.py`
- acceptance: ranking reconstructible from stored policy + facts
- demo value: review queue + overview roster
- limitations: no fabricated "minutes saved"; sample counts only

## P11 — Trust / provenance (TRUST-SAT)

- status: COMPLETE
- implementation: `satsa/analysis/trust.py`, `trust_storage.py`,
  keystore providers, HSM/PKCS#11 fail-closed abstraction
- tests: trust suites (P11/P27/P31/P44), HSM suites
- acceptance: sign → verify; tamper → mismatch; receipts idempotent
- evidence: 0 mismatches on fresh demo data; stress suite green
- demo value: TRUST-SAT page + demo step 7 (8/8 VERIFIED)
- limitations: pure-Python PQC (not side-channel hardened); no
  hardware ML-DSA exists industry-wide (fails closed, self-certified)

## P12 — Human review workflow

- status: COMPLETE
- implementation: `satsa/analysis/review.py` (confirm/dismiss/escalate/
  annotate/request_review; digest-bound; append-only with
  previous_revision_id)
- tests: `tests/test_phase12_satsa_review.py`,
  `tests/test_phase35_satsa_review_analytics.py`
- acceptance: decision binds finding digest; history chronological
- demo value: finding detail records decisions; demo steps 8–9
- limitations: principal identity is header-derived in UI (real
  deployment wires proper auth)

## P13 — E2E vertical slice + UI + CLI + reports

- status: COMPLETE
- implementation: demo dataset (5 CSEs) + ground truth,
  `satsa/ui/` (16 pages), `satsa/cli.py` (`sat-sa`, 13 subcommands),
  `satsa/analysis/report.py`, SAT-SA-first `demo.py`
- tests: `tests/test_phase13_satsa_e2e_vertical_slice.py`,
  `tests/test_phase14_satsa_ui.py`,
  `tests/test_phase54_satsa_cli.py`,
  `tests/test_phase56_satsa_premium_pages.py`
- acceptance: judge path works: overview → entity → risk → evidence →
  recommendation → TRUST-SAT → review → decision → architecture
- evidence: `python demo.py` completes 10/10 steps
- limitations: UI auth is a stub header (see P12)

## P14 — Offline guarantee + deployment

- status: COMPLETE
- implementation: stdlib-only parsing, local assets (no CDN/fonts),
  `tests/test_phase18_satsa_offline_hardening.py` (blocks DNS/TCP),
  `docs/deployment.md`
- tests: offline suite green
- acceptance: 0 network calls in full pipeline
- evidence: offline test runs demo + every UI page under socket block
- limitations: SQLite single-writer boundary (documented)

## P15 — Synthetic ground truth + validation framework

- status: COMPLETE (framework + real composition binding + real
  layer-validation wiring) / PARTIAL (production expert-label
  volume — see limitations)
- implementation: `satsa/analysis/synth.py`,
  `satsa/analysis/validate.py` (ExpertLabel, 10-scenario ground truth,
  per-layer evaluation, `composition_validation` with corrected
  empty-expected-signals semantics — `signals_ok` means *no*
  unexpected signal fired, not the vacuous `expected <= emitted`),
  `satsa/analysis/compval.py` (`run_composition_validation`: builds
  a real synthetic CSE submission per executable scenario, ingests
  it through `SatsaService`, runs the actual default-worker
  pipeline, and compares *emitted* findings/action to the ground
  truth — closing the prior scaffold gap where composition
  validation compared ground truth to itself), `sat-sa validate`
  (wires all three: `--expert-labels <path>` loads real
  `ExpertLabel` records into `layers`, `composition_catalog` for
  the legacy scaffold, `composition_bound` for the real
  pipeline-bound report), `docs/demo/expert-labels.sample.json` +
  `docs/demo/EXPERT_LABELS.md` (illustrative label template,
  explicitly tagged `reviewer: sample-template`, not real examiner
  review — proves the wiring, not production accuracy)
- tests: `tests/test_phase28_satsa_synth.py`,
  `tests/test_phase55_satsa_db_adapter_validation.py`,
  `tests/test_phase61_satsa_composition_validation.py` (9: shape,
  every ground-truth case accounted for, all 5 executable scenarios
  actually produce a real `run_id`, all 5 non-executable scenarios
  report a specific honest reason, healthy control produces zero
  signals, fast-closure/missing-investigation fire the expected
  rule family, CLI `validate` wiring),
  `tests/test_phase62_satsa_expert_validation.py` (5: ExpertLabel
  JSON round-trip + signature distinguishes positive/negative
  labels, `evaluate_layer` precision/recall is real set arithmetic
  not a vacuous 1.0/1.0, `run_validation` against *live* demo
  findings with a deliberately held-out false-negative, CLI
  `--expert-labels` wiring against live findings, and a
  backward-compatibility test proving omitting the flag still
  reports `layers: []` exactly as before)
- acceptance: ground truth hidden from execution; per-layer metrics,
  never one accuracy number; composition validation runs a real
  pipeline per scenario instead of comparing expectations to
  themselves; layer validation computes real TP/FP/FN against
  findings an actual run emitted, when real labels are supplied
- evidence: `run_composition_validation()` returns `executed` (5,
  each with a real `run_id`) + `not_executed` (5, each with a
  specific reason — peer cohort / multi-period baseline / threshold-
  edge non-determinism a single-entity fixture cannot provide) +
  `summary`; `sat-sa validate --expert-labels
  docs/demo/expert-labels.sample.json` against the committed demo
  dataset returns 7 non-empty per-layer rows with real TP/FP/support
  counts derived from live findings — not fabricated round numbers
  (the exact precision figures shown at the time this phase shipped
  were superseded by P22's YES/NO/UNLABELED fix a few phases later;
  see the P22 entry for the corrected numbers and why they changed);
  870 passed, 17 skipped, 0 failed full regression (887 total, +5 vs.
  pre-fix baseline of 882 — the 5 new tests in
  `tests/test_phase62_satsa_expert_validation.py`)
- demo value: `sat-sa validate` prints the legacy catalog, the real
  bound composition report, and (when `--expert-labels` is given)
  real per-layer precision/recall
- limitations: production expert-label volume is still pending —
  real labels from human NCIIPC/SOC examiners reviewing actual
  findings, which an engineering session cannot honestly manufacture
  (the shipped sample file is explicitly tagged as a template, not
  examiner output); the 5 non-executable ground-truth scenarios
  (anomaly-rate, peer-deviation, borderline, noisy,
  conflicting-evidence) genuinely cannot be reproduced
  deterministically in a single-entity fixture and are reported as
  such rather than faked; `evaluate_layer` treated an explicit
  negative label (`is_signal=False`) the same as "no label at all"
  for false-positive counting when this phase shipped — **fixed in
  P22**, see that entry for the corrected YES/NO/UNLABELED semantics

## P16 — Cross-period + cross-entity + similarity + recommendations

- status: COMPLETE
- implementation: `satsa/analysis/drift.py`
  (`DRIFT_METRICS`, `compute_drift`, `compute_kpis`,
  `collect_evidence_refs`), `satsa/analysis/insights.py`
  (`cross_entity_aggregate`, plus the per-query insight builders),
  `satsa/analysis/case_similarity.py`,
  `satsa/analysis/workers/{drift,cross_entity_insights,
  case_similarity}.py`, `satsa/analysis/recommend.py`; supervisor
  wiring in `satsa/analysis/run.py` (`RunService._build_run_extras`,
  additive `RunContext.extras` channel in
  `satsa/contracts/worker.py`)
- tests: `tests/test_phase36_satsa_case_similarity.py`,
  `tests/test_phase37_satsa_drift.py`,
  `tests/test_phase38_satsa_insights.py`,
  `tests/test_phase57_satsa_new_workers.py`,
  `tests/test_phase60_cross_period_cross_entity_wiring.py` (14 new:
  `compute_kpis` derivation / no-fabrication, DriftWorker signal +
  abstain paths, CrossEntityInsightsWorker signal + abstain paths,
  RunService `previous_period` + `cross_entity_aggregate` extras
  wiring, aggregate query helper)
- acceptance: the supervisor now wires `previous_period` (latest
  prior assessment's KPI dict) and `cross_entity_aggregate`
  (other-entities' signal findings in the same assessment) into
  `RunContext.extras`; DriftWorker emits `signal` findings with
  evidence + confidence + rationale when prior metrics diverge and
  abstains (`no_signal` / `insufficient_data`) otherwise;
  CrossEntityInsightsWorker emits `signal` findings citing the
  other entity ids as provenance when a rule exceeds prevalence and
  abstains otherwise; workers never fabricate a baseline
- evidence: 856 passed, 17 skipped, 0 failed full regression;
  drift + cross-entity signal findings persist with valid
  `evidence_refs` + confidence
- demo value: multi-period data now produces real drift findings;
  cross-entity insights fire on the second-and-later entities in
  a shared assessment
- limitations: abstraction, not inference — drift fires only when
  a prior assessment for the same entity exists, and cross-entity
  abstains for the first entity processed in an assessment (it has
  no peers yet); both abstain honestly rather than fabricate.

## P17 — Productization (README, demo, reports, audit)

- status: COMPLETE
- implementation: SAT-SA-first `README.md`, SAT-SA-first `demo.py`,
  `docs/roadmap-status.md` (this file), `docs/deployment.md`,
  premium UI (architecture/agents/trust/decisions/security-data/
  pipeline), professional reports
- tests: premium page suite, CLI suite, full regression
- acceptance: judge understands the system in 30 seconds; every
  image-architecture layer maps to running code (see Final Audit)
- evidence: this document + demo transcript + test counts
- limitations: as listed per-phase above

## P18 — Authentication + RBAC (wire the existing identity system)

- status: COMPLETE
- implementation: `satsa/security.py` (new — `resolve_principal`,
  `require(permission)`, cookie/header credential extraction),
  additive permissions + `satsa_viewer/analyst/supervisor/auditor/
  admin` roles in `qsmlops/security/permissions/model.py`, wired into
  `satsa/ui/__init__.py` (`POST /findings/{id}/review` now requires
  `decision.record`; `GET/POST /login`, `POST /logout`) and
  `satsa/cli.py` (`sat-sa review --credential <token>` /
  `SATSA_CREDENTIAL` env var, replacing the old free-text
  `--principal` argument). No new crypto or session format: this
  reuses the already-existing, already-tested qsmlops
  `IdentityService` (salted API-key credentials,
  `tests/test_phase2_identity_auth.py`, 14 tests) that the SAT-SA UI
  had simply never been wired to — before this phase,
  `satsa/ui/__init__.py` read
  `request.headers.get("x-satsa-principal", "ui-anonymous")` and
  recorded whatever string a caller sent, verbatim, into the
  permanent human-decision audit trail.
- tests: `tests/test_phase63_satsa_auth_rbac.py` (13): unauthenticated
  request rejected (401), the old spoofed header now has zero effect,
  wrong-role credential rejected (403), forged/tampered token
  rejected (401), revoked credential rejected (401), malformed token
  rejected (401), valid supervisor credential succeeds via
  `Authorization` header (API/CLI path) and via the `/login` cookie
  (browser path), the recorded `principal_identity_id` is proven to
  be the real identity id (not free text), recommendation and human
  decision proven to never overwrite each other (separate persisted
  objects — SAT-SA sends `recommend()`, the reviewer independently
  records `dismiss`, both remain independently queryable), and two
  CLI tests (credential required; a real `satsa_supervisor`
  credential succeeds and is recorded faithfully). Also fixed a
  regression this phase caused: `tests/test_phase14_satsa_ui.py`'s
  `test_finding_detail_and_review_post` posted to the review endpoint
  with no credential and expected success — updated to create a real
  `satsa_supervisor` identity and authenticate, asserting the
  recorded principal matches it.
- acceptance: every sensitive UI/CLI action requires a real,
  server-verified identity holding the specific permission for that
  action; a forged/spoofed/tampered/revoked/malformed credential
  fails closed with the correct status code; the audit trail's
  `principal_identity_id` can never again be attacker-chosen text
- evidence: full regression run after the change (see this session's
  final count); the fix is an *integration*, not new cryptography —
  the credential format, hashing, and verification path are identical
  to the already-proven qsmlops identity system
- demo value: `/login` + an authenticated review decision is a real,
  attackable step in the judge story, not a hand-waved "auth would go
  here"
- limitations: this phase gates the one concrete state-changing
  endpoint the backlog named (`POST /findings/{id}/review`, both UI
  and CLI) plus login/logout. The 16 read-only dashboard pages remain
  unauthenticated-readable by design for this pass (a blanket
  app-wide login wall was explicitly deferred rather than risked
  against the working, offline-hardening-tested dashboard without a
  dedicated pass); `sat-sa decision`'s `--principal` (the automated
  supervisor-engine lineage tag, which never writes to
  `satsa_review_decisions`) was left unchanged, a smaller and
  lower-severity gap than the human-review audit trail this phase
  closes. Session cookie is the raw bearer credential itself
  (HttpOnly, not readable by page JS) rather than a separate opaque
  session-id scheme — deliberately minimal, consistent with
  `qsmlops.security.identity.auth`'s own documented scope ("a local
  API-key credential store... not enterprise SSO... not a
  session/cookie system" — the cookie here is just a browser-friendly
  transport for the same bearer token, not a new auth primitive).
  Credential distribution/rotation is a manual operator step (no
  self-service UI yet); acceptable for a single-installation,
  air-gapped deployment, a genuine limitation for a larger
  multi-examiner rollout.

## P19 — Prove the core loop is real, not a demo engine

- status: COMPLETE
- implementation: `tests/test_phase64_satsa_fresh_database_e2e.py` (a
  brand-new SQLite DB — no committed demo, no `demo.py` in the call
  path anywhere — driving the full chain with data from
  `satsa.analysis.synth.generate()`, a generator completely
  independent of the 5 committed demo CSEs and of any detector
  threshold: create entity → open assessment → ingest → analyze →
  risk → prioritize → recommend → authenticated human review (P18) →
  record decision → verify TRUST-SAT → render report), plus a real
  fix in `satsa/ingest/normalize.py` this test surfaced (see below).
- tests: `tests/test_phase64_satsa_fresh_database_e2e.py` (4):
  the full pipeline from nothing, asserted at every stage (real
  evidence-cited findings, real prioritization, a bounded
  recommendation, a human decision bound to a real identity, live
  TRUST-SAT verification — not a cached/stale object — and report
  HTML that contains the actual finding's rule id, not templated
  filler); reproducibility across 3 independent fresh-DB runs from
  the same seed (identical finding families, identical risk score);
  3 independently-generated datasets with different seeds/volumes/
  severity mixes (not mutations of the demo fixture) each producing
  real, distinct findings; a negative-control CSE tuned to be
  operationally clean, measuring — not asserting zero — the real
  false-positive count. Plus
  `tests/test_phase65_satsa_partial_ref_resolution.py` (4): the
  ingestion bug this uncovered, isolated and regression-tested
  directly.
- acceptance: every stage consumes the previous stage's real
  persisted output; no fixture/mock/hardcoded result substitutes for
  computation anywhere in the traced call path; a negative control is
  measured honestly rather than asserted clean
- evidence: **the negative-control test found a real bug**, not a
  false alarm to tune away. A CSE generated with
  `escalation_rate=1.0` / `disposition_rate=1.0` (every critical/high
  alert escalated, every alert dispositioned — deterministically, not
  "probably") still tripped `execution_gap.critical_without_escalation`
  / `negative_space.missing_escalation` /
  `negative_space.missing_disposition`. Root cause: 3 of 12 generated
  escalations and 8 of 30 generated dispositions were silently
  rejected during normalization — each one's `alert_id` resolved to a
  real accepted alert, but its *optional* `case_id` happened to
  reference one of 2 cases independently rejected during case
  validation, and `satsa/ingest/normalize.py`'s two call sites
  rejected the *entire* record (`if not fail`) whenever *either*
  optional reference failed to resolve — contradicting the module's
  own documented contract ("warnings capture... unresolvable
  *optional* references") and `_resolve_either`'s own docstring ("the
  record's own invariant is at least one resolvable ref"). Fixed by
  making `_resolve_either` reject only when *neither* reference
  resolves, downgrading a lone unresolvable reference to a warning
  and keeping the record with that field as `None`. After the fix:
  escalations 9/12 → 12/12 accepted, dispositions 22/30 → 30/30
  accepted, and the three false findings disappeared; full regression
  green afterward (see this session's final count). This is the same
  class of bug as the P6 post-P17 `asset_id` alias fix — evidence
  silently dropped during ingestion, only surfaced by exercising the
  real CSV path against non-fixture data, never caught by unit tests
  that build normalized domain objects directly.
- demo value: proves the judge-facing claim "every stage consumes the
  previous stage's real output" against data the system has never
  seen, not just the rehearsed 5-CSE demo
- limitations: the residual 5 finding families the fully-clean
  negative control still produces
  (`execution_gap.ack_without_investigation`,
  `execution_gap.recurring_without_remediation`, 3
  `anomaly.*` outliers) are documented in the test itself as
  legitimate structural properties of the fixture (investigation
  steps are generated per-case on a fixed schedule, not per-alert, so
  a case with multiple alerts can have individual alerts whose
  ack/close timing falls outside the case's own recorded steps; the
  anomaly findings are volume-driven robust-statistics outliers,
  which is what that detector is supposed to surface) rather than
  bugs — but this is an assessment made in this session, not an
  independently expert-reviewed conclusion; P22's peer/anomaly
  hardening work should revisit it with real statistical rigor

## P20 — Tamper matrix + trust-stress correction

- status: COMPLETE
- implementation: `ReviewService.verify_binding()` (new,
  `satsa/analysis/review.py`) + `SatsaService.verify_review_binding()`
  (`satsa/service.py`) close a gap `review.py`'s own docstring had
  long claimed but nothing ever checked — every recorded decision on
  a finding is now actually compared against the finding's current
  live digest, and `RunService.verify_run()`
  (`satsa/analysis/run.py`) surfaces this automatically under a new
  `"reviews"` key for any finding with decision history, so a
  TRUST-SAT report includes it without a separate call.
  `docs/TRUST_MODEL.md` gained a SAT-SA/TRUST-SAT section: explicit
  roots of trust, what is and is not protected, and a literal
  tampering matrix (mutation → detected? → which test proves it),
  distinguishing what is proven from what is a documented residual
  limitation.
- tests: the pre-existing `tests/test_phase44_satsa_trust_stress.py`
  (11, already green — finding body/evidence/observation_id tamper,
  run-digest tamper, corrupted signature, deleted/missing receipt,
  re-verification stability) was audited first and found *not*
  broken — the "trust-stress test needs correction" backlog item
  predates this session's fixes and was stale. New:
  `tests/test_phase66_satsa_tamper_matrix.py` (6): the review-binding
  check verifies clean and fails after post-decision tampering, is
  included in `verify_run()`'s report, a fabricated/inserted finding
  that was never signed is never reportable as verified, and —
  directly answering the "live state, not cached object" requirement
  — analytics run with verification never invoked, then verify (ok),
  tamper (fails), restore the *exact* original value (verifies again),
  proving the check re-derives from the database as it stands at call
  time rather than a snapshot taken once.
- acceptance: every mutation the roadmap's tampering matrix names is
  either proven detected by an executable test or explicitly
  documented as a residual limitation — never silently assumed
- evidence: `docs/TRUST_MODEL.md`'s tampering matrix table; full
  regression green after the change (see this session's final count)
- demo value: the TRUST-SAT page's verification report now includes
  review-decision integrity, not just run/finding signatures — closer
  to "the entire audit trail is cryptographically verifiable," not
  just the analytical output
- limitations: two residual gaps are now explicit rather than
  implicit — (1) `satsa_review_decisions` has no hash-chain of its
  own, so a *deleted* or *reordered* decision row is not currently
  detected (only a *modified* finding after the fact is, via the
  digest-binding check); (2) whole-database replacement (an attacker
  swaps the `.db` file entirely, receipts included) is undetectable
  without an external trust root cross-check, which does not exist
  yet. Recommendations remain unsigned by design (computed on demand
  from an already-trusted finding, never persisted as an independent
  claim) — documented, not treated as a bug.

## P21 — Simulated manual-sampling workload experiment

- status: COMPLETE
- implementation: new `evaluation/` package (`evaluation/workload/`),
  deliberately separate from `satsa/` — `build_population()` labels
  each synthetic entity "pathological" or "clean" from the
  **generator configuration** (`PATHOLOGICAL_CONFIG` /
  `CLEAN_CONFIG` in `evaluation/workload/experiment.py`) before any
  SAT-SA computation ever runs, so the ground truth is structurally
  independent of what SAT-SA decides — the same independence
  discipline as P19/P15. `run_workload_experiment()` compares SAT-SA's
  real, already-computed `prioritize_entities()` ranking against a
  measured random-order baseline (500 independent shuffles, not an
  assumed analytic k/100 expectation) at top-10%/20%/50%, plus
  "review volume to find every genuinely pathological entity" under
  both orderings.
- tests: `tests/test_phase67_satsa_workload_reduction.py` (4):
  population labels are independent of SAT-SA by construction; SAT-SA
  prioritization beats the measured random baseline at every k on a
  real population; the zero-pathological edge case doesn't crash;
  and a regression guard proving two differently-seeded populations
  produce different results (catches a hardcoded/fabricated return
  value, since a real measurement can't be byte-identical across
  different inputs).
- acceptance: every number in the result comes from an actual
  `prioritize_entities()` call and actual measured shuffles — nothing
  is analytically assumed or hand-typed; every output is labeled
  `"simulated_workload_reduction"`, never "analyst time saved"
- evidence (one representative run, seed 2026, 30 entities / 8
  genuinely pathological / 500 random trials — reproducible via
  `evaluation.workload.run_workload_experiment`):

  | k | SAT-SA recall@k | measured random recall@k | lift |
  |---|---|---|---|
  | 10% | 0.375 | 0.100 | 3.75x |
  | 20% | 0.625 | 0.201 | 3.11x |
  | 50% | 0.875 | 0.502 | 1.74x |

  Review volume to find all 8 pathological entities: SAT-SA order 20
  of 30 entities; random-order mean 27.49 of 30. Full regression green
  after the change (see this session's final count).
- demo value: a genuinely strong, honestly-labeled SIH metric —
  "reviewing the top 10% of SAT-SA's queue finds 3.75x as many real
  problems as reviewing the top 10% in submission order" is concrete,
  reproducible, and correctly scoped as simulated
- limitations: the population is synthetic (two hand-designed
  operational profiles, not a spectrum); "pathological" is a binary
  label, not the graded severity a real supervisory population would
  have; no real examiner has validated that these synthetic
  pathological entities resemble what a real CSE assessment would
  flag — this measures prioritization lift on a controlled synthetic
  population, not real-world workload reduction. The random baseline
  is genuinely measured (not assumed), which is the one rigor
  improvement this phase insisted on over a simpler "trust the math"
  approach.

## P22 — Validation semantics: explicit YES / NO / UNLABELED (partial — see limitations)

- status: PARTIAL — the validation-semantics fix (this phase's most
  concretely-scoped, already-flagged item) is COMPLETE; peer-benchmark
  hardening, literature baselines, and ablation studies (the rest of
  the original P22 scope) are NOT started and are carried forward
  honestly rather than claimed done
- implementation: `satsa/analysis/validate.py` — `evaluate_layer()`
  and `LayerMetric` reworked around explicit YES (`is_signal=True`) /
  NO (`is_signal=False`) / UNLABELED (no label at all) semantics.
  Before this phase, an emitted family with *no* label was silently
  treated identically to one an expert *explicitly rejected*
  (`is_signal=False`) — both fell into the same "false positive"
  bucket, a bug this session's own P15 work had flagged but deferred.
  Now: a positively-labeled family contributes to
  true_positives/false_negatives; a negatively-labeled family
  contributes to false_positives/true_negatives; an emitted family
  with *no* label at all is excluded from the confusion matrix
  entirely and counted separately in `unlabeled_emitted`, so
  precision is never artificially deflated by findings nobody ever
  reviewed. Added `true_negatives`, `specificity`, `f1`,
  `balanced_accuracy`, `support`, `coverage` fields; `precision` /
  `recall` / etc. are `None` (not a fabricated `0.0`) when the
  underlying counts make them undefined. A family carrying *both* a
  positive and a negative label (reviewer disagreement) is handled
  explicitly — counted toward both sides, flagged in `notes` — rather
  than one silently overwriting the other.
- tests: `tests/test_phase62_satsa_expert_validation.py` gained 3 new
  tests (negative label on an emitted family is a real FP; a
  negative label on a *non*-emitted family is a true negative with
  computable specificity; fully-unlabeled/empty input yields `None`
  metrics, not fabricated zeros) and 2 existing tests were corrected
  to the fixed semantics (an unlabeled-but-emitted family no longer
  inflates false_positives). `tests/test_phase55_satsa_db_adapter_validation.py`'s
  `test_evaluate_layer_precision_recall` was also corrected: it had
  been asserting that a family labeled *both* positively and
  negatively resolved to a clean 1.0/1.0 (the negative label being a
  silent no-op) — that was the exact bug; it now correctly asserts
  the conflicting label counts toward both true_positives and
  false_positives (precision 0.5, not a fabricated 1.0).
- acceptance: no unlabeled emission can ever be scored as a false
  positive again; a confirmed-negative label is now a real signal
  instead of dead data; undefined metrics are `None`, never `0.0`
- evidence: regenerated `sat-sa validate --expert-labels
  docs/demo/expert-labels.sample.json` against the committed demo —
  every layer's precision is now exactly what it should be (1.0 for
  every layer with zero confirmed false positives, `coverage` values
  like 0.25–1.0 transparently showing how much of what was emitted
  was ever actually labeled, rather than the previous run's precision
  figures being artificially deflated by unlabeled emissions). Full
  regression run after the change (see this session's final count).
- demo value: `sat-sa validate`'s per-layer report is now honest in a
  way it wasn't before — a layer showing precision 1.0 with coverage
  0.33 correctly communicates "everything we checked was right, but
  we've only checked a third of what fired" instead of conflating
  "wrong" with "unreviewed"
- limitations: peer-benchmark hardening (sparse/heterogeneous/
  outlier-contaminated cohort tests beyond the existing `min_peers`
  gate), literature-named baselines (z-score/MAD/IQR/threshold/
  random/severity-only) compared against SAT-SA on the same
  independently-generated datasets, and ablation studies (disabling
  one analytical worker at a time and re-measuring detection
  coverage) are all still open — not started in this session. This
  entry is marked PARTIAL rather than COMPLETE specifically so that
  distinction survives into any summary that reads phase status
  without reading the details.

## P24 — CI, deployment artifacts, operator diagnostics (partial — see limitations)

- status: PARTIAL — CI workflow, `sat-sa doctor`, and a proven
  backup/restore procedure are COMPLETE; a Dockerfile exists but is
  explicitly unverified (no Docker daemon in this session's
  environment); large-scale (100/1000 CSE) performance measurement is
  NOT started
- implementation:
  - `.github/workflows/ci.yml` — installs dependencies, byte-compiles
    the tree, runs the full suite plus explicit named runs of the
    offline-hardening, trust-stress/tamper-matrix, and auth/RBAC
    suites, a CLI smoke test, and `demo.py`, on Python 3.11 and 3.13.
    **Not pushed and not executed on GitHub Actions this session**
    (git-safety rule: no push) — it is written to be consistent with
    every command verified locally in this session, but "CI passes"
    cannot be claimed as observed fact until it actually runs on
    GitHub's infrastructure.
  - `sat-sa doctor` (`satsa/cli.py`) — a real diagnostic, not an
    import-check: performs an actual ML-DSA sign+verify roundtrip
    through the configured provider, actually connects to and
    migrates the target database, actually probes write permissions
    on the db directory and trust-key directory by writing and
    deleting a real file, actually constructs a `TrustService` against
    the keystore, and reports HSM availability honestly (absence is a
    WARN, not a FAIL — matching the documented "no ML-DSA hardware
    token exists industry-wide" posture). Exits non-zero if anything
    fails.
  - `docs/backup-restore.md` — a procedure that is *exactly* what
    `tests/test_phase68_satsa_doctor_and_backup_restore.py` performs
    and asserts, not independently-drifting prose: copy the SQLite DB
    file + trust-key directory together (a backup of one without the
    other cannot verify), destroy the originals, restore, and confirm
    via `sat-sa doctor` + `sat-sa verify` that the trust chain survived
    — not just that files of the right name exist post-restore.
  - `Dockerfile` — single-process image (CLI + UI over a volume-mounted
    SQLite file), a `HEALTHCHECK` that calls `sat-sa doctor`, explicitly
    marked untested in its own header comment.
- tests: `tests/test_phase68_satsa_doctor_and_backup_restore.py` (5):
  doctor passes clean on a fresh valid install; doctor fails closed
  (non-zero exit, `[FAIL] database`) when pointed at an unusable DB
  path (a directory, not a file); doctor warns rather than fails with
  no `--trust-key-dir`; backup→destroy→restore preserves the full
  trust chain (re-verified against the *restored* files, not assumed);
  a stale-backup control proving the backup mechanism captures a real
  independent snapshot rather than a no-op (a post-backup tamper to
  the working copy does not leak into the restored backup).
- acceptance: an operator can run one command (`sat-sa doctor`) to
  learn whether a fresh install is healthy, with every reported PASS
  backed by an actual exercised operation; a documented backup/restore
  procedure has been mechanically proven, not just written down
- evidence: `sat-sa doctor` run live against a fresh install in this
  session (16 passed, 1 warned — no HSM configured, expected — 0
  failed); full regression green after the change (see this session's
  final count)
- demo value: closes the "clean-room reproduction" test (mega-prompt
  section 100) partially — an operator with only the CLI and this
  documentation can now diagnose and recover a deployment without
  reading source code, for the two operations (health check,
  backup/restore) this phase covered
- limitations: the Dockerfile is unverified — no `docker build` or
  `docker run` was performed in this session; treat it as a draft, not
  a proven deployment artifact, until someone with Docker access
  verifies it (this is disclosed exactly per this phase's own
  standard: "a deployment described but never reproduced does not
  count"). CI is written but has never actually executed — same
  disclosure. Large-scale (100/1000 CSE) performance measurement
  (extending the existing `scripts/benchmark_scaling.py`, which
  already covers 5/10/25/50) was not attempted this session. Upgrade/
  rollback: forward migration is automatic and idempotent
  (`MigrationRunner`); there is no automated downgrade path, disclosed
  in `docs/backup-restore.md` rather than papered over.

## P23 — Claims table, requirements traceability, agent inventory

- status: COMPLETE (documentation consolidation — no code changes)
- implementation: `docs/CLAIMS.md` (every major README/session claim
  mapped to evidence and a status of verified / synthetic evidence /
  simulated / pending / unverified-this-session — never silently
  assumed true), `docs/REQUIREMENTS_TRACEABILITY.md` (every SIH26157
  functional requirement, illustrative use case, and performance
  criterion traced to a component, source file, test, and demo step),
  `docs/AGENT_INVENTORY.md` (the precise 26-agent breakdown the
  backlog worried "could sound inflated" — confirmed via direct
  inspection that all 9 retained MLOps agents have real, substantial
  implementations in `qsmlops/agents/*.py` (~1,600 combined lines,
  none stubs), distinguishing "orchestrated by SAT-SA's own
  supervisor" (the 17) from "orchestrated by the separate qsmlops
  MLOps pipeline" (the 9) rather than conflating the two).
- acceptance: no claim in this project's documentation now lacks a
  traceable evidence source or an honest "pending"/"unverified" label;
  a reviewer can start from any SIH requirement and reach the exact
  test file that proves it, or the exact statement that it isn't
  proven yet
- evidence: the three documents themselves, cross-checked against
  actual file contents in this session (e.g. `qsmlops/agents/*.py`
  line counts were verified via `wc -l`, not assumed)
- demo value: directly answers the "requirement traceability" and
  "agent count integrity" asks (mega-prompt sections 97/123) with an
  artifact a judge or reviewer can independently check line by line
- limitations: this is a documentation consolidation of the previous
  six phases' work, not new analytical capability — its value is
  entirely in making existing evidence findable and honest, which is
  exactly what it was scoped to do

## P25-lite — Browser-facing CSE data upload

Not part of the original P18–P24 plan; added directly in response to
the user asking, after seeing the UI, whether it could actually
ingest real CSE data or was "just for show."

- status: COMPLETE
- implementation: `GET/POST /ingest` in `satsa/ui/__init__.py` +
  `satsa/ui/templates/ingest.html`. The POST handler contains no
  ingestion or analysis logic of its own — it parses the multipart
  form, writes each uploaded file to a temp path per category, and
  calls the identical `SatsaService.submit({category: path, ...})` +
  `run_analysis()` the CLI's `sat-sa ingest`/`sat-sa analyze` already
  use. Gated by the same `ANALYSIS_RUN` permission (`satsa_analyst`/
  `satsa_supervisor`/`satsa_admin`) introduced in P18 — reused, not a
  new permission invented for this one feature. `requirements.txt` /
  `pyproject.toml` gained an explicit `python-multipart` dependency
  (previously an undeclared transitive install FastAPI needs for
  multipart parsing).
- tests: `tests/test_phase69_satsa_ui_ingest_upload.py` (6):
  the form page loads; unauthenticated upload rejected (401);
  `satsa_viewer` role rejected (403, proving the permission check is
  real, not just "any login"); missing the required `alerts` file
  redirects with an error rather than crashing; a real upload with
  non-canonical CSV column names (`AlertID`/`priority`/`host` instead
  of the canonical `native_id`/`severity`/`asset_id`) produces a real,
  queryable, evidence-backed finding not present in any fixture;
  re-submitting under the same entity name reuses the entity rather
  than duplicating it.
- acceptance: a browser user with an analyst-or-higher credential can
  submit genuinely new CSE data (not the demo, not a synthetic
  generator) and get real computed findings back — proven live in
  this session with a hand-crafted submission using deliberately
  non-standard column names to rule out the pipeline being narrowly
  wired to one exact format
- evidence: live end-to-end proof performed in this session — CLI
  ingestion of a hand-built "ACME-BANK" submission (0/11 records
  rejected, 8 real findings, full risk decomposition with named
  contributing findings), then an independent HTTP multipart upload
  of the same data to a fresh entity ("ACME-BANK-WEB") through the
  actual running server, producing byte-for-byte the same finding
  families — proving the browser path and the CLI path are the same
  code, not two implementations that could silently drift; full
  regression green after the change (see this session's final count)
- demo value: directly answers "is this real or just a demo" — a
  judge can bring their own (synthetic-but-realistic) CSV export,
  upload it through the browser, and watch real, evidence-cited
  findings and a real risk decomposition come back, live
- limitations: no progress indicator for large uploads (synchronous
  request/response — analysis runs inline before the redirect, so a
  very large submission would block the request rather than showing
  a progress bar); no partial-upload resume; the 16 read-only pages
  remain unauthenticated by the same deliberate P18 scope decision,
  unaffected by this addition.

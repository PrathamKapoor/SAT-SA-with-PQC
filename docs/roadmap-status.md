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
  `docs/AGENT_INVENTORY.md` (at the time, the precise 26-agent
  breakdown the backlog worried "could sound inflated" — confirmed via
  direct inspection that all 9 retained MLOps agents have real,
  substantial implementations in `qsmlops/agents/*.py` (~1,600
  combined lines, none stubs), distinguishing "orchestrated by SAT-SA's
  own supervisor" (17 at the time) from "orchestrated by the separate
  qsmlops MLOps pipeline" (the 9) rather than conflating the two; the
  SAT-SA count later grew to 22 in P26 — see that section).
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

## P26 — Agent taxonomy expansion (26 → 31 agents)

Not part of the original P18–P25 plan. The user supplied a proposed
9-RETAIN + 17-NEW SAT-SA agent taxonomy (a different grouping than
this project's own registry) and asked for validation against the
actual running code, followed by an explicit instruction: keep the 9
RETAIN agents, keep the 6 existing SAT-SA agents not named in the
proposed table, and add whichever of the proposed agents did not yet
exist as a distinct, real component.

- status: COMPLETE
- implementation: five new components, each real and independently
  tested, none a stub `AgentSpec` standing in for unbuilt logic:
  - `satsa/analysis/workers/entity_asset_resolution.py` —
    `EntityAssetResolutionWorker`; reads
    `run_context.extras["previous_period_assets"]` (new extras key,
    populated by `RunService._build_run_extras()`) and emits
    `entity_asset_resolution.vanished_assets` when a prior-period
    asset is absent now; abstains (`insufficient_data`) when the
    extras key itself is absent, distinct from an explicit empty list.
  - `satsa/analysis/workers/workflow_reconstruction.py` —
    `WorkflowReconstructionWorker`; three checks:
    `workflow_reconstruction.escalation_after_closure`,
    `workflow_reconstruction.disposition_before_investigation`,
    `workflow_reconstruction.sequence_chronology_mismatch`.
  - `satsa/analysis/evidence_assembly.py` — `assemble_explanation()`,
    a pure function consolidating a finding's confidence/recommendation/
    evidence into one `ExplanationBundle`; wired into the UI's
    `/findings/{id}` route (`satsa/ui/__init__.py`), replacing inline
    duplicated logic that previously lived only in the template path.
  - `satsa/analysis/meta_audit.py` — `run_meta_audit(engine,
    trust_key_dir)`, a database-wide sweep reusing
    `TrustService.verify_subject()` and `ReviewService.verify_binding()`
    across every run/finding/review in the database (not just the
    single run the `/trust` page already showed); exposed as a new
    `sat-sa audit` CLI command (`satsa/cli.py`).
  - `satsa/analysis/report.py` — real code that predated this phase
    but had never been added to the `AgentSpec` registry; now
    registered as `satsa.report_generation` so the agent explorer and
    supervisor routing table represent it truthfully.
  Both new workers (`entity_asset_resolution`, `workflow_reconstruction`)
  were added to `RunService`'s default worker set, taking it from 14
  to 16 workers. The registry grew from 26 (9 + 17) to 31 (9 + 22).
- tests: `tests/test_phase70_satsa_workflow_reconstruction.py` (12),
  `tests/test_phase71_satsa_entity_asset_resolution.py` (7),
  `tests/test_phase72_satsa_meta_audit.py` (6),
  `tests/test_phase73_satsa_evidence_assembly.py` (9); every existing
  test asserting a fixed worker/agent count (`test_phase4`,
  `test_phase5`, `test_phase8`, `test_phase53`, `test_phase54`,
  `test_phase56`, `test_phase57`, plus doc references in
  `docs/deployment.md`/`README.md`/`ingest.html`) updated to the new
  counts rather than left inconsistent.
- two real, pre-existing bugs were found and fixed incidentally while
  building this phase (not the phase's primary goal, but left
  unfixed would have undermined it):
  - `RunService._build_run_extras()` had a latent `NameError`: the
    new `previous_period_assets` code referenced `prior_dataset`
    after a try/except where it was only ever assigned inside the
    `try` — fixed by initializing `prior_dataset = None` before the
    `try:`.
  - `satsa/analysis/workers/negative_space.py`'s missing-escalation
    rule gated on `if unesc and completeness["escalations"]:`, which
    contradicted both the surrounding comment and the module's own
    top docstring — both say the finding should still fire (at
    attenuated confidence) when the escalations file wasn't submitted
    at all. Fixed to `if unesc:`; `tests/test_phase6_satsa_negative_space.py`
    updated to assert the finding fires with `effect == 0.3` /
    `confidence.evidence_completeness == 0.0` in that case, plus a new
    contrast test asserting `effect == 0.6` when the file is present.
- acceptance: every new capability is invoked from a real execution
  path (default worker set, a UI route, or a CLI command) — not an
  inert registry entry; full regression green after all count-cascade
  fixes (worker count 14→16, SAT-SA agent count 17→22, total 26→31)
  were applied across the affected test files and docs.
- evidence: `docs/AGENT_INVENTORY.md` (updated with the 5 new rows,
  the P25→P31 growth explanation, and the note that two of the five
  are invoked outside the main `RunService` pipeline rather than
  hidden as a discrepancy).
- demo value: closes the gap between a user-proposed agent taxonomy
  and the actual registry by building the missing pieces for real,
  rather than either rejecting the proposal or renaming existing
  agents to fake a match.
- limitations / explicitly deferred (per the user's own instruction,
  pending real NCIIPC/SOC data): real-world validation against expert
  labels, and the publishable research package. Also explicitly
  deferred within this same instruction and, at the time this section
  was first written, not yet started: the N9/N10 split (now done —
  see "P26 addendum" below) and the N17 calibration workflow extension
  (still not started).

### P26 addendum — N9/N10 Correlation & Signal Fusion split

- status: COMPLETE
- implementation: `satsa/analysis/correlation.py` — `correlate_findings()`
  clusters a run's signal findings by shared `scoped_subjects`,
  flagging a cluster as `corroborated` only when two or more distinct
  rule *families* (not the same detector firing twice) reference the
  same subject. Wired additively into
  `satsa/analysis/risk.compute_entity_risk()`: a new
  `EntityRiskProfile.correlation_clusters` field is populated before
  the per-dimension aggregation loop runs, and does not alter
  `DIMENSION_WEIGHTS` or the existing score formula (no existing
  `test_phase9_satsa_entity_risk.py` assertion changed). Registered as
  `satsa.correlation_fusion`, inserted immediately before the renamed
  `satsa.fusion` (`name` changed from "Fusion Agent" to "Entity Risk
  Scoring Agent"; `agent_id` intentionally unchanged so no existing
  reference to `satsa.fusion` breaks).
- tests: `tests/test_phase74_satsa_correlation_fusion.py` (12) — the
  pure clustering function (subject with one referencing finding is
  not a cluster; two findings from different families corroborate;
  two findings from the same family sharing a subject do not; a
  worker listing the same subject twice in its own `scoped_subjects`
  is deduplicated rather than inflating a cluster) plus integration
  tests proving `EntityRiskProfile.correlation_clusters` is populated
  from a real run and only ever references findings in `state ==
  'signal'`.
- acceptance: distinct from `compute_entity_risk()`'s dimension
  scoring both in what question it answers (cross-detector
  corroboration vs. weighted total risk) and in when it runs (a
  pre-scoring clustering pass, not a scoring step); additive, so no
  previously-asserted risk-profile score value changed.
- evidence: this is a deterministic, structural clustering over
  already-stored identifiers (shared `scoped_subjects`), not a
  statistical inference — its correctness is directly checkable
  against the stored finding rows, so it does not carry the same
  "needs real-world validation" caveat a threshold-based detector
  would.
- demo value: gives a supervisor a direct answer to "did more than one
  independent detector actually agree about this same incident, or
  did one loud dimension just look big" — currently invisible in the
  dimension-only view.
- limitations: purely structural correlation (shared subject id, not
  semantic similarity) — two findings about the same underlying
  incident that don't share an exact `scoped_subjects` id (e.g. an
  alert id on one side and its parent case id on the other) will not
  cluster; extending the subject-matching to case/alert parent-child
  relationships was not attempted this phase.

### P26 addendum — N17 calibration workflow (propose → test → approve → deploy)

- status: COMPLETE (scoped — see limitations)
- implementation: `satsa/analysis/calibration.py` —
  `propose_calibration()` / `run_calibration_test()` /
  `decide_calibration_proposal()` / `deploy_calibration_proposal()`
  as four explicit, ordered functions (each raises `ValueError` if
  called out of order — a proposal can only be tested from
  `'proposed'`, decided from `'tested'`, deployed from `'approved'`),
  plus `CalibrationLedger`, an append-only JSONL store mirroring
  `satsa_review_decisions`'s never-overwrite audit pattern.
  `run_calibration_test()` never grades a proposal against its own
  output: it runs both the currently-deployed worker instance and the
  candidate worker instance over the *same* dataset and scores both
  against the *same* expert-labeled ground truth via the existing
  `satsa.analysis.validate.evaluate_layer()` — reused, not
  reimplemented. A new permission, `calibration.approve`
  (`qsmlops/security/permissions/model.py`), gates the decide/deploy
  steps and is granted only to `satsa_supervisor`/`satsa_admin` — the
  same terminal-authority restriction `decision.record` already
  carries; `satsa_analyst` can propose and test but not approve or
  deploy. Wired into a real execution path:
  `sat-sa calibrate propose|test|approve|reject|deploy|history` (CLI
  subcommand, `satsa/cli.py`), reusing the exact
  `--credential`/`SATSA_CREDENTIAL` authentication path
  `sat-sa review` already uses. The existing `satsa.validation`
  `AgentSpec` was extended (not duplicated into a new agent id) to
  reference this module, since this is explicitly an extension of the
  Validation Agent per the user's own instruction.
- tests: `tests/test_phase75_satsa_calibration.py` (21) — the pure
  workflow functions, ordering enforcement, append-only ledger
  behaviour, and a realistic scenario (a 200s alert closure the
  default fast-closure threshold flags but an expert has labeled a
  false positive; a tightened candidate threshold correctly stops
  flagging it, a measurable, real precision improvement, not a
  fabricated one) proven end to end; `tests/test_phase76_satsa_calibration_cli.py`
  (6) — the same workflow through the actual CLI against a real
  ingested entity/assessment, plus the negative paths (no credential,
  viewer role, deploy-before-approve, unknown worker) failing closed.
- acceptance: nothing about a worker's production thresholds changes
  without passing through all four gated steps; testing a proposal is
  scored against real labels, not the candidate's own output; approval
  and deployment are cryptographically-authenticated, permission-gated
  actions, not free-text fields.
- evidence: `tests/test_phase75_satsa_calibration.py`,
  `tests/test_phase76_satsa_calibration_cli.py`; permission addition
  visible in `qsmlops/security/permissions/model.py`'s
  `CALIBRATION_APPROVE` constant and the `satsa_supervisor` role
  definition.
- demo value: shows a judge the full governance loop a real deployment
  needs for tuning detectors against a SOC's own operating reality —
  propose a change, prove it against labeled data, get explicit
  supervisor sign-off, deploy under a version label — rather than an
  operator silently editing a constant in source code.
- limitations (scoped deliberately, not hidden): (1) `_calibratable_workers()`
  registers only `fast-closure` today — extending to more workers is a
  one-line registry addition per worker, not a redesign, but was not
  done for every worker in this pass; (2) a deployed calibration is
  *not* automatically picked up by future `RunService.run()` calls —
  `CalibrationLedger.latest_deployed()` returns the thresholds dict for
  a caller to pass explicitly into `RunService.run(...)`'s existing
  override parameters; auto-applying it on every subsequent run without
  an explicit call site was judged too large a scope decision to make
  unilaterally (it would mean a run's detection behaviour could change
  based on state outside the run's own explicit inputs) and was
  intentionally left as a documented, deliberate boundary rather than
  attempted and left half-wired.

### P26 addendum — checklist item 2: baselines + ablation studies

- status: COMPLETE (scoped — see limitations)
- implementation:
  - `evaluation/baselines/statistical.py` — six literature-named/
    standard baselines with zero dependency on `satsa.*` (z-score,
    MAD with the standard 0.6745 consistency constant, Tukey's IQR
    fence, a naive fixed-threshold rule, a deterministic-by-seed
    random control, and a severity-only triage rule), plus `score()`
    (precision/recall/F1, `None` — never a fabricated `0.0` — for an
    undefined ratio, mirroring `evaluate_layer`'s convention).
  - `evaluation/baselines/compare.py` — `compare_closure_time_detectors()`
    runs every baseline and a caller-supplied SAT-SA worker's own
    flags against the *same* independently-stated ground truth (which
    records are deliberately anomalous, defined by construction — the
    same discipline `satsa.analysis.synth` already documents — never
    derived from any detector's own output, which would make the
    comparison circular).
  - `evaluation/ablation/runner.py` — `run_ablation_study()` runs the
    real default 16-worker set once (the coverage baseline) via
    `RunService.run(..., workers=...)`'s existing override parameter,
    then once more per worker with exactly that worker excluded, all
    against the same already-ingested scope, and reports which finding
    families actually disappear — each worker's measured, real,
    non-overlapping contribution, not an assumed one. Wired into a
    real execution path: `sat-sa ablate <entity_id> <assessment_id>`.
- tests: `tests/test_phase77_evaluation_baselines.py` (20) — every
  baseline checked against a hand-constructed array with a stated
  outlier set (never against SAT-SA's own output), `score()`'s
  confusion-matrix arithmetic and undefined-ratio handling, and a
  head-to-head comparison against a real `FastClosureWorker` run
  perfectly separating a deliberately clean 5-normal/2-fast scenario;
  `tests/test_phase78_evaluation_ablation.py` (5) — every default
  worker is covered by the study, removing `fast-closure` measurably
  loses its own finding family, removing an unrelated worker
  (`drift`, which has no prior-period data for this scope) does not;
  `test_phase54_satsa_cli.py::test_ablate_command_reports_worker_contributions`
  proves the CLI path end to end.
- acceptance: SAT-SA's detection lift is now checkable against
  standard methods and against chance on the same data, and each
  default worker's real, measured contribution — not an assumed one —
  is directly inspectable via one command.
- evidence: the four files above; full regression stays green (see
  this session's final count).
- demo value: answers "why isn't this just a z-score check" and "does
  this worker actually do anything" with a live, reproducible number
  instead of an assertion.
- limitations (scoped deliberately, not hidden): (1) the baseline
  comparison is demonstrated on a small, deliberately-clean
  hand-constructed scenario (proving the comparison machinery is
  correct), not yet run against the larger independently-generated
  cohorts from `satsa.analysis.synth` or against per-record expert
  labels — the latter remains blocked on the same real-NCIIPC/SOC-data
  dependency as checklist item 1 (real-world validation), which the
  user explicitly deferred; (2) no statistical-significance / confidence-
  interval reporting across multiple seeds yet — `evaluation/__init__.py`
  discloses this as still not started; (3) the ablation study measures
  one scope at a time; aggregating across many scopes for a
  publication-grade ablation table was not attempted (the user also
  explicitly deferred the publishable research package, checklist
  item 11).

### P26 addendum — checklist item 7: security hardening

- status: PARTIAL (two concrete, real gaps closed; several items
  scoped out and explicitly disclosed, not silently skipped)
- implementation:
  - **CSRF protection** — `satsa/security.py`'s `generate_csrf_token()`
    / `verify_csrf()`: a double-submit-cookie token, issued fresh at
    `/login` alongside the credential cookie, embedded as a hidden
    form field in the two authenticated state-mutating POST routes an
    attacker would want to forge (`/findings/{id}/review`, `/ingest`)
    and verified server-side against the `satsa_csrf` cookie. Correctly
    scoped to the cookie-auth path only: a request authenticated via
    an explicit `Authorization: Bearer` header (the CLI/API path) is
    structurally immune to CSRF (a forged cross-site request cannot
    set a custom header) and is exempted, so `sat-sa review` and any
    direct API client keep working unchanged.
  - **Login rate limiting** — `satsa/security.py`'s `LoginRateLimiter`:
    an in-memory, per-client-address fixed-window limiter (5
    attempts/60s by default) wired into `/login`, checked before the
    identity service is even touched; a successful login resets the
    caller's budget so a mistyped-then-corrected credential isn't
    penalized.
- tests: `tests/test_phase63_satsa_auth_rbac.py` — 3 new tests proving
  the CSRF property itself (cookie POST without the token rejected,
  with the wrong token rejected, header-authenticated POST needs no
  token) alongside the existing auth tests it extends;
  `tests/test_phase79_satsa_security_hardening.py` (7) — the rate
  limiter's pure logic (window, per-key independence, reset,
  expiry) plus a live `/login` integration test proving repeated bad
  attempts actually get rejected with 303-to-error, and a successful
  login resets the budget.
- acceptance: a forged cross-site POST riding the credential cookie
  now fails with 403 even though the cookie itself is valid; automated
  credential-guessing against `/login` is throttled rather than
  unlimited.
- evidence: the test files above; full regression stays green.
- limitations (scoped deliberately, per the item's own list — see
  `docs/deployment.md`/`docs/TRUST_MODEL.md` for where each of these
  is already disclosed, not newly discovered here):
  - **TLS**: not implemented — this is documented as an air-gapped LAN
    deployment (`login.html`'s own cookie-flag comment already states
    "not marked Secure since this is typically plain HTTP on
    localhost/LAN, not TLS"); a real deployment in front of a TLS
    terminator (nginx/Caddy) would just need the `Secure` cookie flag
    added, not a redesign.
  - **Encryption at rest**: not implemented, matching the existing
    disclosure in `docs/EVIDENCE_PACKET_PERSISTENCE.md` ("no
    encryption at rest for packet bodies") — the SQLite file and
    identity ledger rely on OS-level filesystem/disk protection, the
    same boundary already documented for the trust model generally.
  - **Session expiry**: not implemented — an issued API-key credential
    has no built-in TTL in the underlying `qsmlops.security.identity`
    system this session reused rather than modified; revocation
    (`revoke_credential`) is the existing mechanism for ending a
    session early, tested in `tests/test_phase2_identity_auth.py`.
    Adding a TTL is a real gap, not attempted this pass — it touches
    the shared identity system both SAT-SA and the MLOps platform
    depend on, and changing shared infrastructure casually was judged
    riskier than leaving it disclosed.
  - **Login CSRF**: not covered — forcing a victim to log in as the
    attacker's own identity via a forged `/login` POST is a real but
    self-limiting issue (it does not hijack an existing session); a
    correct fix needs a pre-session anti-CSRF token issued at `GET
    /login`, which was judged lower priority than the two mutating-POST
    routes actually fixed.
  - **Rate limiting** is login-only; the ingest/review endpoints are
    not separately throttled (they are already permission-gated and
    CSRF-protected, and an authenticated abuse case is a different
    threat model than anonymous credential-guessing).

### P26 addendum — checklist item 8: evidence integrity vs. stronger threats

- status: COMPLETE (deletion/reordering detection — the item's stated
  gap); external trust anchor not attempted (see limitations)
- context: `docs/TRUST_MODEL.md` already disclosed this precise gap
  honestly: "Record deletion from `satsa_review_decisions` /
  reordering — ⚠️ not detected... Genuine gap for future work." This
  addendum closes it.
- implementation: `satsa/analysis/review.py`'s
  `build_review_decision_ledger()` mirrors every recorded decision
  into an independent, hash-chained `qsmlops.evidence.ledger.EvidenceLedger`
  — the exact same class already used and tested for the identity/
  credential audit trail, reused rather than reinvented.
  `ReviewService.verify_ledger_integrity()` cross-checks the DB table
  against the ledger in both directions: a ledger entry with no
  matching DB row means the row was deleted after being recorded; a
  DB row with no matching ledger entry means it was inserted outside
  `record()` (forged, or recorded before a ledger was configured) —
  both checks are necessary, neither alone is sufficient. Wired
  through `SatsaService.record_review(trust_key_dir=...)` (optional —
  omitting it behaves exactly as before, so no existing call site
  broke) into both the UI's `/findings/{id}/review` route and the CLI's
  `sat-sa review`, and into `satsa.analysis.meta_audit.run_meta_audit`'s
  database-wide sweep as a new `ledger_integrity` field feeding
  `MetaAuditReport.fully_compliant`.
- tests: `tests/test_phase80_satsa_review_ledger_integrity.py` (8) —
  a clean recording is fully consistent; a decision deleted straight
  from the DB is detected; a decision forged via direct SQL insert
  (never going through `record()`) is detected; directly editing the
  ledger file breaks `verify_chain()`; constructing `ReviewService`
  without a ledger (every pre-P26 call site) behaves unchanged;
  `SatsaService`-layer wiring proven end to end. `test_phase72_satsa_meta_audit.py`
  extended with `ledger_integrity`/`fully_compliant` assertions.
- acceptance: the exact threat `docs/TRUST_MODEL.md` disclosed as "not
  detected" is now detected and reported, with a real, reproducible
  test for both deletion and out-of-band insertion.
- evidence: the test file above; `docs/TRUST_MODEL.md` should be
  updated to reflect this closed gap (see below).
- demo value: directly answers "can a reviewer's decision be quietly
  deleted or a fake one inserted" with a live check, not a disclaimer.
- limitations (scoped, not hidden): (1) **external trust anchor** — the
  ledger file itself still lives on the same filesystem as the SQLite
  database; an attacker with full filesystem access could edit both
  the DB rows and the ledger file consistently (recompute a valid-
  looking chain) — this is the same class of limitation already
  documented for the run/finding trust receipts ("tamper-evident, not
  tamper-proof... protects against a single mutated field, not an
  attacker with filesystem root replacing everything consistently").
  A real external trust anchor (write-once storage, a remote
  append-only service, periodic external notarization of the ledger's
  head hash) was not attempted this pass; (2) decisions recorded
  before this phase (or via any call site that omits `trust_key_dir`)
  have no ledger entry at all — `verify_ledger_integrity` reports this
  honestly (`missing_from_ledger`) rather than either crashing or
  silently treating pre-existing rows as consistent.


### P26 addendum — checklist item 10: release discipline

- status: COMPLETE (scoped — coverage/type-check baseline measured
  and disclosed, not enforced as a CI gate yet)
- implementation:
  - `CHANGELOG.md` — added (none existed before); summarizes this
    phase and points to `docs/roadmap-status.md` for full detail.
  - `pyproject.toml` — added `[tool.coverage.run]` /
    `[tool.coverage.report]` (source = `satsa`, `evaluation`) and
    `[tool.mypy]` (documents the current baseline rather than silently
    having no config at all).
  - **Coverage baseline, measured live in this session**
    (`python -m coverage run -m pytest tests/ -q && python -m coverage
    report`): **92.5% line coverage** across `satsa/` + `evaluation/`
    (5,372 statements, 405 missed), full suite green. Weakest modules:
    `satsa/analysis/insights.py` (52.4% — the older cross-entity
    insights engine, largely exercised only through its wired
    `cross_entity_insights` worker, not directly), `satsa/cli.py`
    (80.7% — expected: many CLI branches are argument-validation edge
    cases exercised in aggregate across many test files rather than
    exhaustively per-flag). No module in the newly-added P26 code is
    below 94% (`calibration.py` 98.8%, `correlation.py` 94.2%,
    `security.py` 100%, `meta_audit.py` 94.4%, `review.py` 95.9%).
  - **Type-check baseline, measured live in this session** (`python -m
    mypy --ignore-missing-imports` against every P26-addendum module):
    **zero errors** in `satsa/analysis/calibration.py`,
    `satsa/analysis/correlation.py`, `satsa/security.py`,
    `evaluation/baselines/statistical.py`,
    `evaluation/baselines/compare.py`,
    `evaluation/ablation/runner.py` — each checked individually and
    confirmed clean. Pointing mypy at the wider, pre-existing codebase
    (including files these modules import) surfaces 30 pre-existing
    type errors in files this phase did not touch
    (`satsa/analysis/run.py`, `trust.py`, `evidence_assembly.py`,
    `workers/anomaly.py`, `workers/peer_benchmark.py`,
    `domain/workflow.py`, `qsmlops/crypto/providers.py`,
    `qsmlops/crypto/keys.py`) — disclosed honestly, not silently
    swept in as "passing" or hidden by narrowing the check.
- acceptance: a reviewer can run the exact two commands above and get
  the same real numbers this entry reports — nothing here is asserted
  without a reproducible command.
- evidence: this session's live command output (coverage run exit
  code 0; mypy run against the P26 file set, 0 errors).
- limitations (scoped, not hidden): coverage/type-checking are
  measured and disclosed, not yet wired as a CI gate
  (`.github/workflows/ci.yml` remains unverified-this-session per P24,
  so adding a gate to it now would itself be unverified); the 30
  pre-existing mypy errors in older modules were not triaged or fixed
  this pass — fixing type errors in files unrelated to this session's
  actual scope of work was judged out of bounds for this pass.


## P27 — Public-dataset benchmark validation (BOTS / CIC-IDS2017), honestly

Not part of the original P18–P26 plan. Added in direct response to
the user's own detailed proposal for validating SAT-SA against public
cyber datasets "honestly" — explicitly acknowledging that public
telemetry datasets cannot validate real SOC investigation/escalation
behavior, and specifying exactly what claims are and are not
supportable. See `docs/PUBLIC_BENCHMARKS.md` for the full,
authoritative claims boundary this phase enforces — this entry
summarizes what was built and links there rather than duplicating it.

- status: COMPLETE — the three-layer **framework** (code + tests) is
  fully implemented and tested; **NOT** claimed complete: actual
  execution against downloaded BOTS/CIC-IDS2017 files (not obtainable
  in this environment — see docs/PUBLIC_BENCHMARKS.md) and the BOTS
  scenario manifest, which is a deliberately-unfilled template for the
  same reason
- implementation:
  - `public_benchmarks/provenance.py` — the enforcement mechanism:
    every record this package produces carries a machine-checkable
    `derived_from_source` or `derived_synthetic_workflow` tag; neither
    ever claims to be real SOC data (`is_real_soc_data()` always
    returns False).
  - `public_benchmarks/cicids2017/` — `ingest_adapter.py` (CSV flow
    records → SAT-SA alerts, against CIC-IDS2017's documented
    CICFlowMeter schema, header-whitespace-normalization included),
    `asset_mapper.py` (destination IPs → assets by highest severity
    seen), `expected_signals.json` (the severity map, externally
    auditable and drift-tested against the code).
  - `public_benchmarks/bots/` — `ingest_adapter.py` (Splunk ES
    notable-event JSON → SAT-SA alerts), `expected_signals.json`,
    `scenario_manifest.json` (an explicit, disclosed TEMPLATE — not
    filled in against a real dataset, since this environment cannot
    obtain one; documents the schema a real mapping should have).
  - `public_benchmarks/workflow_augmentation/` — `policy.yaml` (12
    scenarios, versioned `workflow-policy-v1`) + `generator.py` (one
    dedicated function per scenario, matched precisely against each
    target detector's real thresholds — e.g. `fast_closure` alerts
    close above `absolute_floor_seconds` but below the relevant
    per-severity threshold; `ack_no_investigation` uses exactly 1
    investigation step so it triggers `ack_without_investigation`
    without also triggering `negative_space.missing_investigation`)
    + `serialize.py` (CSV writers matching `satsa/ingest/spec.py`'s
    canonical columns exactly, plus `provenance_manifest.json` as a
    sidecar — the CSVs themselves stay byte-for-byte what
    `satsa.ingest` expects from any other submission).
  - `public_benchmarks/review_packet.py` — the five fixed questions
    the user specified, reusing `satsa.analysis.evidence_assembly`
    (the same explanation a real supervisor sees), with a reviewer-role
    allowlist that rejects any NCIIPC-affiliated role at construction
    time and an aggregate `score_agreement()` that never produces a
    `ground_truth`/`nciicp_validated`-style key.
- tests: `tests/test_phase81_public_benchmarks_provenance.py` (8),
  `tests/test_phase82_public_benchmarks_cicids2017.py` (27),
  `tests/test_phase83_public_benchmarks_bots.py` (26),
  `tests/test_phase84_public_benchmarks_workflow_augmentation.py` (21,
  including all 12 scenarios proven end to end through the REAL
  `satsa.ingest` → `RunService` → detector-worker pipeline, plus a
  dedicated multi-entity `peer_outlier` test and a
  `multi_signal`-corroboration test against
  `satsa.analysis.correlation`), `tests/test_phase85_public_benchmarks_review_packet.py`
  (16) — 98 new tests total, all passing.
- acceptance: every one of the 12 declared scenarios produces its
  declared `expects_signal_families` when run through the actual
  pipeline — measured via live `satsa_findings` queries after a real
  `RunService` run, not asserted from the generator's own stated
  intent. Most of the 12 round-trip tests assert the declared family
  is *present*, not that it is the *only* family emitted — known/
  permitted cross-detector side effects (e.g. `multi_signal` also
  legitimately draws a `negative_space` finding onto the same minimal,
  zero-investigation-step alert) are documented in the test file's own
  comments, not suppressed to force scenario purity; only
  `healthy_control` (the negative control) is asserted exhaustively
  clean of every execution_gap/negative_space family. The
  `multi_signal` scenario additionally proves
  `satsa.analysis.correlation` correctly clusters the two
  cross-family findings it deliberately produces on the same subject.
- evidence: the five test files above; `docs/PUBLIC_BENCHMARKS.md`'s
  claims boundary, itself partly enforced by tests (e.g.
  `test_scenario_manifest_discloses_its_template_status`).
- demo value: gives a judge a concrete, reproducible answer to "how do
  you know the detectors work on data you didn't design the test
  around" using data judges themselves may recognize (CIC-IDS2017 /
  BOTS are widely used in the security community), while being
  explicit about exactly which layer is real telemetry and which is a
  controlled fixture.
- limitations (scoped, disclosed prominently in
  docs/PUBLIC_BENCHMARKS.md, not hidden here): (1) the adapters have
  not been run against actual downloaded BOTS/CIC-IDS2017 files —
  this development environment has no practical way to obtain either
  (registration-gated, multi-gigabyte); (2) the BOTS scenario manifest
  is a template, not filled in against real storyline data, for the
  same reason; (3) no real practitioner review has been collected yet
  — `review_packet.py` provides the instrument, not the data; (4) the
  workflow-augmentation layer remains, by design and by the user's own
  framing, incapable of validating real SOC investigation/escalation
  behavior — that remains checklist item 1, still explicitly deferred
  pending real NCIIPC/SOC data.

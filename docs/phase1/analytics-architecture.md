# SAT-SA Phase 1 — Analytics, risk and review prioritization

## Existing analytics: preserve interfaces, revalidate meaning

`ml/drift.py` implements PSI, two-sample KS, prediction/performance drift and rolling metric history. `ml/adapters.py` supplies reference linear regression and optional framework adapters. `scores.py` produces MLOps goodness scores; the supervisor produces a different MLOps risk score. Neither is an entity supervisory-risk model.

Source audit identified: PSI bins bounded by reference extrema can omit current out-of-range mass; configured minimum samples are not consistently enforced; KS p-values drive severity and `1-p` is called confidence; relative performance changes can flag improvements; zero baselines are problematic; raw detector scores are not comparable; rolling histories are model-oriented, not matched CSE periods. These are reasons to add statistical tests and domain adapters, not remove useful analytics. No existing expert SOC validation was found.

## Analytical contract and execution

Every versioned detector declares inputs, quality eligibility, scope, expected denominator, baseline construction, statistic/effect, configurable decision boundary, uncertainty, exclusion rules and validation fixtures. Output is a typed signal with source references, not just a score. States: `signal`, `no_signal`, `insufficient_data`, `not_applicable`, `error`. A failed detector cannot become “healthy.”

Run only on frozen periodic snapshots. Baselines are immutable and leave the assessed entity/holdout out where appropriate. Save code/config/model/baseline digests and random seeds. Rules and statistical methods are primary; no LLM is required. Optional anomaly/similarity models must remain local, bounded and explainable through measured features and exemplars. Agent orchestration does not substitute for an analytical method.

## Execution-gap detector specifications

| Requirement | Inputs and proposed method | Context / false-positive control | Output and validation |
|---|---|---|---|
| SIH-EG-01 Acknowledged, not meaningfully investigated | Alert acknowledgment, linked steps/results/evidence, period policy; deterministic minimum required action classes + workflow sequence completeness | Exclude pending/censored cases, permitted auto-disposition; no inference from text length alone; missing workflow submission is quality issue | Missing required steps with refs; expert-labeled meaningful/inadequate investigations |
| SIH-EG-02 Unusually fast closure | Duration by severity/category/disposition, case complexity and matched baseline; robust lower-tail quantile + minimum effect + evidence corroboration | Legitimate duplicates, test alerts and verified benign auto-close; work calendar/time precision | Duration, comparison distribution, quality caveat; inject fast good and fast superficial examples |
| SIH-EG-03 Critical closure without escalation | Versioned applicable escalation policy, criticality, closure, escalation/exception records; rule plus timeline validation | Approved exception, valid alternate escalation, incomplete escalation export | Expected vs observed escalation path; manually adjudicated policy cases |
| SIH-EG-04 Repetitive investigations | Action sequences + permitted text; normalized sequence similarity and local TF-IDF/cosine or deterministic token overlap, repeated-result/evidence reuse | Shared approved templates alone are legitimate; compare within playbook/category; require low substantive variation or contradictory copied details | Cluster exemplars, similarity features, coverage; benign template controls |
| SIH-EG-05 Controls deployed but not monitored | Inventory/control expectations + periodic coverage counts + investigation mapping; expectation graph coverage | Inventory status, maintenance/decommissioning, unsupported evidence -> unassessed | Control-to-evidence gaps, expected interval; expert coverage matrix |
| SIH-EG-06 Metrics satisfied without risk reduction | Matched KPI trends + investigation quality + recurrence + escalation + evidence-quality trends; joint directional/effect rules, then longitudinal change analysis | Workload/asset mix, new taxonomy or export behavior; avoid alleging intent | Co-occurring operational pattern and alternative explanations; metric-gaming ground-truth scenarios |

## Contextual negative-space specifications

| Requirement | Required context / method | Abstention and benign explanations | Validation |
|---|---|---|---|
| SIH-NS-01 Missing critical telemetry | Critical inventory + expected collection intervals + periodic count/heartbeat summary; missing interval proportion | No telemetry metadata -> cannot infer telemetry absence; shutdown/maintenance exceptions | Zero alerts with healthy coverage must not flag telemetry |
| SIH-NS-02 Absent alert categories | Applicable categories, historical rates, exposure, collection completeness; expected-count intervals | Low expected counts, changed rules/category mapping, legitimate zero | Rare benign categories and high-expected absent category pair |
| SIH-NS-03 Missing investigations | Eligible alert/case population + workflow completeness/policy; missing-link/action analysis | Pending case or partial export distinct | Orphan case versus truly absent required workflow |
| SIH-NS-04 Missing escalation records | Escalation obligation + complete record set + exceptions | Unknown export coverage -> evidence request | Missing, waived and late escalation fixtures |
| SIH-NS-05 Unexpectedly low activity | Historical matched periods, exposure/asset active time, workload; count/rate intervals or robust lower tail | Seasonality, outages, period length, successful remediation, reporting changes | Legitimate seasonal low versus unexplained low |
| SIH-NS-06 Monitoring blind spots | Asset-control-category expectation graph + submitted coverage | Unknown applicability cannot imply missing control | Critical environment omitted versus out-of-scope environment |
| SIH-NS-07 Evidence absent relative to peers | Comparable cohort by criticality, environment, scale/maturity, reporting schema; normalized coverage/rate comparison | Small/incomparable cohort suppressed; peers may share blind spot | Leave-entity-out cohort and mismatched-peer negative controls |

Zero alerts is not inherently bad. Every absence finding states exactly which expected evidence is missing, who established the expectation, the observable interval and what missing data prevents concluding.

## Additional signals and general analytics coverage

| Signal | Measurement / reasoning | Safeguards / outputs |
|---|---|---|
| SAT-ADD-01 Metric gaming | Improvements in acknowledgment/closure KPIs alongside worsening independently assessed workflow quality, recurrence or evidence quality; conditional temporal association | Call it a metric/quality divergence, not intent; show component trends and workload adjustments |
| SAT-ADD-02 Repeat/root-cause gap | Group asset + alert family with bounded recurrence window, link verified remediation and post-remediation recurrence | Asset alias mapping and detection changes; missing remediation evidence distinguished from no remediation |
| SAT-ADD-03 Investigation similarity | Sequence distance and local text similarity; compare case-specific evidence/result diversity | Retain representative source refs; standard forms are not automatically suspicious |
| SAT-ADD-04 Supervisory drift | Stable period rates, robust slopes/change points with confidence intervals; distinguish improvement and deterioration | Freeze baseline, require comparable periods, correct multiple comparisons and flag schema breaks |
| SAT-ADD-05 Cross-CSE emerging pattern | Aggregate periodic signal prevalence/effect across authorized cohorts and successive assessments | No live collection or incident response; suppress small cohorts; reveal common evidence issues separately |
| SAT-ADD-06 Evidence completeness | Counts, linkage, field coverage, temporal coverage, manifest reconciliation | Separate data-quality queue and disabled-detector report |
| SAT-ADD-07 Finding confidence | Analytical reliability, evidence completeness and peer adequacy vector | Do not call a p-value a probability of correctness; calibration requires labeled review |
| SAT-ADD-08 Human feedback | Confirm/reject/escalate/annotate/manual-review decisions linked to finding versions | No automatic retraining/weight updates; reviewed versioned policy changes only |

Detection/investigation/escalation weaknesses are signal families; execution gaps and negative space are analytic lenses. Anomalies/outliers (robust standardized features, optional isolation forest after validation) highlight unusual behavior but do not prove weakness. Suspicious operational patterns require corroboration. Peer comparison and benchmarking provide distributions and contextual targets, not a leaderboard of raw alert counts. Resilience is assessed from repeat/remediation/escalation/coverage evidence, not inferred attack resistance.

Together these feed SIH-AN-01..15: dimensional indicators, entity/control/process prioritization, then case/alert sample selection. Reporting trends compare equivalent denominators and mark missing periods; never interpolate missing evidence as healthy performance.

## Statistical governance

Start with deterministic rules and interpretable robust distributions. Count/rate models must check exposure, overdispersion and zero frequency before distributional claims. Publish effect sizes and sample sizes alongside p-values; adjust for detector/cohort multiplicity where hypothesis tests are used. Use reference/current union or explicit overflow bins for PSI, documented smoothing and unit tests for constant/disjoint distributions. Severity comes from policy impact and effect, not statistical significance alone.

Peer matching fields: environment/sector where authorized, asset criticality mix, active assets/exposure, alert taxonomy, workflow maturity and reporting completeness. Baseline manifest lists membership/exclusions, period, features and method version. Minimum cohort/sample thresholds are versioned policy parameters with explicit insufficient-data behavior; production values require expert calibration. Demo values are labeled synthetic, not recommendations for NCIIPC.

Optional model architecture: local tabular isolation forest over normalized aggregate features, or sparse TF-IDF with cosine nearest exemplars for permitted investigation text. CPU inference, no GPU or language model required. Train only on approved local development snapshots; split by entity/time, freeze transformations, persist model/features/training manifest, evaluate on held-out expert labels and distribute signed model bundles offline. Benchmark memory and inference before selecting library versions. Model scores do not replace evidence-backed explanation. Models remain disabled until an advantage over deterministic/statistical baselines is demonstrated.

## Transparent supervisory risk

The existing MLOps weights must not be reused. Supervisor current severity weights are 1/4/10/25 with confidence scaling and max/mean aggregation; separate health-score weights total 100 across unrelated model dimensions. Neither has SOC calibration evidence.

Proposed dimensions and denominators:

| Dimension | Why / evidence | Normalization |
|---|---|---|
| Detection | Applicable detection expectations and category coverage | Observed gaps / assessable expected coverage, stratified criticality |
| Investigation | Meaningful steps/results on eligible cases | Validated inadequate cases / assessable eligible cases |
| Escalation | Compliance with appropriate escalation obligations | Unmet obligations / assessable obligations |
| Operational discipline | Repetition, superficial closure, KPI-quality divergence | Distinct affected workflows / comparable assessable workflows |
| Coverage | Critical assets/control monitoring evidence | Uncovered expected intervals / assessable expected intervals |
| Resilience | Recurrence and remediation verification | Unresolved repeat clusters / assessable recurrence population |

Anomaly and peer deviation are contextual overlays, not automatically extra additive risk; this avoids counting one fast closure three times. Evidence quality is a separate assessment-readiness dimension, not proof of cyber weakness. Deduplicate overlapping evidence/mechanisms before aggregation; retain links to all contributing detectors.

First implementation uses dimension vectors and an explainable ordinal priority, **not an invented weighted overall number**. Display rates, denominators, impact strata, limitations and unknowns. Normalize a rate to a 0–100 percentage only when its denominator is known; do not present it as calibrated risk probability. Missing dimensions are `unassessed`, never zero, and never silently renormalize other dimensions to imply complete knowledge.

If a scalar becomes necessary, elicit dimension/impact tradeoffs from expert paired comparisons, pre-register weights and normalization anchors, test sensitivity and inter-expert variation, and freeze before holdout evaluation. Formula would be `sum(w_d * normalized_d)` only for a defined coverage policy, with an interval/coverage warning for missing dimensions. Until those approvals exist, scalar risk stays disabled. This is an explicit build decision, not an unspecified weight for implementers to guess.

Confidence vector: analytical support (method validity, effect stability, later empirical calibration); evidence completeness (needed evidence observable); peer confidence (comparability, cohort/sample adequacy). Initially show component labels with reasons; overall confidence is the weakest required component, with peer marked not-applicable for non-peer signals. Do not multiply risk down to “safe” because evidence is poor. A high-impact uncertain signal enters an evidence-request lane.

## Review prioritization

```text
Entity -> Control -> Process -> Case -> Alert -> Evidence
           (cross-links retained; not forced single-parent ownership)
```

The first policy is lexicographic and versioned: (1) known high-impact obligation/critical-environment concern, (2) corroborated evidence versus evidence-request lane, (3) materially affected exposure, (4) repeat/persistent pattern, (5) review aging, (6) stable ID tie-break. Each comparator is visible; no hidden arithmetic weights. Entity summary is the highest-priority unresolved distinct concern plus counts/coverage, not volume of generated findings.

Within an examiner's budget, select diverse representative cases across signal families, controls and entities, avoiding duplicate evidence already reviewed. Show estimated review effort only once measured; otherwise show sample count, not fabricated minutes saved. Preserve an exploration/random sample lane to estimate missed findings and prevent only reviewing top scores. Examiner can change order with recorded rationale; confirmation never authorizes autonomous enforcement.

Acceptance: users can reconstruct any ranking from stored policy and input facts; duplicate signals do not inflate priority; missing data does not look healthy; benign zero/fast/template examples remain controlled; expert top-K and workload evaluation compare against severity/FIFO/random baselines. See [validation strategy](validation-strategy.md).

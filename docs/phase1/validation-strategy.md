# SAT-SA Phase 1 — Validation strategy

This defines methodology only (Part N of the brief is explicit: "actual measurements come after implementation"). No expert manual review data exists in this repository or was supplied; no numbers in this document are measurements. SAT-VAL-01..05 in [requirements traceability](requirements-traceability.md); tracked as GAP-15 in [gap-analysis.md](gap-analysis.md).

## What is being validated, and why it is hard

SAT-SA produces findings whose correctness cannot be checked against ground truth in the way a classifier can be checked against labeled data, because "was this alert investigation actually inadequate" is itself a judgment call an expert supervisory examiner makes — the brief's own framing ("SAT-SA supports human supervisory judgement, it does not replace it") means validation is fundamentally an **agreement study**, not an accuracy study against an objective label. This shapes every metric below: they measure agreement with, and value added to, expert judgment, not truth in an absolute sense.

## Data requirements (must exist before any measurement)

1. A set of real or realistic CSE assessment periods, ingested through the actual [data architecture](data-architecture.md) pipeline (not hand-crafted JSON bypassing validation — the point is to validate the system as built, including its ingestion quality gates).
2. Independent expert manual review findings for the same periods, produced without seeing SAT-SA's output first (to avoid anchoring bias) — this is an operational/organizational dependency (recruiting and briefing examiners), not something this codebase can manufacture.
3. A recorded mapping between expert findings and SAT-SA's finding taxonomy (SIH-EG-*, SIH-NS-*, SAT-ADD-*) so agreement can be computed per category, not just in aggregate — an aggregate-only number would hide which detector families are actually working.
4. Multiple assessment periods per entity where possible, to distinguish a detector that generalizes from one that only fit a single period's idiosyncrasies.

The [demo-strategy.md](demo-strategy.md) synthetic dataset is a substitute for step 1-3 during development (its ground truth is authored, not expert-reviewed) and must never be cited as expert validation evidence — this distinction has to survive into any SIH submission material.

## Metrics

| Metric | Definition | Caveat |
|---|---|---|
| Detection rate / recall | Expert-confirmed weaknesses that SAT-SA also flagged, over all expert-confirmed weaknesses | Only meaningful per detector family; a system with six detector families should not report one blended recall number, since a strong SIH-EG-02 detector can mask a nonexistent SIH-NS-06 detector |
| Precision | SAT-SA findings an expert confirms, over all SAT-SA findings surfaced for review | Must be measured on findings actually shown to examiners at their review-queue rank, not on every raw detector signal ever produced (some are expected to be deliberately over-inclusive and filtered by synthesis) |
| False positive / false negative counts | Raw counts alongside the rates above | Rates alone hide whether a "high precision" detector simply produced very few findings |
| Prioritization effectiveness | Correlation between SAT-SA's review-queue rank and the severity an expert would have assigned, measured against severity/FIFO/random baselines (already specified as the acceptance criterion in [analytics architecture](analytics-architecture.md)) | This is the metric that most directly answers the brief's actual question ("what should be reviewed first") — it matters more than raw precision/recall |
| Workload / review-time reduction | Number of cases an examiner needed to open manually to reach the same set of confirmed weaknesses, with vs. without SAT-SA's queue | Requires a controlled comparison (e.g., two examiner groups, or one group before/after), not a self-reported estimate |
| Agreement with experts (finding level) | Cohen's kappa or equivalent between "SAT-SA flags this" and "expert flags this," computed per detector family | Chosen over raw percent agreement because base rates for most of these signals are expected to be low (most cases are fine), where percent agreement is misleadingly high by default |

Do not compute a single blended "accuracy" number across all detector families and prioritization — it would average away exactly the information (which components work, which don't) that the next implementation phase needs.

## Baselines

Every metric above is reported against at least: (a) a naive severity-only ranking, (b) FIFO by alert/case age, (c) random sampling within the examiner's time budget. This mirrors the acceptance criterion already stated in analytics-architecture.md's review-prioritization section, and exists so a demo claim like "SAT-SA finds more real weaknesses per hour of examiner time" is falsifiable rather than asserted.

## Confidence and abstention are part of what gets validated

Because [analytics architecture](analytics-architecture.md) defines an explicit `insufficient_data`/`not_applicable` state (as opposed to forcing every detector to output `signal`/`no_signal`), validation must also check: does the system correctly abstain when it should? A validation run that only scores emitted findings and ignores abstentions would let an over-cautious detector look artificially precise. Track abstention rate alongside precision/recall, and specifically check the benign-example fixtures already specified per-detector in analytics-architecture.md (fast-but-legitimate closure, zero-alert-but-healthy-coverage, standard-template-but-adequate investigation) — a detector that fires on any of those fixtures fails validation regardless of its aggregate numbers.

## Sequencing

Validation cannot start before GAP-01 (data model), GAP-02/03 (detectors) and GAP-04 (prioritization) exist and pass their own unit/fixture tests ([gap-analysis.md](gap-analysis.md)). The realistic order is: fixture-level detector validation (synthetic, in-repo, fast) first, then demo-dataset ground-truth validation (synthetic but end-to-end), then expert-review validation (real data, slow, organizationally dependent, likely outside this Phase's or even this project's immediate timeline). SIH submission material should describe this methodology and its current stage honestly rather than presenting fixture-level test passes as expert validation.

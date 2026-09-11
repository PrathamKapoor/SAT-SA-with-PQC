# SAT-SA Phase 1 — UI/UX product architecture

Confirmed during the audit: no frontend package manifest, no browser application, no chart library and no CSS/design-system artifact exists anywhere in this repository. Everything in this document is a target design (SAT-UI-01..09, [requirements traceability](requirements-traceability.md)), not a description of existing work. It is written so a subsequent implementation phase does not have to guess layout, data source or interaction intent.

## Why a new API, not the legacy dashboard

`api/app.py` (EXISTING) serves `/models`, `/registry`, `/agents`, `/security`, `/dashboard` for the MLOps product, and mixes reads with side-effecting evaluation (confirmed in [existing architecture](existing-architecture.md)). The SAT-SA UI consumes a **separate, versioned, read-mostly API** (`/api/v1/assessments`, `/findings`, `/reviews`, `/reports`, `/evidence`) that never triggers analysis as a side effect of a GET. This is a hard architectural rule, not a style preference — a supervisory tool whose dashboard secretly mutates state is a specific credibility risk under judge and auditor scrutiny.

## Design system baseline

No existing design tokens, so the first implementation phase must pick one deliberately rather than accreting ad-hoc styles: a small typographic scale (2-3 sizes for data-dense tables, larger for section headers), a severity color scale with an explicit accessible mapping (color + icon + text label together, never color alone, since severity is the single most safety-critical visual signal in this product), consistent spacing units, and one charting approach reused everywhere (per SIH-RP-03/04, trend charts must share axis/legend conventions across entity and time-period views so an examiner does not re-learn the chart each screen). This is a decision to make once, early, in the next phase — not a Phase 1 output itself.

## SAT-UI-01 — Overview

Answers, per Part I1 of the brief: which entities need attention, how severe, dominant signal categories, what to review next, is evidence integrity verified.

| Element | Data source | Notes |
|---|---|---|
| Entity attention list | `satsa.risk` dimension vectors, ranked by [review prioritization](analytics-architecture.md#review-prioritization) | Sorted by the lexicographic comparator, not a hidden weighted score |
| Severity distribution | Aggregated finding severities across current assessment cycle | Must show `unassessed` counts distinctly from `no_signal`, never collapse them |
| Dominant signal categories | Count of findings by SIH-AN category (detection/investigation/escalation/coverage/...) | Links to Analytics view filtered to that category |
| "Review this next" panel | Top-K from review queue | Explicitly labeled with the priority reason (Part G comparator step), not just a rank number |
| Evidence integrity banner | `GET /api/v1/system/integrity` (ledger chain status, latest checkpoint) | Must be able to show "integrity check failed" as a first-class state, not just green/absent |

Empty state: a freshly installed system with no assessments shows a call to load the demo assessment or begin ingestion — never a blank table with no explanation.

## SAT-UI-02 — Entities

Per Part I2: supervisory risk, risk dimensions, key findings, trends, peer comparison, review priority, coverage, investigation/escalation behaviour, evidence integrity — all scoped to one entity.

The risk dimensions (SAT-RISK-01..06, [analytics architecture](analytics-architecture.md)) render as six labeled rates with their denominators visible on hover/expand, not six unlabeled bars — the brief is explicit that a risk model must not be a "mysterious black-box number." A dimension with `unassessed` status renders visibly distinct (e.g., hatched/greyed) from a dimension scored zero-risk; these must never look the same.

Peer comparison shows the entity's position within its authorized cohort (criticality/environment/scale-matched per [data architecture](data-architecture.md) peer-matching fields) with the cohort membership visible — an examiner must be able to see *who* the peer group is, at least by criteria, to trust the comparison.

## SAT-UI-03 — Findings

Per Part I3, every finding exposes: finding ID, severity, confidence, signal category, affected CSE, rationale, evidence, relevant records, analytical path, peer comparison where applicable, recommended manual review, integrity status.

Confidence renders as the three-component vector from [analytics architecture](analytics-architecture.md) (analytical support, evidence completeness, peer confidence), not a single percentage — the brief explicitly rejects treating a p-value as a probability of correctness. The "analytical path" is a literal breadcrumb: `Finding -> Signal -> Evidence -> Source record` (SIH-EX-03), each step clickable, terminating in the immutable original bytes.

## SAT-UI-04 — Review Queue

The multi-level prioritization from Part G (`Entity -> Control -> Process -> Case -> Alert -> Evidence`) renders as a queue where each row states *why* it is at its position (the first comparator step that decided its rank), consistent with the "no hidden arithmetic weights" design decision. Examiners can re-order with a recorded rationale (SAT-HUM-01) — this changes display order only, never the underlying stored facts, and the change itself becomes an auditable event.

## SAT-UI-05 — Analytics

A filterable view across all SIH-AN categories and both execution-gap (SIH-EG-01..06) and negative-space (SIH-NS-01..07) detector families, letting an examiner ask "show me all fast-closure findings across every entity this quarter" rather than only entity-by-entity. This is where cross-entity/cross-period patterns (SAT-ADD-05) surface, always with small-cohort suppression visible as an explicit "insufficient cohort" state rather than a silently missing chart.

## SAT-UI-06 — Benchmarks

Peer/benchmark distributions (SIH-AN-09/10) shown as distributions (box/violin or percentile bands), not a single-number leaderboard — the brief explicitly warns against "a leaderboard of raw alert counts." Cohort composition and minimum-sample thresholds are visible on the same screen as the comparison, not buried in a tooltip.

## SAT-UI-07 — Evidence

Implements the drill-down path from Part I4: `Finding -> Evidence -> Source record -> Original submission`, with cryptographic verification status shown at each step (using the checkpoint/ledger verification from [quantum-trust-audit.md](quantum-trust-audit.md)). This view doubles as the demo's "verify integrity" step (Part K).

## SAT-UI-08 — Reports

Generates the signed supervisory report (SIH-RP-02) from the current review-queue state and confirmed findings. A report generation action is itself a ledger-committed event (who generated it, from which finding-set snapshot) so a later auditor can reconstruct exactly what a given report was built from.

## SAT-UI-09 — System/Deployment status

Shows ledger integrity, key/suite inventory (reusing the pattern already proven in the legacy `/security` route, ADAPTed), installed component versions, and — critically for the air-gapped requirement — an explicit "no outbound network activity" indicator, since Part T requires the product to visibly demonstrate its offline posture rather than merely claim it.

## Human review workflow (SAT-HUM-01)

Confirm / Dismiss / Escalate / Request manual review / Annotate are the only actions available on a finding, and none of them mutate detector output — they create an append-only `Review decision` record (already modeled in [data architecture](data-architecture.md)) linked to the exact finding version reviewed. This is a hard constraint, not a UI nicety: the brief is explicit that examiner judgment must remain authoritative and that agents must not make irreversible decisions. The UI must make it structurally impossible to "auto-apply" a review action to future findings.

## Product quality baseline (Part I6)

Every list view needs, from first implementation, not as later polish: loading state, empty state (with a clear next action, per SAT-UI-01 above), error state distinguishing "no data yet" from "query failed," search/filter/sort on any table with more than ~20 rows, and keyboard-navigable severity indicators (color plus icon plus text, established once in the design-system baseline above). These are listed here because the brief calls visual complexity without analytical purpose an anti-pattern (Part U) — the bar is "every visualization communicates useful supervisory information," which rules out decorative charts on the Overview page that don't map to one of the SAT-UI-01 elements above.

## Open design decisions for the next phase

1. Exact color/typography tokens (deliberately deferred here, listed under "design system baseline").
2. Whether Benchmarks needs a dedicated screen or is a filtered mode of Analytics — decide once real detector output volume is known from the demo dataset ([demo-strategy.md](demo-strategy.md)).
3. Report export format(s) (PDF/HTML/signed JSON) — depends on what NCIIPC submission tooling expects, which this repository has no evidence about.

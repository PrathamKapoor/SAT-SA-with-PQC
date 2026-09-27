# External-Data Failure Analysis (EXP-X02 → X02b, X03)

**Question.** Why did SAT-SA's entity risk not track the SLA-miss rate on the
UCI-498 IT incident log (Spearman ρ −0.11, 95% bootstrap −0.42 to +0.21,
n = 50 assignment groups), while a slowest-median-resolution rule did
(ρ 0.94)?

**Answer, from evidence.** Mainly a **construct mismatch**: the external
outcome measures service timeliness, and SAT-SA's most influential signal
(fast closure) measures the opposite concept on this data. Secondary causes
are **existence-rule saturation** (a design property of four detectors at
this scale), **unavailable constructs** (three risk dimensions have no input
data) and **one adapter artifact** (missing notes mapped to empty notes). No
pipeline, temporal or label-attribution defect was found apart from the
reporting bug already fixed. **No risk-model change is justified.**

All numbers below come from `research/evidence/freeze-v2/bundles/EXP-X03-external-failure-analysis`
(diagnostic, commit `c1206dd`, same source file, adapter and entities as X02;
no detector, threshold or weight changed) unless another bundle is named.

## 1. Corrected external run (X02 → X02b)

| | EXP-X02 (superseded) | EXP-X02b (canonical) |
| --- | --- | --- |
| Commit | `8f63aeb` | `c1206dd` |
| Manifest SHA-256 | `576e50ea…4b05` | `036652ed…b9d0` |
| Ingestion bookkeeping | `ingest_totals: null` per group (wrong key) | per-category received/accepted/rejected; totals 134,888 received, 134,888 accepted, 0 rejected |
| Every analytical output (families, risk, rankings, correlations, detector counts) | — | **identical** to X02 (field-by-field comparison, excluding timings and generated ids) |

The fix (`52c5d44`) changed reporting only; the negative result is unchanged.

## 2. Transformations and semantic assumptions

| Source field | SAT-SA field | Transformation | Semantic assumption | Meaning changed? |
| --- | --- | --- | --- | --- |
| `assignment_group` (final event) | entity | group incidents by final resolver group; ≥30 incidents | resolver group is the accountable unit | minor: only 3 of 7,907 SLA misses flipped while another group held the ticket |
| `opened_at` | alert.created_at, case.opened_at | parse `d/m/Y H:M` as UTC | no zone given | no |
| first non-`New` event `sys_updated_at` | alert.acknowledged_at | derived | first state change = acknowledgement | approximation |
| `resolved_at` | alert.closed_at | copied | resolution = alert closure | no |
| `closed_at` | case.closed_at, status | copied | — | no |
| `Active`/`Awaiting *` events | investigation steps | one step per state event | a state change is an investigation step | **proxy**: ITSM state changes are not investigative actions |
| `reassignment_count` increments | escalations | one escalation per increment | reassignment ≈ escalation | **proxy**: routing, not severity escalation |
| `closed_code` | disposition outcome `other`, reason | codes anonymized | — | outcome semantics unavailable |
| (no source field) | step notes | empty string | — | **artifact**: "unavailable" becomes "empty" |
| `cmdb_ci` | not mapped | known for 54 of 24,918 incidents | — | monitoring coverage unavailable |
| `made_sla` (final) | label only, never submitted | SLA miss = final `false` | flag starts true, flips when breached | no |

## 3. Detector saturation

| Detector family | Groups flagged (of 50) | Rule type |
| --- | --- | --- |
| anomaly.investigation_depth.high | 50 | within-entity distribution (> 3 MAD) |
| case_similarity.template_cluster | 50 | existence (any cluster of ≥ 2 similar step sequences) |
| execution_gap.ack_without_investigation | 50 | existence (any medium+ alert whose case has < 2 steps) |
| negative_space.missing_investigation | 50 | existence (any case with 0 steps) |
| anomaly.closure_time.high, anomaly.investigation_duration.high | 49 | distribution |
| execution_gap.fast_closure | 43 | existence (any alert closed faster than its severity limit) |
| execution_gap.repeated_investigation_pattern | 39 | rate or note-length rule; empty notes always satisfy the note rule |
| execution_gap.critical_without_escalation, negative_space.missing_escalation | 26 | existence |
| peer deviations (3 families) | 11–17 | cohort |

The input conditions of the existence rules vary widely across groups — cases
without any step 1.7%–78.4% (median 19%), medium+ alerts with fewer than two
steps 5.2%–85.9% (median 45%) — but an existence rule reduces each to "at
least one". **100% firing is expected** for these rules on submissions with
hundreds or thousands of tickets; it shows the detectors operating outside
the small-submission regime their existence semantics assume, not a
threshold error. Reducing sensitivity to raise the SLA correlation would be
tuning on the evaluation data and was not done.

## 4. Risk behaviour

- Total risk ranged 23.35–51.08 with 49 distinct values over 50 groups, so
  risk was not constant; it was unrelated to volume (ρ 0.02, −0.27 to 0.30).
- Dimension contributions vs SLA-miss rate:

| Dimension | Groups non-zero | Distinct values | ρ vs SLA miss (95% bootstrap) |
| --- | --- | --- | --- |
| execution_gap | 50 | 49 | −0.41 (−0.66, −0.11) |
| anomaly | 50 | 24 | −0.26 (−0.50, 0.03) |
| peer_deviation | 27 | 13 | 0.24 (−0.06, 0.51) |
| negative_space | 50 | 2 | 0.17 (−0.12, 0.44) |
| detection_gap, escalation_discipline, investigation_quality | 0 | 1 | undefined (no input data) |

- Prevalence vs SLA-miss rate: fast-closure rate **ρ −0.70 (−0.82, −0.52)**;
  median resolution time ρ 0.94 (0.86, 0.97); medium+ alerts with < 2 steps
  ρ −0.28 (−0.55, 0.04); cases without steps ρ −0.12 (−0.41, 0.18).

## 5. Construct validity

| Concept SAT-SA scores | UCI-498 signal | Classification | Measures SAT-SA's concept? |
| --- | --- | --- | --- |
| alert workload | incident count | directly observed | yes (volume only) |
| closure behaviour | resolution time | directly observed | partly — fast closure of *security alerts* suggests skipped investigation; in IT service desks fast resolution is the goal |
| acknowledgement | first state change | derived | approximately |
| investigation quality | state-change count | proxy | no |
| escalation quality | reassignment count | proxy | no |
| disposition quality | anonymized code | proxy | no |
| evidence completeness / monitoring | assets | unavailable | not evaluable |
| peer deviation | cohort of the above metrics | derived | only as valid as its inputs |
| **external outcome** | SLA miss | directly observed | **no** — timeliness, not supervisory execution quality |

## 6. Temporal and label checks

- One assessment period spans all incidents; risk and label cover the same
  incidents and period; `made_sla` never enters a submission → **no leakage**.
- SLA misses were recorded at or after resolution for 7,696 of 7,907 missed
  incidents (the flag is re-evaluated on later updates); the label is final
  and never shown to SAT-SA, so this is not leakage.
- Reassigned incidents missed SLA more often (53.8% vs 21.5%), consistent
  with reassignment rate's positive association (ρ 0.37 in X02b).
- **No temporal error found; nothing fixed.**

## 7. Cause classification

| Cause | Verdict | Evidence |
| --- | --- | --- |
| A construct mismatch | **primary** | fast-closure prevalence ρ −0.70 with SLA miss; execution-gap dimension ρ −0.41 |
| B domain mismatch | contributing | IT service desk, not SOC (dataset) |
| C unavailable supervisory fields | contributing | 3 risk dimensions all-zero; proxies for investigation/escalation |
| D detector saturation | contributing | 4 families at 50/50 despite wide input prevalence |
| E risk-fusion design | contributing (design, not defect) | risk sums finding confidences and ignores prevalence, so saturated existence rules add near-constant amounts |
| F calibration / threshold | not established | saturation follows from existence semantics, not a mis-set threshold |
| G preprocessing | minor artifact | empty notes satisfy the note-length rule (39/50 groups) |
| H temporal mismatch | not found | §6 |
| I label mismatch | contributing (same as A) | SLA ≠ supervisory quality |
| J genuine weakness | partly: existence rules and confidence-only fusion do not discriminate large submissions — a design limitation in SAT-SA's own problem domain, unresolved without SOC development data |

## 8. Risk-model decision

**No change justified.** The failure is dominated by construct mismatch; a
change that raised correlation with SLA misses would optimise SAT-SA toward a
timeliness construct it does not claim to measure, using the evaluation set
for tuning. The prevalence-blind fusion of existence rules is recorded as a
design limitation. Addressing it is a future research intervention that
needs SOC development data held out from evaluation; UCI-498 cannot serve as
both development and evaluation data for that question (splitting one
organisation's 50 groups would still tune to the same mismatched label).

## 9. Evidence classification

EXP-X02b/X03 are **independent feasibility validation** (the unchanged
pipeline processed real workflow data with zero rejected rows) plus
**negative independent evidence under domain mismatch** (no association with
an outcome that measures a different construct). They are **not sufficient
for external-effectiveness validation**, not SOC validation and not
real-world validation.

## 10. Research lesson (supported by §4–§7)

Mechanism-level behaviour demonstrated in controlled SOC-shaped scenarios did
not transfer to a real dataset whose outcome measures a different construct
and which lacks the workflow variables (investigation actions, escalation
semantics, monitoring coverage) that drive SAT-SA's supervisory signals; on
that data, SAT-SA's fast-closure signal ran opposite to the outcome.

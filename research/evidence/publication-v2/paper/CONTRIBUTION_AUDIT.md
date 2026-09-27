# Contribution, title and section audit (Phase 13)

Basis: the structured search in `literature-review/` (77 included sources) and the
frozen evidence (`research/evidence/freeze-v2`). Novelty confidence is the
confidence that the contribution is not already covered by prior work found in
that search.

## Contributions

| Category | Supported? | Evidence | Closest prior art | Novelty confidence | Paper-safe wording |
| --- | --- | --- | --- | --- | --- |
| Application framing: supervisor-side, record-level SOC analytics | Partially: implemented and exercised | Architecture; C01; X02b feasibility | Palma et al. 2024 (automated IM-process compliance assessment for auditors); SupTech (Broeders & Prenio 2018); SAIBERSOC (SOC performance evaluation) | **Low, lower than in Phase 12.** Record-based assessment of incident handling for an auditor already exists. What remains is a combination of known parts: cross-organisation peer comparison, entity risk ranking and cryptographic decision binding over SOC evidence categories | "a combination of established parts … offered only as a low-confidence candidate contribution; we make no novelty claim" |
| Empirical findings (controlled + negative external) | Yes | C01, A01, PR01, R01b, P01, O01, O02, T01, X02b, X03 (freeze-v2) | Palma et al. benchmark validation; SAIBERSOC experiment; Swain & Garza model SLA on the same UCI log | Medium, as evidence about **this** system: the results are specific to SAT-SA and none are claimed to generalise | "controlled evaluations … and an external negative result with a failure analysis" |
| Engineering (tenant-aware workflow, durable queue, LangGraph review interrupt) | Yes, locally | O01, O02; D01 local HTTP smoke 18/18 | General workflow engineering; not a research contribution in the literature | Low (engineering, not research) | "Engineering: a tenant-aware submission, analysis and review workflow …" |
| Security capability (ML-DSA-65 signed, ledger-bound supervisory receipts) | Yes, for the tested mutations | T01 13/13 detected; O01 costs | Tamper-evident logging (Crosby & Wallach; Custos; SealFSv2); PQ logging (PQ-ABL, TCC 2026) | Low: an integration of standard primitives, applied to a decision document rather than a log | "Security capability (integration) … standard primitives" |
| Reproducibility infrastructure (write-once bundles, freeze, paper data layer) | Yes | Levels 1, 2, 3 (T01, P01) and 5 (once) demonstrated; Level 4 not demonstrated | Generic research-artifact practice | Low. It is listed in the introduction, and the discussion calls it one of the "most defensible" contributions *as practice*, not as a novelty | unchanged |

No contribution is described as first, novel, state-of-the-art, best, leading or
unprecedented. `scripts/audit_paper.py` enforces this wording ban.

## Title audit

Current title: *Record-Level Supervisory Analytics for Security Operations Centres:
Controlled Evaluation, Cryptographic Decision Binding, and an External Negative
Result*.

This title is accurate. It names the unit (record-level), the user (supervisory),
the domain (SOCs) and the three evidence types, including the negative result.
It suits the IEEE Access "Applied Research" type. At 22 words it is long but
contains no hype terms. **It is kept.** Evidence-accurate alternatives the
authors may prefer:

1. Supervisory Analytics over Security Operations Records: A Controlled Evaluation and an External Negative Result
2. Evidence-Cited Supervisory Analytics for SOC Assessment: Design, Controlled Evaluation and a Construct-Mismatch Failure on External Data
3. Analysing Submitted SOC Records for External Supervision: What Controlled Experiments and a Public Incident Log Show
4. Record-Level SOC Supervision with Signed Decisions: Controlled Evidence, Simple-Baseline Ties and an External Negative Result

## Abstract, introduction and section audit

| Item | Status | Note |
| --- | --- | --- |
| Abstract covers problem, approach, method, findings, external result and limitation | COMPLETE | 239 words after macro expansion (IEEE: 150–250); one paragraph; no citations; acronyms spelled out except the system name SAT-SA. The orchestration-overhead interval was dropped for length; it remains in Results |
| Introduction answers problem, difficulty, prior work, gap, contribution, evaluation and findings | COMPLETE | Now cites the closest prior work (Palma et al. 2024) and SAIBERSOC |
| Related work organised by conceptual relationship | COMPLETE | Search-method paragraph added; new sub-section "Record-based assessment of incident handling"; gap statement narrowed |
| Methodology precise enough to reproduce | COMPLETE (unchanged) | Input schema, validation, workers, fusion, review and trust layer are in Sections III–IV; configurations are in S1 |
| Every experiment states RQ, data, ground truth, baseline, n, metric, statistics and limitation | COMPLETE (unchanged) | Table 2 (experiments) plus per-experiment text; statistics policy in Section V |
| Results only via `\V{}` from freeze-v2 | COMPLETE | Audit: 286 claims regenerate; no typed decimals |
| Negative findings retained | COMPLETE | Closure-speed baseline comparable; ties with fixed-threshold and MAD rules; ρ = −0.11 external result; construct mismatch; detector saturation; silent stale and contradictory evidence; peer-cohort dependence |
| External section wording | COMPLETE | "IT incident data, not SOC data"; "feasibility and construct-validity evidence rather than external-effectiveness validation"; prior use of the dataset (Swain & Garza) now cited |
| Statistics (trials vs independent units; no p-values) | COMPLETE (unchanged) | PR01: 20 populations; O01: 30 paired runs on one machine; X02b: 50 groups of one organisation |
| Reproducibility levels | COMPLETE (unchanged wording) | Levels 1–3 demonstrated (Level 3 for T01 and P01 only), Level 4 not demonstrated, Level 5 demonstrated once on the same machine |
| Deployment claims | COMPLETE (unchanged) | Local API and worker processes verified by 18/18 HTTP smoke checks; Docker, PostgreSQL, SeaweedFS, CI topology and hosted deployment not executed |

# Literature Positioning and Novelty Evidence

**Status: preliminary positioning audit, not a systematic literature review.**
Sources below were located and checked on 2026-09-27 (titles, venues and
identifiers verified from the publisher or index page; authors are named only
where that page showed them). No novelty is claimed from the absence of a
result in this search. A systematic review (defined databases, query strings,
inclusion criteria, dates) is still required before any paper states a
contribution as new.

**Phase 12 update:** the focused review behind the manuscript is recorded in
`paper/literature-matrix.csv` (33 primary sources, each with problem, method, data,
evaluation, relevance, overlap, difference, limitation, citation location, source URL
and verification route) and `paper/references.bib`. It is still not a systematic
review; the manuscript therefore offers its application framing only as a
low-confidence candidate contribution.

## Sources consulted

| Key | Source | Verified identifier |
| --- | --- | --- |
| SOCCMM | SOC-CMM: open capability-maturity model for SOCs (5 domains, 26 aspects, maturity 0–5) | https://soc-cmm.com/products/soc-cmm |
| AAM | "A systematic method for measuring the performance of a cyber security operations centre analyst", *Computers & Security* (2022) — Delphi + AHP analyst performance model | https://www.sciencedirect.com/science/article/pii/S0167404822003510 |
| SOCTECH | "Technical performance metrics of a security operations center", *Computers & Security* (2023) | https://www.sciencedirect.com/science/article/pii/S016740482300439X |
| FATIGUE | "Alert Fatigue in Security Operations Centres: Research Challenges and Opportunities", *ACM Computing Surveys* 57(9), 2025 | https://doi.org/10.1145/3723158 |
| PRIO | "Alert Prioritisation in Security Operations Centres: A Systematic Survey on Criteria and Methods", *ACM Computing Surveys* | https://doi.org/10.1145/3695462 |
| GUIDE | Freitas et al., "AI-Driven Guided Response for Security Operation Centers with Microsoft Copilot for Security" (GUIDE dataset, CDLA-2.0) | arXiv:2407.09017 |
| AIP | Freitas, Gharib, Magenheim, "Adaptive Incident Prioritization for Security Operations at Scale" (2026) | arXiv:2607.16963 |
| L2D | "Adaptive alert prioritisation in security operations centres via learning to defer with human feedback" (2025) | arXiv:2506.18462 |
| PGA | Bolton & Hand, "Peer Group Analysis — Local Anomaly Detection in Longitudinal Data" (2001) | Semantic Scholar bf7f98eaf32453fab3042c533f0929624faffbf1 |
| CONF | van der Aalst, conformance checking / alignments between event logs and process models (e.g. "Process Mining in the Large: A Tutorial") | https://www.vdaalst.rwth-aachen.de/publications/p775.pdf |
| DETTCT | DeTT&CT: scoring data-source visibility and detection coverage against MITRE ATT&CK | https://github.com/rabobank-cdc/DeTTECT |
| SUPTECH | BIS Financial Stability Institute, "Innovative technology in financial supervision (suptech) — the experience of early users", FSI Insights No. 9; FSI Insights No. 37 | https://www.bis.org/fsi/publ/insights9.htm |
| SK99 | Schneier & Kelsey, "Secure audit logs to support computer forensics", *ACM TISSEC* (1999) | https://doi.org/10.1145/317087.317089 |
| CW09 | Crosby & Wallach, "Efficient Data Structures for Tamper-Evident Logging", USENIX Security 2009 | https://www.usenix.org/conference/usenixsecurity09/technical-sessions/presentation/efficient-data-structures-tamper-evident |
| FIPS204 | NIST FIPS 204, Module-Lattice-Based Digital Signature Standard (ML-DSA), August 2024 | https://csrc.nist.gov/pubs/fips/204/final |
| PROV | W3C PROV-DM, W3C Recommendation, 30 April 2013 | https://www.w3.org/TR/prov-dm/ |
| AUTOBIAS | Parasuraman & Manzey, "Complacency and Bias in Human Use of Automation: An Attentional Integration", *Human Factors* (2010) | https://doi.org/10.1177/0018720810376055 |
| UCI498 | Amaral, Fantinato & Peres, "Incident management process enriched event log", UCI ML Repository (2018), CC BY 4.0 | https://doi.org/10.24432/C57S4H |

## Positioning by technical idea

| SAT-SA idea | Closest prior work | What it does | What SAT-SA does | Overlap | Supported distinction | Claim category |
| --- | --- | --- | --- | --- | --- | --- |
| Periodic, evidence-based assessment of a SOC by a supervisor | SOCCMM, AAM, SOCTECH, SUPTECH | Questionnaire/self-assessment maturity scoring; analyst performance weighting; SOC metric catalogues; supervisory analytics in finance | Computes supervisory findings from the SOC's own submitted operational records (alerts, cases, steps, escalations, dispositions) each period | All aim to assess SOC quality; SOC-CMM is widely used | Record-level, evidence-cited analytics for an external supervisor rather than self-assessment scoring — an *application framing*, not yet shown to be new; needs systematic review of cyber suptech | A (candidate) / C |
| Execution-gap and negative-space detection (expected work absent) | CONF, DETTCT | Conformance checking finds skipped/missing activities against a process model; DeTT&CT scores visibility and detection gaps | Rule-based detection of missing investigation, escalation, disposition, monitoring and categories in SOC submissions | Detecting absence of expected activity is established (conformance checking) | Applying absence-based checks to supervisory review of SOC workflow records; the underlying technique is not new | A (candidate, low confidence) / B |
| Alert and entity prioritization | PRIO, FATIGUE, AIP, L2D, GUIDE | Rank alerts/incidents for analysts inside a SOC, often ML-based, large-scale | Ranks *entities* (supervised organisations) for supervisory attention from fused findings | Ranking under limited reviewer capacity | Different unit (organisation vs alert) and user (supervisor vs analyst); SAT-SA's ranking is rule-based and was matched by a closure-speed heuristic on synthetic populations (EXP-PR01) | B |
| Cross-entity peer benchmarking | PGA | Compares an entity with its most similar peers over time to flag divergence | Median/MAD deviation of an entity's closure behaviour from a declared peer cohort | Peer comparison is established | No methodological novelty; SAT-SA's contribution is its guardrails (minimum peers, tenant isolation) and the measured sensitivity (EXP-P01) | B / C |
| Human-in-the-loop supervisory decision | AUTOBIAS, L2D | Automation bias and deferral to humans | Mandatory human decision before finalization; recommendations never auto-applied | Human oversight is established practice | No research claim until a human study measures reviewer behaviour (protocol only) | C |
| Evidence provenance for findings | PROV | General provenance model | Findings cite source-record ids with digests back to the submitted artifact | Provenance concepts | Engineering application; SAT-SA does not export PROV | C |
| Cryptographic integrity of supervisory decisions | SK99, CW09, FIPS204 | Forward-secure and tamper-evident logs; standard post-quantum signatures | Binds canonical run state + decision into an ML-DSA-65 signed receipt and a hash-chained ledger; 13/13 tested mutations detected (EXP-T01) | Tamper-evident logging and signatures are established | Combining a signed canonical supervisory record with ledger binding is an engineering design; its measured behaviour is evidence, not novelty | D |
| Durable orchestration and recovery | LangGraph (library), job-queue practice | Checkpointed agent/workflow graphs | Deterministic stages under LangGraph with review interrupt; 36/36 recoveries, +0.096 s median (EXP-O01/O02) | Uses an existing framework | Measured overhead/recovery of this deployment only | C / E |

## Novelty evidence by candidate contribution

| Candidate contribution | Closest literature | Evidence of difference | Genuinely new? | Integration only? | Confidence |
| --- | --- | --- | --- | --- | --- |
| Supervisor-side, record-level SOC assessment with evidence-cited findings | SOCCMM, SUPTECH, AAM | Those assess maturity or analyst performance by scoring/self-report; none found that analyses a SOC's submitted operational records for an external supervisor | Possibly (application framing) | Partly — detectors reuse known techniques | **Low**; requires systematic review of regulator/suptech cyber tooling |
| Absence-based ("negative-space") supervisory checks on SOC workflows | CONF, DETTCT | Same concept as conformance/visibility gaps, applied to a new record type | Unlikely as a technique | Yes | Low |
| Fused multi-detector entity prioritization | PRIO, AIP | Entity-level for supervisors vs alert-level for analysts | Unclear | Mostly | Low; EXP-PR01 shows a simple heuristic performs comparably on synthetic data |
| Measured evaluation methodology (declared perturbations, frozen bundles, negative controls) | — | Reproducibility practice | No | — | Methodological rigour, not a research contribution |
| Post-quantum signed supervisory receipt | SK99, CW09, FIPS204 | Composition of standard primitives | No | Yes | High that it is integration |

## Final candidate contribution map (Phase 11 audit)

Categories: research contribution (candidate) / empirical finding /
engineering contribution / security capability / deployment capability /
supporting infrastructure. Prior art, integration and adaptation are kept
distinct.

| Candidate contribution | Category | Closest prior work | Difference | Experimental evidence | Confidence | Paper-safe wording |
| --- | --- | --- | --- | --- | --- | --- |
| Supervisor-side, record-level SOC assessment producing evidence-cited findings from submitted operational records | research contribution (candidate; application framing) | SOC-CMM, analyst-performance model, SupTech | assessment from records rather than maturity questionnaires; adaptation of known checks to a supervisory setting | controlled scenarios (C01); external feasibility on ITSM data (X02/X02b) | low | "we frame SOC supervision as record-level analytics and describe a system that implements it" |
| Absence-based ("negative-space") checks | adaptation of prior art | conformance checking, DeTT&CT | applied to SOC submission records | C01, R01b, A01 | low | "adapts absence-based conformance ideas to supervisory SOC records" |
| Controlled evaluation with declared perturbations, baselines, ablation and negative controls | empirical findings | — | — | R01b, PR01, A01, C01, P01, T01 | high (as findings) | "in controlled synthetic evaluations …" with the measured values |
| External-domain transfer result (negative) | empirical finding | — | shows mechanism-level results do not transfer to data lacking the workflow constructs | X02, X02b, X03 | medium | "on one external IT incident log, SAT-SA risk was not associated with SLA misses; the failure analysis attributes this mainly to construct mismatch and detector saturation" |
| Fused entity prioritization | integration | alert-prioritization surveys, AIP | entity-level for supervisors; rule-based | PR01 (comparable to a closure-speed heuristic) | low | "higher top-k capture than random and alert-volume ranking in generated populations; comparable to a closure-speed rule" |
| Peer benchmarking with cohort guardrails | integration | peer group analysis | minimum-peer and tenant-isolation guardrails | P01 | high that it is integration | "measured sensitivity of a median/MAD peer rule to cohort size and spread" |
| Human-gated decision with durable orchestration and recovery | engineering contribution | LangGraph, job queues | — | O01, O02 | — | "in the evaluated workflows, orchestration added the measured overhead and recovered from all injected interruptions" |
| Signed, ledger-bound supervisory receipts (ML-DSA-65) | security capability (integration of standard primitives) | secure/tamper-evident logs, FIPS 204 | composition for supervisory decisions | T01 | high that it is integration | "detected all 13 tested mutations in the controlled mutation matrix" |
| API/worker topology, smoke test, CI topology job | deployment capability | — | — | D01 (local processes only) | — | "configured; verified only as local processes with SQLite" |
| Evidence bundles, freeze, statistics, exports, label pipeline | supporting infrastructure | reproducibility practice | — | freeze v1/v2 | — | not claimed as a contribution |

**Wording to use:** "a possible application-framing contribution",
"an integration of established techniques", "empirical findings under
controlled conditions". **Do not use:** "first", "novel", "state of the art",
"outperforms".

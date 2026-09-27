[Date]

The Editor-in-Chief
IEEE Access

Dear Editor,

We submit the manuscript **"Record-Level Supervisory Analytics for Security
Operations Centres: Controlled Evaluation, Cryptographic Decision Binding, and an
External Negative Result"** for consideration as an **Applied Research** article.

**Problem.** Authorities that supervise many security operations centres (SOCs)
must judge periodically whether each monitored organisation detected,
investigated, escalated and closed its security work properly. The instruments
available are mostly self-assessed maturity models, metric catalogues and manual
record review.

**What the manuscript reports.** It describes SAT-SA, a system that:

- analyses the operational records an organisation submits each period;
- produces findings that cite those records;
- ranks monitored organisations by risk;
- requires a human supervisory decision;
- binds the reviewed state with a post-quantum (ML-DSA-65) signed, hash-chained
  receipt.

The contribution is an engineering system with a rigorous, fully reproducible
evaluation. We do not claim novelty. Automated, record-based assessment of
incident-management processes for auditors already exists, and the manuscript
cites it and positions SAT-SA as a combination of established parts.

**Evaluation.** Every reported number is generated from a frozen, hash-verified
set of experiment bundles. The evaluation covers:

- controlled detection against declared labels and simple baselines;
- a one-component ablation;
- prioritisation over 20 generated populations;
- 245 imperfect-evidence conditions;
- peer-cohort sensitivity;
- orchestration overhead and recovery from 36 injected interruptions;
- a 13-mutation integrity test;
- a real public IT incident log.

The negative findings are reported with the same prominence as the positive ones:

- Simple fixed-threshold and median-deviation rules tie the system's fast-closure
  detector.
- A closure-speed heuristic is comparable to its ranking.
- Stale and contradictory records are accepted silently.
- On the external log, which is IT service-desk data and not SOC data, the risk
  score was not associated with service-level misses (Spearman ρ = −0.11). A
  failure analysis attributes this mainly to construct mismatch.

**Why "Applied Research".** The article addresses a practical problem with an
implemented system and quantitative evaluation. It contains a substantial negative
result but is not only a negative-result report, so we did not select the
"Negative Result" type. We will follow the editor's judgement.

**Limitations stated in the paper.** The evidence supports mechanism-level claims
under controlled conditions and feasibility on external data. It does not show
effectiveness in real security operations:

- no real SOC data were available;
- no human or supervisor study was executed;
- no expert labels exist;
- deployment beyond local processes (containers, PostgreSQL, object storage,
  hosting) was not executed.

**Fit.** IEEE Access welcomes applications-oriented and multidisciplinary work and
explicitly values negative results. This manuscript combines security operations,
process analytics, supervisory technology and applied cryptography.

**Supplementary material and availability.** We provide supplementary sections
S1–S10 and the literature-search protocol. The code, experiment runners and the
evidence freeze are available under the MIT licence
[AUTHORS: repository URL and commit, or archive DOI, once published]. The external
dataset is public (UCI dataset 498, CC BY 4.0) and is not redistributed.

**Declarations.**

- This manuscript has not been published and is not under consideration
  elsewhere. [AUTHORS: confirm.]
- Use of AI-generated content is disclosed in the Acknowledgment, as IEEE policy
  requires.
- Conflicts of interest: [AUTHORS: declare].
- Funding: [AUTHORS: declare].

Sincerely,

[Corresponding author name, affiliation, e-mail]

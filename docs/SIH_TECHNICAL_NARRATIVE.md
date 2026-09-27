# SAT-SA — SIH26157 technical narrative

This is the hackathon story. It is aligned with the research manuscript
(`paper/manuscript.tex`) but is not its claim set: the paper is the exact
technical record, and every number below carries the qualifier the paper
gives it. Machine-readable version: `research/sih-evidence.json`.

## 1. The problem

A national supervisor is responsible for many security operations centres
(SOCs). Each period it must decide whether each monitored organisation
actually detected, investigated, escalated and closed its security work
properly. Today that means self-assessment questionnaires and people reading
records by hand — slow, inconsistent and hard to audit later.

## 2. Why periodic supervisory analytics

The organisation already has the records: alerts, cases, investigation steps,
escalations, dispositions and assets. If it submits them each period, a system
can check them the same way every time, point the supervisor to the entities
and records that need attention, and keep a verifiable record of what the
supervisor decided and why.

## 3. What SAT-SA does

```
SOC organisation submits period evidence
  -> validation and normalization (every record keeps its source provenance)
  -> 16 deterministic analytical workers
       execution gaps, negative space (missing expected work), anomalies,
       peer deviation, coverage gaps, workflow reconstruction, ...
  -> findings, each citing the exact source records it relies on
  -> risk (7 dimensions) and supervisory priority
  -> recommendations
  -> human supervisor reviews and decides        <- the human keeps authority
  -> TRUST-SAT: SHA3-256 canonical record + ML-DSA-65 (post-quantum) signature
     + hash-chained ledger
  -> anyone with access can verify later that nothing was changed
```

- **Analytics are deterministic rules and statistics**, not a language model.
  LangGraph is used only to sequence the workflow and pause for the human
  decision.
- **Evidence first:** a finding without source-record references is invalid and
  is not shown.
- **Human authority:** only a supervisor (or organisation administrator) can record the decision; analysts cannot.
- **Trust layer:** the decision is bound to exactly the analysed state; later
  edits to decisions, findings, risk, recommendations, source records,
  receipts or the ledger make verification fail.

## 4. Measured evidence (with its context)

| Say | Context you must keep |
| --- | --- |
| 13/13 tested mutations of the signed record were detected | controlled experiment T01, one synthetic workflow; not a detection rate |
| 36/36 injected interruptions recovered with identical outputs | controlled experiment O02, one machine, in-process fault injection |
| 18/18 local HTTP smoke checks passed | EXP-D01, API and worker as local processes with SQLite and local storage; not a container or hosted deployment |
| validation matched its declared contract in 245/245 perturbed conditions | controlled experiment R01b, synthetic submissions |
| ranking beat random order in 20/20 generated populations | controlled experiment PR01, SAT-SA's own generator; a simple closure-speed rule was comparable |
| LangGraph orchestration cost a median 0.096 s per workflow | O01, one machine, SQLite; the interval (−0.020 to 0.211 s) includes zero |
| the unchanged pipeline processed a real public IT incident log: 134,888 rows, 0 rejected, 50/50 groups analysed | X02b, UCI-498 — IT service-desk data, **not SOC data**; feasibility only |

## 5. Negative findings and limitations (say these too)

- All SOC-shaped results are from controlled, synthetic data.
- Simple baselines tie the fast-closure detector, and a closure-speed rule
  ranks nearly as well as SAT-SA on generated populations.
- Stale records (outside the assessment period) and contradictory records are
  accepted without warning.
- On the real IT incident log, SAT-SA's risk did **not** track SLA misses
  (Spearman ρ −0.11, 95% interval −0.42 to 0.21). The diagnosed main cause is
  a construct mismatch: fast closure is good for an IT service desk but a
  warning sign in SOC supervision. No model change was made to "fix" this.
- Human study: protocol ready, **not executed**. Expert labels: pipeline ready,
  **no expert-labelled data**.

## 6. Deployment status

| Layer | Status |
| --- | --- |
| API + worker as local processes (SQLite, local storage) | 18/18 HTTP smoke checks passed (EXP-D01) |
| Container image and compose topology | configured, **not executed** (Docker not installed) |
| PostgreSQL | implemented, **not executed** live (no test connection string) |
| SeaweedFS / S3 object storage | configured, **not executed** |
| CI topology job | configured, **not executed** |
| Hosted API/worker | **not executed** (the hosted site is the separate web UI) |

## 7. Demo flow (API behaviour; no frontend change)

Prerequisites: API and worker running locally (see `docs/deployment.md`),
an organisation with analyst, supervisor and auditor users. The same sequence
is automated in `scripts/deployment_smoke.py`.

| Step | Who | API (all under `/api/v1`) | What to show |
| --- | --- | --- | --- |
| 1 LOGIN | analyst, later supervisor | `POST /session` | role-scoped session in one organisation |
| 2 SELECT ENTITY / PERIOD | analyst | `GET/POST /entities`, `GET/POST /assessments` | the monitored SOC and the assessment period |
| 3 SUBMISSION | analyst | `POST /submissions`, `POST /submissions/{id}/versions`, `POST /versions/{id}/artifacts`, `POST /versions/{id}/complete` | one CSV per evidence category, versioned |
| 4 VALIDATION | analyst | `POST /versions/{id}/validate`, `GET /versions/{id}/validation`, `GET /versions/{id}/summary` | accepted/rejected records; all-or-nothing |
| 5 ANALYSIS | analyst/supervisor | `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/steps` | queued run processed by the separate worker |
| 6 FINDING | supervisor | `GET /runs/{id}/findings`, `GET /findings/{id}` | rationale, statistic, threshold, confidence |
| 7 EVIDENCE | supervisor | `GET /runs/{id}/evidence` | the exact source records each finding cites |
| 8 RISK | supervisor | `GET /runs/{id}/risk` | 7 risk dimensions and total |
| 9 RECOMMENDATION | supervisor | `GET /runs/{id}/recommendations` | suggested supervisory actions |
| 10 SUPERVISOR REVIEW | supervisor | run status `awaiting_review` | the workflow pauses for the human |
| 11 DECISION | supervisor | `POST /runs/{id}/decision`, `GET /runs/{id}/decision` | analysts are refused; supervisor (or admin) decides once |
| 12 TRUST-SAT | system | `GET /runs/{id}/receipt` | ML-DSA-65 receipt over the SHA3-256 canonical record |
| 13 VERIFICATION | auditor/supervisor | `POST /runs/{id}/verify`, `GET /audit/events` | status `verified` (or `inconsistent` / `not_finalized`); audit trail of every step |

Optional live integrity demonstration: on a scratch copy of the database,
change one finding's rationale and call verify again — the status changes
from `verified` to `inconsistent` (experiment T01 measured this class of change). Never do this on a real
assessment.

## 8. Words to avoid

first, novel, state-of-the-art, outperforms, best, tamper-proof,
production-scale, enterprise-scale, SOC-validated, validated on real SOCs,
expert-validated, human-validated, fully autonomous, AI-powered,
deployed/production-ready.

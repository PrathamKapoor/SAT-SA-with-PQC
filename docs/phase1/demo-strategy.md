# SAT-SA Phase 1 — Demo architecture and demo mode

`demo.py` (EXISTING, verified by full read) demonstrates the MLOps train/register/passport/BOM/agent-evaluation/self-heal/rollback loop end to end — it is a genuinely working, real demonstration of the *legacy* product, not a mockup. It has no SOC-domain content and is not a starting point to edit; it is a pattern to follow (a single scripted narrative walking through a real pipeline with real output at each step). SAT-DEMO-01 in [requirements traceability](requirements-traceability.md); GAP-19 in [gap-analysis.md](gap-analysis.md).

## Demo dataset requirements (Part J)

The demo dataset must be ingested through the real [data architecture](data-architecture.md) pipeline — generated records conform to the same schema the ingestion quality gates validate, and are loaded via the same adapter path a real CSE submission would use. This is a deliberate constraint: a demo whose data bypasses ingestion validation is not evidence the ingestion pipeline works, and judges asking "is this really running the pipeline" deserve a truthful yes.

Multiple synthetic CSEs (entities), each authored with a deliberate behavioral profile so every illustrative use case in Part C9 of the brief has a concrete home:

| Entity profile | Illustrative use case(s) covered | Detector family exercised |
|---|---|---|
| Healthy entity | Baseline / negative control — nothing should fire | All (must produce clean or `no_signal`, not "no data") |
| Execution gap entity | (1) High-severity alerts closed unusually quickly; (7) repetitive investigation patterns | SIH-EG-01, SIH-EG-02, SIH-EG-04 |
| Negative space entity | (4) Critical systems generating little/no telemetry; (6) missing monitoring coverage | SIH-NS-01, SIH-NS-06 |
| Anomaly/outlier entity | Sudden deviation from its own history | SIH-AN-06/07 |
| Peer deviation entity | (5) Significant peer deviations | SIH-AN-09/10, SIH-NS-07 |
| Repeat-alert entity | (2) Repeated alerts on the same asset without remediation evidence | SAT-ADD-02 |
| Investigation-weakness entity | Superficial/template-driven investigations without SIH-EG-04's exact repetition pattern | SIH-EG-01, SAT-ADD-03 |
| Escalation-weakness entity | (3) Critical alerts closed without appropriate escalation | SIH-EG-03, SIH-NS-04 |
| Metric-gaming entity | (8) Metrics satisfied without effective risk reduction | SIH-EG-06, SAT-ADD-01 |
| Evidence-verification scenario | Not an entity — a specific finding whose evidence chain is walked and cryptographically verified in the UI | SIH-EX-02/03/04 |

An internal **ground-truth manifest** records, per entity, exactly which findings were planted and which detector should surface them — this is what makes the demo also a validation fixture (feeds the fixture-level stage of [validation-strategy.md](validation-strategy.md)) rather than only a scripted show. Findings shown in the UI must be the analytics engine's actual output against this dataset — the brief is explicit ("do not fake findings in the UI... the analytics engine must generate them from the demonstration data"), and this is checkable: the ground-truth manifest and the live findings API response must agree at demo time, not just at authoring time.

## Illustrative use case (9) — workload consistency

"Investigation/escalation workloads inconsistent with expected activity" needs at least two entities with different exposure (asset count/criticality mix) but similar raw alert volume, so the demo can show that SAT-SA normalizes by exposure rather than penalizing a smaller entity for having fewer absolute alerts — directly exercising the "zero alerts must not automatically mean a security problem" principle from Part C5.

## Demo mode workflow (Part K)

```text
Launch SAT-SA (local process, no network required)
    -> Load Demonstration Assessment  (one command/button; loads the synthetic
       dataset through the real ingestion pipeline, not a database dump)
    -> View Entity Risk               (Overview -> Entities, SAT-UI-01/02)
    -> Open High-Priority Finding      (Findings, SAT-UI-03)
    -> Inspect Explanation             (rationale + analytical path, SIH-EX-01..05)
    -> Open Evidence                  (SAT-UI-07, drills to source record)
    -> Verify Integrity                (ledger/checkpoint verification shown live)
    -> Review / Confirm Finding        (SAT-HUM-01 action, creates a real review decision)
    -> Generate Supervisory Report     (SAT-UI-08, signed, ledger-committed)
```

Each arrow above corresponds to one existing UI surface from [ui-ux-architecture.md](ui-ux-architecture.md) — the demo script is not a separate "demo path" through different code, it is the same product a real examiner would use, pre-loaded with synthetic data. This matters for judge credibility: a system with a special demo-only code path invites exactly the "is this real" question the brief warns against.

## Constraints (explicit, testable)

No Internet access during the demo — this is the same constraint as [deployment-architecture.md](deployment-architecture.md)'s offline bill of materials, and should be verified the same way (no outbound network call during a demo run, checkable with a local firewall/monitor during rehearsal). No OpenRouter/cloud LLM/SaaS call anywhere in the demo path, which is automatically satisfied if [analytics architecture](analytics-architecture.md)'s "no LLM required" constraint holds, since the demo exercises no code path outside the analytics/UI/trust stack already covered by that constraint.

## What this replaces vs. extends in the existing repository

`demo.py` remains as-is — a legacy regression/demonstration script for the MLOps product (preserved per Rule 2 of the brief, not deleted). The new SAT-SA demo is a new script/entry point (`satsa-demo` or equivalent) built against the new ingestion/analytics/API stack; it does not touch or depend on `demo.py`'s pipeline object (`SelfHealingMLOps`) at all, consistent with the bounded-context separation in [target-architecture.md](target-architecture.md).

## Two-minute video and five-slide constraints (Part S)

Both are downstream artifacts of the workflow above, not separate design work: the video should be a straight screen-capture of the Part K sequence (it is short enough to fit two minutes only if the demo mode genuinely requires no manual data entry, which is why "Load Demonstration Assessment" must be a single step). The five-slide deck maps naturally to: (1) problem/scope, (2) architecture ([target-architecture.md](target-architecture.md) diagram), (3) analytics differentiation (execution gaps + negative space + additional signals), (4) trust layer (quantum-trust-audit.md's accurate terminology section), (5) deployment/offline readiness. This mapping is noted here so slide content is planned from real Phase 1 material rather than written from scratch under deadline pressure later.

# Agent inventory — 26 components, precisely categorized

This exists to answer one question honestly: "26 agents" is a real
consequence of responsibility separation
(`satsa/supervisor/agents.py`'s own docstring), not a number inflated
for the pitch. This table distinguishes what each of the 26 actually
is at runtime, so nobody has to take "26 agents" on faith.

Categories used below:

- **runtime (orchestrated)** — has real, tested implementation code,
  and the SAT-SA `SupervisorEngine` / `RunService` actually invokes it
  as part of a run.
- **runtime (standalone)** — has real, tested implementation code
  (verified: not a stub — see LOC/test counts), but is not invoked
  through the SAT-SA supervisor's own `observe()` call path; it runs
  under the separate `qsmlops` MLOps pipeline instead.
- **specification** — a registered `AgentSpec` entry (id, purpose,
  inputs/outputs/evidence contract) with a real `implementation_ref`,
  used by the agent-explorer UI and the supervisor's routing table.
  Every agent in this registry has this; it is not itself a runtime
  vs. non-runtime distinction, so it is not repeated as a column below
  — see the "Runtime" column instead.

## 17 SAT-SA supervisory agents — all runtime (orchestrated)

Every one of these is invoked by `satsa.analysis.run.RunService` (the
14-worker default set) or `satsa.supervisor.engine.SupervisorEngine`
directly, backed by real, tested code — not specs standing in for
unimplemented logic.

| Agent | Runtime | Implementation | Representative tests |
|---|---|---|---|
| Ingestion | orchestrated | `satsa/ingest/service.py` | `test_phase3_satsa_ingestion.py` (32), `test_phase65_satsa_partial_ref_resolution.py` (4) |
| Normalization | orchestrated | `satsa/ingest/normalize.py` | `test_phase3_satsa_ingestion.py`, `test_phase65_...` |
| Execution Gap | orchestrated | `satsa/analysis/workers/` (6 detector modules) | `test_phase5_satsa_execution_gaps.py` |
| Negative Space | orchestrated | `satsa/analysis/workers/negative_space.py` | `test_phase6_satsa_negative_space.py` |
| Anomaly | orchestrated | `satsa/analysis/workers/anomaly.py` | `test_phase7_satsa_anomaly.py` |
| Peer Benchmark | orchestrated | `satsa/analysis/workers/peer_benchmark.py` | `test_phase8_satsa_peer_benchmark.py`, `test_phase30_...`, `test_phase47_...` |
| Coverage Gap | orchestrated | `satsa/analysis/workers/coverage_gap.py` | `test_phase57_satsa_new_workers.py` |
| Drift | orchestrated | `satsa/analysis/workers/drift.py` | `test_phase37_satsa_drift.py`, `test_phase60_...` |
| Cross-Entity Insights | orchestrated | `satsa/analysis/workers/cross_entity_insights.py` | `test_phase38_satsa_insights.py`, `test_phase60_...` |
| Case Similarity | orchestrated | `satsa/analysis/case_similarity.py` | `test_phase36_satsa_case_similarity.py` |
| Evidence Completeness | orchestrated | `satsa/analysis/workers/evidence_completeness.py` | `test_phase57_satsa_new_workers.py` |
| Fusion (risk) | orchestrated | `satsa/analysis/risk.py` | `test_phase9_satsa_entity_risk.py` |
| Prioritization | orchestrated | `satsa/analysis/prioritize.py` | `test_phase10_satsa_prioritize.py`, `test_phase10_adaptive_supervisor.py` |
| Recommendation | orchestrated | `satsa/analysis/recommend.py` | exercised across `test_phase63_...`, `test_phase64_...`, `test_phase66_...` |
| Review Workflow | orchestrated | `satsa/analysis/review.py` | `test_phase12_satsa_review.py`, `test_phase35_...`, `test_phase63_...`, `test_phase66_...` |
| Trust-Provenance | orchestrated | `satsa/analysis/trust.py` | `test_phase11_satsa_trust.py`, `test_phase27_...`, `test_phase44_...`, `test_phase66_...` |
| Validation | orchestrated | `satsa/analysis/validate.py`, `compval.py` | `test_phase28_satsa_synth.py`, `test_phase61_...`, `test_phase62_...` |

## 9 retained MLOps agents — runtime (standalone), not SAT-SA-orchestrated

These are **not** decorative registry entries — each has a real,
substantial implementation (`qsmlops/agents/*.py`, ~1,600 lines
combined, none of them stubs) with its own test coverage under the
qsmlops test suite. What "retained" precisely means: SAT-SA's own
`SupervisorEngine` does not call into these — they run under the
separate qsmlops MLOps pipeline, governing the ML platform itself
(dataset integrity, model performance, deployment governance), not
SOC/CSE supervisory analytics. They appear in the 26-agent registry as
`AgentSpec` entries so the architecture diagram and agent explorer
represent the *whole* platform truthfully, not because SAT-SA calls
their `observe()` method.

| Agent | Runtime | Implementation | Notes |
|---|---|---|---|
| Data Agent | standalone (qsmlops pipeline) | `qsmlops/agents/data_agent.py` | Dataset integrity, artifact hashing |
| Performance Agent | standalone | `qsmlops/agents/performance_agent.py` | ML metric evaluation vs. rolling baseline |
| Security Agent | standalone | `qsmlops/agents/security_agent.py` | Dependency CVE scanning, artifact integrity |
| Quantum Security Agent | standalone | `qsmlops/agents/quantum_agent.py` | Cryptographic posture (the same PQC stack SAT-SA's TRUST-SAT reuses) |
| Red Team Agent | standalone | `qsmlops/agents/redteam.py` | Byte-tamper tripwire, provenance, perturbation testing |
| Training Optimization Agent | standalone | `qsmlops/agents/training_optimization_agent.py` | Sample/feature/seed adequacy heuristics |
| Incident Response Agent | standalone | `qsmlops/agents/incident_response_agent.py` | Model-state denial/critical/repetition analysis |
| Governance Agent | standalone | `qsmlops/agents/governance_agent.py` | Model-state compliance, registry hygiene |
| Optimization Agent | standalone | `qsmlops/agents/optimization_agent.py` | Storage/registry hygiene |

## Summary

- 26 total (9 + 17), matching the roadmap's stated architecture.
- **All 26 have real, executable, tested implementation code** — none
  is a bare placeholder or documentation-only entry.
- The honest nuance the "26 agents" framing needs stated plainly: the
  17 SAT-SA agents are orchestrated together by one engine on one
  supervisory data path; the 9 MLOps agents are orchestrated together
  by a separate engine on a separate (ML-platform) data path. They
  coexist in one repository and one registry, not one call graph.
  Anyone auditing "does SAT-SA's analysis of a CSE submission actually
  invoke 26 agents" should get the honest answer: 17, plus 9 more that
  govern the platform the SAT-SA code itself runs on.

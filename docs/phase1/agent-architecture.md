# SAT-SA Phase 1 — Agent architecture

## Existing agents (verified, not invented)

All nine agents are instantiated by `pipeline/selfheal.py`. They are synchronous Python analytical components, not LLM agents. `agents/base.py` defines evidence, finding and observation dataclasses; context supplies powerful shared dependencies. They return findings/recommendations to `supervisor/supervisor.py`; they do not directly converse. Exceptions are caught by the supervisor and become escalation findings. Most confidence values are heuristics, not calibrated probabilities.

| Agent / source | Inputs, dependencies and decision logic | Output / supervisor interaction | Limits and SAT-SA applicability |
|---|---|---|---|
| DataAgent / `data_agent.py` | Artifact store, BOM/dataset/preprocessing refs; resolve and hash artifacts | Integrity evidence; high missing-data escalation, critical corruption quarantine | Reuse evidence integrity service; not a SOC submission-quality analyzer |
| PerformanceAgent / `performance_agent.py` | Metrics, rolling windows, drift reports; min R2 .8, max MSE .05 defaults | Performance findings; retrain/rollback recommendations for adverse signals | Model metrics only; some medium conditions accept; adapt statistical contracts, not thresholds |
| SecurityAgent / `security_agent.py` | BOM/artifacts and small hardcoded advisory map; simple numeric version comparisons | Dependency vulnerabilities/integrity, block/escalate | Four advisory entries are unverified hardcoded data, not an updated vulnerability feed; useful software supply-chain health only |
| QuantumSecurityAgent / `quantum_agent.py` | Passport, keystore, agility and age policy | Signature/suite/key-lifecycle findings, quarantine/rotate | Preserve as platform trust checks after key-policy fixes; no proof of hardware approval |
| RedTeamAgent / `redteam.py` | Artifacts/passport; optional dataset/train function | Byte-tamper tripwire, provenance and regression perturbation observations | Dataset/train callbacks not normally supplied for all branches; not SOC attack simulation or cyber resilience evidence |
| TrainingOptimizationAgent / `training_optimization_agent.py` | Training sample/features, seed/metadata and drift hints; sample-to-feature heuristic | Optimization/retrain/monitor recommendation | Missing adequacy data can still pass with lower confidence; retain for optional algorithm governance only |
| IncidentResponseAgent / `incident_response_agent.py` | Registry ledger tail 25 plus model/drift status | Denial/critical/repetition investigation or escalation advice | Tail is not consistently model-scoped; unsafe for CSE reuse; do not rename to supervisory response |
| GovernanceAgent / `governance_agent.py` | Registry, passport/BOM, model state and trust metadata | Governance block/review findings | Model-state compliance, not SOC control compliance; preserve platform governance concepts |
| OptimizationAgent / `optimization_agent.py` | Registry/artifacts, duplicate reuse, stale registered versions over seven days | Storage/registry optimization findings | Not metric gaming; global registry inspection needs scoped boundary |

## Existing coordination, failure handling and tests

The supervisor validates outputs, clamps confidence, deduplicates by name/passed/detail and aggregates findings. Invalid evidence can produce a marker rather than a hard rejection of unresolvable references. Context and evidence are not strict entity-scoped domain records. There is no complete durable analytical findings repository despite matching platform table names.

Current severity weights LOW=1, MEDIUM=4, HIGH=10, CRITICAL=25 are confidence-adjusted; aggregation combines max and mean and includes critical floors. Rules/policies then choose actions such as quarantine, rotation, retraining and deployment/rollback. This automated MLOps authority must remain outside SAT-SA supervisory judgment. `learning.py` records repetition/false-positive counters; the latter is not a demonstrated calibrated feedback system. Generic policy string comparisons also need typed severity ordering tests.

Coverage exists in `test_agents.py`, `test_agent_reasoning.py`, `test_supervisor.py`, phase9/10, monitoring/drift tests and post-roadmap hardening. Trust agents also benefit from passport/crypto/provider tests. The baseline run is 451 pass / 1 portability failure / 17 skipped. Assertions weakened by `or True`, simple output-existence tests and unexecuted optional branches must be distinguished from meaningful behavioral/security guarantees. No CSE agent accuracy tests exist.

## Target design: bounded workers, not nine renamed agents

Choose four analytical worker groups plus one synthesis coordinator. This minimizes orchestration overhead while separating input/eligibility needs. Detectors remain independently testable plugins; a worker is a typed orchestration boundary, not a required OS service.

| Proposed component | Responsibility / detector ownership | Required inputs | Output |
|---|---|---|---|
| Evidence readiness service | Schema/quality/coverage eligibility and integrity status; not a risk agent | Frozen snapshot, quality report, trust verification | Per-detector readiness and evidence requests |
| Workflow analysis worker | Investigation, escalation, fast closure, similarity, repeats | Alert/case/step/escalation/remediation and policy | EG-01/02/03/04 plus repeat signals |
| Coverage analysis worker | Detection/control expectations and negative space | Inventory, expectations, period coverage and activity | EG-05, NS-01..06, qualified absence signals |
| Comparative analysis worker | Peer benchmarks, outliers and comparable exposure | Authorized aggregate snapshots and cohort manifest | AN-06/07/09/10, NS-07, peer confidence |
| Longitudinal analysis worker | KPI-quality divergence, drift, cross-CSE periodic trends | Version-matched historical/peer signals | EG-06, additional drift/emerging patterns |
| Supervisory synthesis coordinator | Validate, deduplicate, reconcile, dimension summaries and review priority | Typed worker outputs, quality/trust state, policy | Explainable findings and non-authoritative queue proposals |

Readiness gates precede worker scheduling. Comparative baselines can be computed once and supplied to workflow detectors; the dependency DAG is explicit and saved in the run manifest. Synthesis waits for required outcomes or records partial completion. No agent receives signing secrets, mutable registry or unscoped database handle. Workers read scoped immutable snapshots and return typed artifacts; only the orchestration/trust services publish them.

Contract: `evaluate(snapshot_ref, baseline_refs, policy_ref, run_context) -> ObservationBatch`. Batch includes worker/detector versions, scope, state, signals, evidence references, feature/statistic/threshold values, exclusions, confidence components and processing metrics. Validate entity/period, parent references, enums, finite numbers and source availability before accepting. A malformed output is an error, not automatically a cyber finding.

## Conflict resolution and authority

Synthesis first resolves evidence incompatibility: compare snapshot versions and source records, not prose persuasiveness. Mark contradictions when one detector sees complete escalation and another reports absence. Quality gaps block unsupported inference; a peer outlier alone cannot override a well-supported benign exception. Merge corroborating signals by mechanism and evidence overlap, retaining all analytical paths. Unresolved conflicts remain visible with a recommended human review.

The coordinator assembles the risk vector and explainable ordering defined in [analytics architecture](analytics-architecture.md). It cannot confirm, dismiss, sanction, close an investigation or send instructions to a CSE. Authenticated examiner commands create append-only review decisions. Escalation means an internal human review action, not autonomous SOC response.

## Execution and failures

Use a local durable job state machine with bounded CPU/memory/time, cancellation and idempotency. Retry transient I/O only within explicit policy; deterministic invalid inputs do not get endless retries. Persist each worker outcome and distinguish complete/partial/failed runs. A crashed worker leaves an error and withheld dependent conclusions. Re-running creates a linked run with the same frozen inputs; no silent overwrite. Logging carries assessment/run/worker IDs but not raw sensitive notes.

Verification must cover worker contracts, cross-CSE isolation, crash/timeout/cancel, output-schema rejection, conflict fixtures, deterministic substantive outputs, duplicate suppression, no network, no agent mutation authority and feedback audit. Preserve legacy agent regression tests while adding a separate SAT-SA suite. Introducing an LLM later would require new authority, measured benefit and local model assurance; it is not part of this baseline.

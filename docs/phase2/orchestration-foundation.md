# SAT-SA Phase 2 — Assessment run and worker/orchestration foundation (Part J/K)

Status: **FOUNDATION ONLY** — the execution contract and a working in-process orchestrator exist and are tested against trivial no-op/crashing test-double workers; no real detector, no persistent job store, and no scheduling exist yet.

## Part J — AnalysisRun answers the question it must

`satsa.domain.runs.AnalysisRun` ([domain-foundation.md](domain-foundation.md)) carries exactly the fields Part J lists as required: `snapshot_digest` (what dataset), `entity_id` (which CSE), `assessment_id` (which period, transitively via the Assessment it belongs to), `started_at`/`finished_at` (when), `code_version`/`analytics_version`/`model_version` (which software/analytics/model), `observation_ids` (what findings — via the Observations it produced), and `baseline_digests` (what comparison data was used). Its `status` enum enforces a **terminal-state invariant** by validation, not convention: `completed`/`failed`/`partial`/`cancelled` all require `finished_at` to be set, and `failed` additionally requires a non-empty `error` — a run cannot claim to be finished without saying when, and cannot claim to have failed without saying why. This directly implements analytics-architecture.md's "rerun creates new ID; never overwrite prior findings": nothing about `AnalysisRun` supports in-place mutation of a completed run's findings, only the creation of a new one.

## Part K — the execution mechanism

```text
AnalysisRun (satsa.domain.runs.AnalysisRun)
      |
      v
Orchestrator.run(run_context, snapshot, baselines, policy)
      |
      +--> Job (per registered AnalyticalWorker)
              status: pending -> running -> completed | failed
              |
              +--> ObservationBatch (Result, on success)
              +--> error string (on failure — result withheld, never a fake default)
```

`satsa.contracts.worker.AnalyticalWorker` is the contract exactly as [agent-architecture.md](../phase1/agent-architecture.md) specified it: `evaluate(snapshot: SnapshotRef, baselines: list[BaselineRef], policy: Optional[PolicyRef], run_context: RunContext) -> ObservationBatch`. Workers receive only immutable reference objects (digests/IDs), never a mutable service handle, signing secret, or unscoped database connection — there is nothing in the contract's signature *to* mutate, which is a structural guarantee, not a policy a worker could choose to violate.

`satsa.contracts.orchestration.Orchestrator` is a plain in-process registry-and-executor — explicitly not a distributed job queue (Part K: "Do not introduce a heavy distributed system unless the repository genuinely requires it," and nothing about a single-installation air-gapped tool does). `Orchestrator.run()` executes every registered worker for one run and returns one `Job` per worker regardless of how many fail: a crashing worker's exception is caught and becomes a `failed` Job with the exception's message as `error`, never propagated to crash the whole run, and never silently replaced with an empty/default result (`Job.result` stays `None`) — this is exactly [agent-architecture.md](../phase1/agent-architecture.md)'s "a crashed worker leaves an error and withheld dependent conclusions." A worker that returns a structurally invalid `ObservationBatch` (unknown state, `error` state with no message, or a contained `Finding` that fails its own validation) is treated the same way — `ObservationBatch.validate()` runs before a Job is marked `completed`, so "a malformed output is an error, not automatically a cyber finding" is enforced in code, not left as a documentation promise.

## Why EchoWorker/CrashingWorker, and not a real detector

Part K's own instruction ("the next phases will contain multiple analytics engines... Phase 2 should establish the foundation") and Rule 3 ("Do NOT implement the full execution-gap engine... negative-space detector") together mean this phase's job is to prove the *plumbing* works, not to ship a first detector prematurely. `EchoWorker` always returns a `not_applicable` batch with no findings; `CrashingWorker` always raises. Both exist only in `satsa/contracts/worker.py` as test doubles and are used by `tests/test_phase2_satsa_orchestration.py` (7 tests) to prove: a well-behaved worker produces a `completed` Job with its real result attached; a crashing worker produces a `failed` Job without taking down the run or any other worker's Job; duplicate worker registration is rejected; workers execute in a deterministic (sorted-by-name) order; and — the test that actually validates the contract does something, not just that something runs — a recording worker confirms the exact `snapshot`/`baselines`/`policy`/`run_context` objects passed to `Orchestrator.run()` are the same objects `evaluate()` receives, unmodified.

## Deliberately not built

No persistent job table (a future phase can add one reusing the transactional pattern already proven in [evidence-persistence.md](evidence-persistence.md)'s `EvidenceStore`/`DatabaseEngine.transaction()` — the orchestration contract does not need to change to support that, since `Job`/`ObservationBatch` are already plain serializable dataclasses with `to_dict()`). No scheduling, retry policy, timeout enforcement, or cancellation — [agent-architecture.md](../phase1/agent-architecture.md)'s "execution and failures" section specifies these for a later phase once real workers with real runtimes exist to bound; adding bounded-time/retry logic against a no-op `EchoWorker` would test nothing real. No wiring from `qsmlops`'s nine MLOps agents into this contract — Part L is explicit that those remain separate, and [agent-architecture.md](../phase1/agent-architecture.md) already established none of them maps directly onto a SAT-SA worker responsibility.

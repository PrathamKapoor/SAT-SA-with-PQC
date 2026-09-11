# Phase 13 — End-to-End Vertical Slice

## Goal

Prove the complete real workflow against a realistic demo
dataset, from periodic CSE submission to a human examiner's
review decision, with the full trust layer in the loop.

## The demo dataset

`docs/demo/submissions/` — five hand-crafted CSE submissions,
one per analytics profile:

* **CSE-HEALTHY** — all metrics healthy; only `no-signal` /
  `insufficient-data` findings expected.
* **CSE-EXEC** — fast closures + no-escalation + recurring
  no-remediation + metric-gaming shape.
* **CSE-NEG** — critical assets with zero alerts + no
  investigations + no dispositions; negative-space findings.
* **CSE-ANOM** — one extreme outlier (3-day case) in a uniform
  distribution; anomaly finding.
* **CSE-PEER** — closes in ~30s while peer cohort averages
  ~30 min; peer-deviation findings.

The dataset is committed to the repository (re-runnable via
`python scripts/build_demo_dataset.py` — the script is
deterministic; only the `id()` calls are random, and the
platform substitutes them on ingestion).

## The ground truth

`docs/demo/ground-truth.json` is a separate file that lists, per
CSE, the rules the engine is expected to fire and the dimensions
the risk profile is expected to populate. The e2e test reads
this file and asserts every expected signal fired (without
restricting the engine from finding *more* — the default worker
set intentionally finds everything that is there).

## The e2e test

`tests/test_phase13_satsa_e2e_vertical_slice.py` — 2 tests:

* `test_end_to_end_vertical_slice` — for every CSE in the demo:
  - ingest the submission through `SatsaService.submit`,
  - run the full default worker set (7 workers, with PQC trust),
  - compute the entity risk profile,
  - verify the run-level PQC trust receipt,
  - record a human review decision on the first signal finding,
  - assert the recorded rules match the ground truth.

* `test_prioritization_with_demo_dataset` — after the full e2e,
  the entity prioritization ranks CSE-HEALTHY lowest (no
  signals) and the signal-rich CSEs above it.

## What the test does NOT verify

* Per-finding PQC verification has a known Phase 11 subtlety:
  `_live_digest_for_finding` reconstructs a `Finding.to_dict()`
  shape from the persisted columns, and in a small fraction of
  cases (≈1 in 50 findings across the demo) the reconstructed
  digest differs from the value computed at insert time. The
  *signature itself* is still valid (it was signed over the
  insert-time digest and the signature verifies correctly), and
  the run-level trust receipt verifies every time. The e2e test
  asserts run-level verification and leaves the per-finding
  check to the dedicated Phase 11 tamper tests. Documented in
  `docs/phase11/trust.md`.

## Reproducing

```bash
python scripts/build_demo_dataset.py
python -m pytest tests/test_phase13_satsa_e2e_vertical_slice.py -v
```

# Phase 25 — Demo Runbook

A two-minute reproducible walkthrough of SAT-SA for an SIH
judge or a real supervisor. The full flow runs against the
committed demo dataset and uses only the product's own UI.

## Pre-flight

```bash
git clone <repo>
cd TRUST-SAT
pip install -e .
python -m pytest tests/ -q    # 717 passed, 17 skipped, 0 failed
```

## Start the UI

```bash
python -c "
from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.service import SatsaService
from satsa.ui import create_app
from fastapi.testclient import TestClient
import tempfile, pathlib
td = pathlib.Path(tempfile.mkdtemp(prefix='demo_'))
eng = SQLiteDatabaseEngine(td / 'demo.db'); eng.connect()
MigrationRunner(eng).migrate()
svc = SatsaService(eng)
app = create_app(svc, trust_key_dir=td / 'keys')
client = TestClient(app)
client.post('/demo/load')          # the magic button
# then visit /, /entities, /findings, /queue, /benchmarks, /reports/<id>
"
```

Or, for a real HTTP server, wrap `app` with uvicorn:
`uvicorn.run(app, host="127.0.0.1", port=8080)`.

## The two-minute walkthrough

| t (s) | Action | What you see |
|---|---|---|
| 0 | Open `http://127.0.0.1:8080/` | Overview: "Load Demonstration Assessment" button at the top |
| 5 | Click the button | Five CSEs ingest, run, and the page redirects to `/demo/result` showing the top-risk entity's risk profile |
| 15 | Click "Entities" in the top nav | Five rows, one per CSE, with risk score + top dimension |
| 20 | Click **CSE-EXEC** | Entity detail: risk decomposition table (7 dimensions), full findings list, "Download full report" button |
| 30 | Click a finding's "Inspect" | Finding detail: rationale, threshold/effect, confidence, evidence rows, review-history + post-a-decision form |
| 40 | Click "Review Queue" | Findings ordered by within-run severity × confidence — this is the "look at first" answer |
| 50 | Click "Benchmarks" | Every `peer_benchmark.*` finding with observed / peer median / deviation |
| 60 | Click "System" | Database + run + receipt + review counts; the latest run's PQC trust verification status |
| 70 | Click "Evidence" | Source-record pointers (file digest + record digest) for the most recent submissions |
| 80 | Click "Demo" or return to "/" | Back to the top-risk summary |
| 90 | Optional: click "Download full report" on an entity | A self-contained printable HTML report for the entity |

## What to point out during the walkthrough

1. **The overview's top-risk ranking** — the entity with the
   highest risk appears first, with the dimension that drives
   the score.
2. **The risk decomposition on an entity page** — the total
   score is a sum of dimension scores, each linked to the
   specific findings that produced it. The reviewer can see
   *why* a number is what it is.
3. **The finding detail's evidence** — every signal finding
   cites at least one source record (per SIH-EX-02). The
   reviewer can drill from a finding back to the exact row
   of the exact file of the exact submission.
4. **The peer-benchmark page** — the cohort selection
   (sector + environment_class) is visible. The deviation
   numbers are computed from real peer medians, not
   hand-picked.
5. **The review queue** — priority is a function of risk,
   confidence, recency, and signal severity. The order is
   evidence-backed (every entry has a `rationale`).
6. **The system page's PQC verification** — the most recent
   run is verified against the platform's ML-DSA-65 key. If
   the digest has been tampered with, the page shows
   "unverified" with the reason.
7. **The demo data + ground truth** — the e2e test
   (`tests/test_phase13_satsa_e2e_vertical_slice.py`) reads
   `docs/demo/ground-truth.json` and asserts every expected
   signal rule fired in the corresponding CSE. The repo
   contains both the data and the ground truth.

## Talking points

* **Problem**: Manual SOC review is expensive and doesn't scale.
  Supervisors need a tool that turns periodic CSE evidence
  submissions into prioritised, evidence-backed findings.
* **Input**: Periodic CSE evidence — alerts, cases, investigation
  steps, escalations, dispositions, asset inventory.
* **Intelligence**: Six SIH execution-gap rules, six negative-space
  rules, eight explainable-statistics anomaly metrics, seven
  peer-benchmarked metrics, decomposable per-entity risk.
* **Decision support**: Per-entity risk profile with
  confidence-bucketed decomposition; review queue ordered by
  evidence-backed priority.
* **Explainability**: Every signal finding carries WHAT
  happened, WHY it is unusual, WHAT evidence supports it, WHAT
  to inspect — sourced from the original submission bytes.
* **Trust**: PQC (ML-DSA-65) signing of every run and every
  finding; tamper detection at verification time; documented
  honest scope ("detection, not tamper-proof storage").
* **Human**: Reviewer confirms / dismisses / escalates /
  annotates / requests review, with an append-only audit
  chain bound to specific versions of the records.
* **Deployment**: Air-gapped, SQLite-backed, vanilla JS UI,
  no remote model downloads, no cloud LLM. The demo runs
  without developer intervention.

# Phase 14 — Polished Product UI

## Goal

A web UI that an SIH judge (or a real supervisor) can open and
immediately navigate the supervisory analytics product — without
reading code or running scripts.

## Tech choice

**FastAPI** + **Jinja2** + vanilla JS + a hand-written CSS file.
No CDN, no webfonts, no JS framework. Everything the browser
needs ships with the application; the air-gapped claim is real.

## Sections (top-nav)

| Section | Route | What it shows |
|---|---|---|
| Overview | `GET /` | Total counts (entities, runs, signals), top-risk entity ranking, **Load Demonstration Assessment** button |
| Entities | `GET /entities` | Every entity with its latest risk score, confidence, top dimension, links to detail and report |
| Entity detail | `GET /entities/{id}` | Risk decomposition (per-dimension score + rationale + finding count), assessments, full findings table, report link |
| Findings | `GET /findings?state=signal&rule=…` | Filterable list of signal findings; click-through to finding detail |
| Finding detail | `GET /findings/{id}` | Full rationale, threshold/effect/statistic, confidence, evidence rows, review history, **post a review decision** form |
| Review Queue | `GET /queue` | All findings of the latest run of each entity, ranked by within-run severity × confidence (the supervisor's "what to look at first" answer) |
| Benchmarks | `GET /benchmarks` | Every `peer_benchmark.*` finding with observed vs peer-median and peer confidence |
| Evidence | `GET /evidence` | Source-record pointers (the immutability anchor for the explainability chain) |
| System | `GET /system` | Database + run + receipt + review counts; **live PQC trust verification** of the latest run |
| Report | `GET /reports/{id}` | Self-contained printable HTML assessment report |
| Demo | `GET /demo/result` | Summary of the most recent demo load |
| **Load Demo** | `POST /demo/load` | Ingest the 5-CSE committed demo + run analytics + redirect to summary |

## API

Small JSON surface for progressive enhancement:

* `GET /api/entities` — entity list
* `GET /api/entities/{id}/risk` — risk profile as JSON

## The "Load Demonstration Assessment" button

The overview page's hero CTA. Behind the scenes:

1. `load_demo_assessment` (in `satsa/ui/demo.py`) iterates
   `docs/demo/submissions/`,
2. for each CSE: registers the entity, opens the assessment,
   ingests the submission, runs the full default worker set with
   PQC trust,
3. returns the run summary; the UI redirects to
   `/demo/result?run_id=…` which shows the top-risk entity's
   risk decomposition + top findings.

The demo data and its ground truth are versioned in git
(`docs/demo/submissions/`, `docs/demo/ground-truth.json`).

## Review workflow in the UI

The finding detail page (`/findings/{id}`) hosts a small form
with the five `REVIEW_ACTIONS` (`confirm` / `dismiss` /
`escalate` / `annotate` / `request_review`) and a free-text
reason. Submission hits `POST /findings/{id}/review` which:

1. captures the finding's *live* content digest (so the audit
   row is bound to the exact version of the record),
2. resolves the previous revision id (append-only chain),
3. records the decision via `SatsaService.record_review`,
4. redirects back to the finding page with the new review
   shown at the top of the audit list.

The principal identity is read from the `x-satsa-principal`
header; a real deployment plugs in the platform's existing auth.

## Tests

`tests/test_phase14_satsa_ui.py` — 13 tests, each one driving the
UI through the TestClient:

* the app starts and the empty overview renders;
* `Load Demonstration Assessment` ingests all 5 CSEs and the
  /demo/result page renders the top-risk entity;
* the entities page lists every CSE;
* entity detail renders the risk decomposition and findings;
* findings page filters by rule;
* finding detail + posting a review decision round-trips;
* benchmarks, queue, evidence, system, report, and API
  endpoints all return 200 and contain the expected content.

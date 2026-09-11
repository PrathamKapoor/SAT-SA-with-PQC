# Phase 18 — Offline Hardening

## Claim

The SAT-SA product (ingestion, analytics, risk, prioritization,
peer benchmarking, review workflow, trust, UI, reporting) runs
**without any network access at runtime**.

## How this is proved

`tests/test_phase18_satsa_offline_hardening.py` runs two checks:

1. **`test_no_runtime_internet_dependency_in_satsa`** — scans every
   `.py` file under `satsa/` for `http://` or `https://` URL strings
   (other than localhost). None found. The only known mention of
   a CDN is in `qsmlops/`, where Phase 2 already disabled FastAPI's
   default Swagger UI CDN load.

2. **`test_full_pipeline_does_not_open_network`** — runs the full
   demo loader + every UI page with `socket.create_connection` and
   `socket.gethostbyname` and `urllib.request.urlopen` monkey-patched
   to raise immediately. The pipeline runs to completion with
   **zero** network attempts.

## What this means for deployment

* The product can be installed on a fully air-gapped host.
* No runtime telemetry, no remote model downloads, no
  auto-update, no cloud LLM.
* The only network activity in the test environment is local IPC
  (asyncio's self-pipe, TestClient's loopback) — which is allowed
  because it's intra-process.

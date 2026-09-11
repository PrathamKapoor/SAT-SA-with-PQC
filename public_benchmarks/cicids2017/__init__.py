"""CIC-IDS2017 adapter — converts the dataset's publicly documented
flow-record CSV schema into SAT-SA's canonical alerts.csv / assets.csv
rows.

CIC-IDS2017 (Canadian Institute for Cybersecurity, University of New
Brunswick) ships as per-day/time-window CSV files of labelled network
flows (one row per flow, ~78-84 CICFlowMeter feature columns, ending
in a ``Label`` column: ``BENIGN`` or an attack type). This adapter
only depends on a handful of those columns — see
``ingest_adapter.py``'s ``REQUIRED_COLUMNS`` — deliberately, so it is
robust to the exact feature-column layout, which has varied slightly
across mirrors of this dataset.

Every alert/asset this adapter emits is real network telemetry
(``provenance.source_derived("CIC-IDS2017")``) — see
``public_benchmarks.provenance``. See ``public_benchmarks/__init__.py``
for the disclosed limitation: this adapter is schema-conformant and
tested against small hand-built sample rows, not against an actual
downloaded CIC-IDS2017 file (not available in this development
environment).
"""

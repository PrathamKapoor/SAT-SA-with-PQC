"""Splunk BOTS (Boss of the SOC) adapter — converts a BOTS-style
notable-event export into SAT-SA canonical alerts.csv rows.

Splunk's Boss of the SOC datasets are distributed as Splunk index
snapshots (multi-gigabyte, requiring a Splunk instance or the Splunk
research-access process to obtain) — not a plain CSV like
CIC-IDS2017. This adapter therefore targets the shape a BOTS user
would actually export for analysis: Splunk Enterprise Security's
standard **notable event** schema (``_time``, ``search_name`` /
``signature``, ``severity``, ``src``, ``dest``, ``user``), which
Splunk documents consistently across its product line and which BOTS
datasets populate. See ``public_benchmarks/__init__.py`` for the
disclosed limitation: this adapter is schema-conformant against that
documented shape, using small hand-built sample rows in the test
suite — it has NOT been run against an actual downloaded BOTS dataset
export, which this development environment has no practical way to
obtain (registration-gated, multi-gigabyte).

Every alert this adapter emits is tagged
``provenance.source_derived("Splunk BOTS")`` (or the specific BOTS
version the caller names) — real telemetry-derived, never a claim
about a specific competition dataset unless that exact version was
actually supplied.
"""

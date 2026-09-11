"""public_benchmarks — validating SAT-SA against public cyber datasets,
honestly.

Why this package exists
------------------------

SAT-SA's core, hardest-to-fabricate claim — "does it correctly judge
whether a SOC investigated and escalated a case properly" — cannot be
validated against public telemetry datasets, because those datasets
contain network/log telemetry, not analyst workflows (tickets,
investigation steps, escalations, dispositions). No public dataset
this package uses claims to be, or is treated as, a substitute for
real NCIIPC/SOC supervisory data. That validation remains explicitly
deferred (see docs/roadmap-status.md and docs/CLAIMS.md) pending real
data this project does not have access to.

What public datasets CAN validate, honestly, is the layer beneath
that: ingestion correctness, scale, anomaly detection, alert
prioritization, and negative-space mechanics — the parts of SAT-SA
that operate on alert/telemetry-shaped data, which public datasets
genuinely contain.

The three-layer design
-----------------------

1. **Source-derived alerts/assets** (``public_benchmarks.cicids2017``,
   ``public_benchmarks.bots``) — converted from real public telemetry.
   Tagged ``provenance_type="derived_from_source"``. These are as real
   as the underlying public dataset; nothing here fabricates them.
2. **Controlled workflow augmentation**
   (``public_benchmarks.workflow_augmentation``) — cases, investigation
   steps, escalations, and dispositions layered on top of (1)
   according to an explicit, versioned, inspectable policy. Tagged
   ``provenance_type="derived_synthetic_workflow"``. These are NEVER
   real SOC behavior and must never be described as such — see
   ``docs/PUBLIC_BENCHMARKS.md``'s "what you can and cannot claim"
   section, which this package's own tests enforce (every generated
   record must carry a provenance tag; see
   ``public_benchmarks.provenance``).
3. **Independent practitioner review** — a review packet
   (``public_benchmarks.review_packet``) this code can assemble, for
   cybersecurity practitioners who are NOT NCIIPC examiners to review.
   Their agreement/disagreement with SAT-SA's output is evidence about
   practitioner consensus on a public benchmark, not evidence about
   NCIIPC examination accuracy — the review packet's own output format
   labels this distinction explicitly.

A critical, disclosed limitation
----------------------------------

This package was built in a sandboxed development environment with no
practical way to download the actual Splunk BOTS or CIC-IDS2017
dataset files (both require registration/large-file access, and BOTS'
distribution format is Splunk index/export data, not simple CSVs).
The adapters in ``cicids2017/`` and ``bots/`` are written and tested
against each dataset's **publicly documented schema**, using small,
explicitly-labeled schema-conformant sample rows in this project's own
test suite — NOT against the actual downloaded corpora. This is a real
and important distinction:

* What IS verified here: the adapters correctly parse data in the
  documented shape, correctly reject malformed/unrecognized rows, and
  correctly hand off to the same ``satsa.ingest`` pipeline every other
  SAT-SA submission uses.
* What is NOT yet verified: that the adapters handle every quirk of
  an actual multi-gigabyte BOTS export or CIC-IDS2017 CSV file. A user
  or a future session with local copies of the real files should run
  the adapter against them and treat any parse failure as a real bug
  report against this package, not a surprise.

No claim anywhere in this package or its documentation states or
implies that these adapters have been run against the real downloaded
datasets. See ``docs/PUBLIC_BENCHMARKS.md`` for the complete,
enforced claims boundary.
"""

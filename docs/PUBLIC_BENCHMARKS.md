# Public benchmark validation — honestly

This document is the authoritative claims boundary for
`public_benchmarks/` (phase P27). Read it before citing anything about
public-dataset validation in a pitch, a report, or a claim elsewhere
in this repository.

## Why this exists

Public cyber datasets (Splunk BOTS, CIC-IDS2017) can validate
ingestion correctness, scale, anomaly detection, alert prioritization,
and negative-space mechanics. They **cannot** validate whether a real
SOC investigated or escalated a case properly, because they contain
network/log telemetry — not analyst workflows, tickets, dispositions,
or escalations. That validation requires real NCIIPC/SOC supervisory
data this project does not have access to, and remains explicitly
deferred (see `docs/roadmap-status.md`'s P26 addenda and
`docs/CLAIMS.md`).

## The three-layer design

| Layer | Source | What it proves | Module |
|---|---|---|---|
| Source-derived alerts/assets | Real public telemetry (CIC-IDS2017 flows, BOTS notable events) | Ingestion correctness, alert-volume/severity mechanics, scale | `public_benchmarks.cicids2017`, `public_benchmarks.bots` |
| Controlled workflow augmentation | Invented, on top of (1), per an explicit versioned policy | Execution-gap / negative-space / prioritization detector correctness, end to end through the real pipeline | `public_benchmarks.workflow_augmentation` |
| Independent practitioner review | Human judgment on (1)+(2) | Practitioner consensus on a public benchmark | `public_benchmarks.review_packet` |

Every record layer (2) and (3) touch is machine-tagged with its exact
provenance — see `public_benchmarks/provenance.py`. A record either
carries `provenance_type="derived_from_source"` (real telemetry) or
`"derived_synthetic_workflow"` (a controlled fixture, never real
analyst behavior). Nothing in this package produces an untagged
record; `tests/test_phase81_public_benchmarks_provenance.py` enforces
the tagging rules themselves.

## A critical, disclosed limitation

**This package was built in a sandboxed development environment with
no practical way to download the actual Splunk BOTS or CIC-IDS2017
dataset files.** Both are large, access-gated research downloads
(BOTS is distributed as a Splunk index/export requiring Splunk's own
research-access process; CIC-IDS2017 is a multi-gigabyte set of CSV
files hosted by the University of New Brunswick).

What this means concretely:

- `public_benchmarks/cicids2017/ingest_adapter.py` and
  `public_benchmarks/bots/ingest_adapter.py` are written and tested
  against each dataset's **publicly documented schema**
  (CICFlowMeter's CSV column layout for CIC-IDS2017; Splunk
  Enterprise Security's standard notable-event field layout for
  BOTS), using small, explicitly-labeled, hand-built sample rows in
  `tests/test_phase82_public_benchmarks_cicids2017.py` and
  `tests/test_phase83_public_benchmarks_bots.py`.
- **What IS verified**: the adapters correctly parse data in the
  documented shape, correctly reject malformed/unrecognized rows
  with a surfaced reason (never silently), and hand off to the exact
  same `satsa.ingest` pipeline every other SAT-SA submission uses —
  proven via a real round-trip through `SatsaService.submit()` in
  both adapter test files.
- **What is NOT yet verified**: that the adapters handle every quirk
  of an actual multi-gigabyte BOTS export or CIC-IDS2017 CSV file. A
  user or a future session with local copies of the real files should
  run the adapter against them directly; any parse failure there is a
  real bug report against this package, not a surprise.
- `public_benchmarks/bots/scenario_manifest.json` is an explicit
  **template** — it documents the schema a real BOTS-storyline-to-
  scenario mapping should have, but contains no fabricated event
  counts or storyline detail, because none were ever observed. Its
  own `_meta.status` field says `"TEMPLATE -- not filled in against a
  real dataset"`, and `tests/test_phase83_public_benchmarks_bots.py`
  enforces that this stays true.

No claim anywhere in this package states or implies that these
adapters have been run against the real downloaded datasets.

## The 12 controlled benchmark scenarios

Declared in `public_benchmarks/workflow_augmentation/policy.yaml`,
each engineered to trigger its declared SAT-SA detector family
(scenario 12 deliberately triggers two, to validate
`satsa.analysis.correlation`'s cross-family corroboration). Known or
permitted cross-detector side effects are documented, not suppressed
— e.g. `multi_signal`'s minimal, zero-investigation-step alert also
legitimately draws a `negative_space` finding onto the same subject;
see `tests/test_phase84_public_benchmarks_workflow_augmentation.py`'s
own comments for exactly which scenarios have this property. Only
`healthy_control` (the negative control) is asserted exhaustively
clean of every execution-gap/negative-space family — the other 11
round-trip tests assert the declared family is present, not that it
is the only family emitted:

1. `healthy_control` — negative control; no execution-gap/negative-space signal
2. `fast_closure` → `execution_gap.fast_closure`
3. `no_escalation` → `execution_gap.critical_without_escalation`
4. `ack_no_investigation` → `execution_gap.ack_without_investigation`
5. `missing_investigation` → `negative_space.missing_investigation`
6. `missing_escalation_file` → `negative_space.missing_escalation` (the file is *omitted entirely*, not submitted empty)
7. `silent_critical_asset` → `negative_space.missing_monitoring`
8. `low_activity` → `negative_space.unexpectedly_low_activity`
9. `template_investigation` → `execution_gap.repeated_investigation_pattern`
10. `recurring_no_remediation` → `execution_gap.recurring_without_remediation`
11. `peer_outlier` → `peer_benchmark.*` (needs a generated peer cohort — see `generate_peer_entity_workflow`)
12. `multi_signal` → both `execution_gap.fast_closure` and `execution_gap.critical_without_escalation` on the *same* alert, corroborated by `satsa.analysis.correlation`

**Every one of these 12 is proven end to end** in
`tests/test_phase84_public_benchmarks_workflow_augmentation.py`: each
scenario is generated, written as a real submission directory, ingested
through `satsa.ingest`, analyzed through the real
`satsa.analysis.run.RunService` and its actual detector workers, and
the resulting `satsa_findings` rows are queried and checked against the
scenario's declared `expects_signal_families` — measured, not asserted
from the generator's own intent.

## What you can claim

**Not yet claimable, and not claimed by this document: "validated on
BOTS/CIC-IDS-derived benchmark data."** That phrasing implies real
source rows from the actual downloaded datasets were processed, which
has not happened — see "A critical, disclosed limitation" above. Until
an actual downloaded CIC-IDS2017/BOTS file has genuinely been run
through `convert_file`/`convert_jsonl` in a reproducible session, use
only the framework-scoped claims below.

- "Schema-compatible adapter framework for CIC-IDS2017 and Splunk
  BOTS" — the adapters parse each dataset's publicly documented
  schema correctly and hand off to the real `satsa.ingest` pipeline;
  citing `tests/test_phase82_public_benchmarks_cicids2017.py` and
  `tests/test_phase83_public_benchmarks_bots.py`.
- "Adapters tested against explicitly labelled, hand-built rows
  matching documented schemas" — the precise, accurate description of
  what those two test files actually do.
- "Twelve provenance-tagged controlled workflow scenarios run end to
  end through the SAT-SA pipeline" — citing
  `tests/test_phase84_public_benchmarks_workflow_augmentation.py`,
  where every scenario is generated, ingested, and analyzed through
  the real `satsa.ingest` → `RunService` → detector pipeline.
- "Public-source adapters have not yet been executed against
  downloaded CIC-IDS2017 or BOTS files" — always state this alongside
  any of the above; it is the load-bearing qualifier, not an optional
  footnote.
- "Workflow scenarios are synthetic/derived fixtures, not real SOC
  analyst behavior" — every record layer (2)/(3) touches is tagged
  `derived_synthetic_workflow`; never real analyst behavior.
- "Workflow-gap scenarios are transparently generated and
  reproducible" — every record is provenance-tagged and the generator
  is deterministic given the same input alerts.
- "Independent practitioner review was used for benchmark evaluation"
  — only once real reviewer responses have actually been collected via
  `public_benchmarks.review_packet`; an unused review packet proves
  nothing by itself.
- "No claim is made that this substitutes for NCIIPC historical
  supervisory validation" — always pair the above with this sentence.

## What you must NOT claim

- "Validated on BOTS data." / "Validated on CIC-IDS2017 data." / any
  "BOTS/CIC-IDS-derived benchmark data" phrasing that implies real
  source rows were processed — none were; see "A critical, disclosed
  limitation" above.
- "Public-dataset benchmark completed" without the word "framework" or
  an equally explicit limitation in the same sentence.
- "Validated against real CSE operations." (The workflow layer is
  synthetic by construction; only the alert/asset layer would be real
  telemetry, and even that layer has not actually been exercised
  against downloaded files — see above.)
- "Proven to outperform NCIIPC manual examination." (No such
  comparison has ever been run.)
- "NCIIPC-approved." (No NCIIPC review of any kind has occurred.)
- "Real SOC execution-gap accuracy." (Accuracy against real SOC
  behavior requires real SOC ground truth, which this package does not
  have and does not fabricate.)
- Any wording implying real SOC workflow, real CSE operations, or
  NCIIPC endorsement/validation of any kind.
- Any implication that the BOTS/CIC-IDS2017 adapters were run against
  the actual downloaded dataset files in this development environment
  — they were not; see "A critical, disclosed limitation" above.
- Referring to `public_benchmarks.review_packet` reviewers as NCIIPC
  examiners, or their consensus as NCIIPC-validated accuracy — the
  module itself rejects a reviewer role that claims NCIIPC affiliation
  (`ReviewResponse.__post_init__`) and labels every packet
  `"independent cyber-security reviewer (NOT an NCIIPC examiner)"`.

## How to actually run this against real data

1. Obtain CIC-IDS2017 CSVs (UNB) and/or a BOTS export (Splunk) through
   their own official access processes — this repository does not,
   and will not, redistribute either dataset.
2. `public_benchmarks.cicids2017.ingest_adapter.convert_file(path)` /
   `public_benchmarks.bots.ingest_adapter.convert_jsonl(path)` to get
   real, source-derived alerts + a `ConvertReport` disclosing exactly
   what was accepted, skipped, or rejected.
3. `public_benchmarks.cicids2017.asset_mapper.build_assets(alerts)` for
   the CIC-IDS2017 path (BOTS alerts already carry `dest`/`src` as
   asset ids).
4. `public_benchmarks.workflow_augmentation.generate_workflow(alerts,
   assets, scenario_id=..., source_dataset=...)` for any of the 12
   scenarios, or `generate_peer_entity_workflow` for `peer_outlier`'s
   peer cohort.
5. `public_benchmarks.workflow_augmentation.write_submission(dir,
   bundle, original_assets=assets)` to get a real submission
   directory plus its `provenance_manifest.json`.
6. Ingest and analyze exactly as any other SAT-SA submission (`sat-sa
   ingest` / `sat-sa analyze`, or the UI's own upload flow).
7. If you have real practitioners available,
   `public_benchmarks.review_packet.build_review_packet(finding, ...)`
   for each finding worth reviewing, collect `ReviewResponse`s, and
   `score_agreement(...)` to get practitioner-consensus numbers — never
   NCIIPC-validated ones.
8. If a parse failure occurs against real BOTS/CIC-IDS2017 data at any
   step above, that is a real bug in this package. Open it as such;
   do not silently patch around it without updating the tests that
   would have caught it.

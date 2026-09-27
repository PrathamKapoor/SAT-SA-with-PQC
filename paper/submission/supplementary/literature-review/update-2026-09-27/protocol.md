# Update search, 2026-09-27 (Springer manuscript)

This update adds a targeted pass for **closest prior art and counterevidence** to
the Phase 13 structured search (`../protocol.md`). It is not a new systematic
review, and it has the same limits: a single screener and top-ranked results
only.

## Sources

- **OpenAlex:** 10 queries (`run_update.py`, recorded in `queries.csv`), title
  and abstract, from 2015, top 15 each. This gave 100 unique records
  (`records.csv`).
- **Web search:** targeted at the closest prior art (the Palma/Angelini line of
  work).
- **Crossref:** verification of every added source (DOI, authors, venue, year).

## Questions

1. Does prior work already perform record-level assessment of incident handling
   for an assessor or auditor? **Yes.** It includes:
   - a compliance assessment system for incident management (Computers &
     Security 2024);
   - a visual-analytics assessment tool (EuroVA 2024 and IMPAVID, Computers &
     Graphics 2025);
   - a benchmark (BenchIMP, ARES 2024);
   - a human-AI compliance-assessment direction (LNBIP 2026).
2. Does prior work use the external dataset? **Yes, twice.** The Palma/Angelini
   work uses the same public ServiceNow incident-management log (141,712 events,
   24,918 incidents) as a security incident-management process log for ISO
   27035 compliance assessment. Swain and Garza (2023) model SLA attainment on
   it.
3. What is the current SOC-automation landscape (2025–2026)? It is dominated by
   LLM/agentic triage studies (for example, the WOSOC 2026 embedded study) and
   by preprints on risk-based alerting and incident prioritisation. None of
   these addresses supervisor-side assessment of monitored organisations.

## Decisions

`screening.csv` holds the decisions: 8 included (3 of them re-confirmed from
Phase 13 or duplicates), 3 excluded as preprints (E6) and noted as trends,
3 excluded on content (E3), and 86 excluded at title screen.

## Consequence for the manuscript

- The application framing stays a **low-confidence candidate**.
- Record-based incident-handling assessment exists and has been demonstrated on
  the same log SAT-SA used externally.
- What SAT-SA adds is a specific combination:
  - SOC evidence categories beyond an incident log;
  - cross-organisation peer comparison and ranking;
  - a signed, ledger-bound supervisory decision.
- SAT-SA was not compared experimentally with those systems.

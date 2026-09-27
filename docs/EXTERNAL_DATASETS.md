# External Dataset Suitability Analysis

SAT-SA's detectors need **workflow** evidence: when an alert was raised,
acknowledged and closed; which investigation steps, escalations and
dispositions followed. A dataset without those fields cannot test those
detectors, whatever its size or popularity. This analysis was done on
2026-09-27. Status values: **integrated**, **partially integrated**,
**unsuitable**, **blocked**.

## Summary

| Dataset | Status | Why |
| --- | --- | --- |
| UCI-498 Incident management process enriched event log | **integrated (partial external validation)** | Real ticket workflow with lifecycle timestamps, state transitions, reassignments and an organisation-recorded SLA outcome; IT service management, not a SOC |
| Microsoft GUIDE | **unsuitable for workflow detectors; blocked for download** | Real SOC incidents with triage grades, but only alert creation time — no acknowledgement/closure, investigation steps or escalations. Kaggle download needs an authenticated account |
| CIC-IDS2017 | **unsuitable for supervisory questions; blocked for download** | Network flows with attack labels; no cases, steps, escalations or analyst actions. Multi-GB, form-gated download |
| Splunk BOTS (v1–v3) | **unsuitable for supervisory questions; blocked** | Security telemetry distributed as Splunk indexes (requires Splunk to extract); no analyst workflow |

## Candidate detail

### UCI-498 — Incident management process enriched event log

| Aspect | Detail |
| --- | --- |
| Source | Amaral, Fantinato & Peres (2018), UCI Machine Learning Repository, https://doi.org/10.24432/C57S4H |
| Licence | CC BY 4.0 |
| Download | `https://archive.ics.uci.edu/static/public/498/incident+management+process+enriched+event+log.zip`, downloaded 2026-09-27T03:04:04Z; ZIP SHA-256 `6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6`; CSV SHA-256 `fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef` (141,712 events, 24,918 incidents, 36 columns) |
| Temporal fields | `opened_at`, `sys_updated_at` per event, `resolved_at`, `closed_at` (minute resolution, no time zone) |
| Workflow fields | `incident_state` (New, Active, Awaiting *, Resolved, Closed), `sys_mod_count`, `reassignment_count`, `reopen_count`, `assignment_group`, `sys_updated_by` (pseudonymous) |
| Investigation fields | state transitions only; no free-text investigation notes |
| Escalation fields | none explicit; `reassignment_count` increments used as a **proxy** |
| Ground truth | none for supervisory quality. `made_sla` (final value, false = SLA missed; it starts true and flips to false during 9,114 incidents) is an independent operational outcome recorded by the source organisation |
| Mapping | `public_benchmarks/itsm_incident_log/adapter.py` (`uci498-adapter/1`): entity = final assignment group; incident → alert + case; work-state events → investigation steps; reassignments → escalations; closure → disposition `other`; assets not mapped; `made_sla` kept out of every submission |
| Detectors supported | fast closure, acknowledgement without investigation, missing investigation, anomaly (closure time, investigation depth/duration), workflow reconstruction, repeated investigation, peer benchmarking, case similarity, prioritization |
| Detectors not supported | coverage gap / missing monitoring (no assets: `cmdb_ci` known for 54 of 24,918 incidents); disposition-quality checks (codes anonymized); escalation semantics (proxy only) |
| Research questions | EXT-1 feasibility of the unchanged pipeline on real workflow data; EXT-2 detector behaviour on real distributions; EXT-3 association of SAT-SA entity risk/priority with SLA-miss rate vs data-only baselines |
| Limitations | IT service desk, not SOC; one organisation; SLA timeliness is not supervisory execution quality; UTC assumed |
| Provenance | Original file never modified; derived submissions, `labels.json` and `transformation-report.json` written separately; every record `derived_from_source` |

### Microsoft GUIDE

| Aspect | Detail |
| --- | --- |
| Source | Freitas et al., arXiv:2407.09017; Kaggle "Microsoft Security Incident Prediction" |
| Licence | CDLA-Permissive-2.0 (stated in the paper) |
| Data fields | `IncidentId`, `AlertId`, `Timestamp` (alert creation), `DetectorId`, `AlertTitle`, `Category`, `MitreTechniques`, `IncidentGrade` (TP/BP/FP), `ActionGrouped`/`ActionGranular` (remediation), entity/evidence fields, `OrgId` |
| Temporal fields | alert creation only |
| Workflow / investigation / escalation fields | none |
| Ground truth | customer-analyst incident triage grade |
| Supported | alert/incident triage and remediation-action questions; incident volume per organisation |
| Unsupported | every execution-gap, negative-space, closure-time, escalation and investigation detector |
| Status | unsuitable for SAT-SA's workflow research questions; download blocked (authenticated Kaggle account required) |

### CIC-IDS2017

| Aspect | Detail |
| --- | --- |
| Source | Canadian Institute for Cybersecurity, University of New Brunswick |
| Data | CICFlowMeter network flows with attack labels |
| Workflow fields | none |
| Supported | alert ingestion and volume only, through `public_benchmarks/cicids2017` |
| Status | unsuitable for supervisory questions; not downloaded (multi-GB, registration form) |

### Splunk BOTS

| Aspect | Detail |
| --- | --- |
| Source | Splunk Boss of the SOC datasets |
| Data | security telemetry distributed as pre-indexed Splunk data |
| Workflow fields | none |
| Status | unsuitable for supervisory questions; blocked (requires Splunk to export); `scenario_manifest.json` remains a template |

## Evidence categories

| Category | Evidence available |
| --- | --- |
| Controlled synthetic | mechanism, robustness, integrity, orchestration, peer sensitivity, prioritization (EXP-R01b, O01, O02, T01, P01, A01, PR01) |
| External dataset | partial: UCI-498 real IT incident workflow (EXP-X02) |
| Real SOC operational data | **not evaluated** |

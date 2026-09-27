# S7. External dataset and mapping (UCI-498)

**Dataset.** Amaral, Fantinato and Peres (2018), *Incident management process
enriched event log*, UCI Machine Learning Repository dataset 498,
DOI 10.24432/C57S4H, CC BY 4.0. A real ServiceNow IT incident event log of
one organisation — **IT service-desk data, not SOC data**.

**Provenance.** Downloaded 2026-09-27T03:04:04Z from
`https://archive.ics.uci.edu/static/public/498/incident+management+process+enriched+event+log.zip`;
ZIP SHA-256 `6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6`;
CSV SHA-256 `fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef`
(141,712 events, 24,918 incidents, 36 columns). The experiment refuses a file
with a different checksum.

**Adapter.** `public_benchmarks/itsm_incident_log/adapter.py` (`uci498-adapter/1`).
Entity = final assignment group with at least 30 incidents (50 groups,
22,604 incidents). The SLA label is loaded only after SAT-SA's ranking exists
and never enters a submission.

| Source field | SAT-SA field | Transformation | Semantic assumption | Meaning changed? |
| --- | --- | --- | --- | --- |
| `assignment_group` (final event) | entity | group by final resolver group; ≥ 30 incidents | resolver group is the accountable unit | minor: 3 of 7,907 SLA misses occurred while another group held the ticket |
| `opened_at` | alert.created_at, case.opened_at | parse `d/m/Y H:M` as UTC | no zone given | no |
| first non-`New` event `sys_updated_at` | alert.acknowledged_at | derived | first state change = acknowledgement | approximation |
| `resolved_at` | alert.closed_at | copied | resolution = alert closure | no |
| `closed_at` | case.closed_at, status | copied | — | no |
| `Active` / `Awaiting *` events | investigation steps | one step per state event | a state change is an investigation step | **proxy** |
| `reassignment_count` increments | escalations | one escalation per increment | reassignment ≈ escalation | **proxy** (routing, not severity escalation) |
| `closed_code` | disposition outcome `other`, reason | codes anonymised | — | outcome semantics unavailable |
| (none) | step notes | empty string | — | **artifact**: "unavailable" becomes "empty" |
| `cmdb_ci` | not mapped | known for 54 of 24,918 incidents | — | monitoring coverage unavailable |
| `made_sla` (final) | label only | SLA miss = final `false` | flag starts true, flips when breached | no |

Source: `docs/EXTERNAL_FAILURE_ANALYSIS.md` §2 and `docs/EXTERNAL_DATASETS.md`.

**Datasets assessed and not used.** Microsoft GUIDE (real SOC incidents with
triage grades but only alert creation times; download requires an
authenticated Kaggle account) and CIC-IDS2017 (network flows with attack
labels; no cases, steps, escalations or analyst actions). See
`research/dataset-suitability.json`.

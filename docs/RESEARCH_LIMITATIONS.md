# Research Limitations

Each limitation cites the evidence that establishes it. Bundles are in
`research/evidence/freeze-v1/bundles/`; experiment IDs are defined in
[EXPERIMENTS.md](EXPERIMENTS.md).

## Data limitations

- **No real SOC data.** Every SOC-shaped result comes from authored catalog
  fixtures (5 executable scenarios, EXP-C01) or SAT-SA's own generator
  (EXP-PR01, EXP-A01). No NCIIPC/CSE/SOC submission has been analysed.
- **External data is from IT service management, not security operations.**
  EXP-X02 uses a real ServiceNow incident log (UCI-498, one organisation,
  2016–2017). Domain transfer to SOC workflows is untested.
- **Mapping losses on the external data.** Assets could not be mapped
  (`cmdb_ci` known for 54 of 24,918 incidents), so coverage/monitoring
  detectors were not evaluable; escalations are reassignment proxies; closure
  codes are anonymized; 1,556 incidents have no resolution time; 2,157
  incidents with an unknown group were excluded (EXP-X02 transformation
  report).
- **Timestamps without time zone** in UCI-498 are interpreted as UTC.

## Label limitations

- Catalog labels (EXP-C01, EXP-A01) were written by the project, alongside the
  detectors they score.
- Generator labels (EXP-PR01, EXP-A01 population) come from two profiles
  whose pathological settings inject exactly the behaviours SAT-SA's
  detectors target, so separation is likely optimistic.
- The external label (SLA miss) measures timeliness, not supervisory
  execution quality (EXP-X02).
- **No expert labels exist.** The only label file is a template
  (`docs/demo/expert-labels.sample.json`), which the Phase 10 ingestion
  refuses.

## Synthetic-data limitations

- A simple closure-speed heuristic matched SAT-SA's ranking on most generated
  populations (recall@20%: 8 higher, 11 equal, 1 lower; EXP-PR01), and on the
  12-record closure-time corpus fixed-threshold and MAD baselines tie SAT-SA
  exactly (F1 1.0; EXP-C01). Synthetic separability does not establish added
  value over simple rules.
- On real data several detectors saturate: acknowledgement-without-
  investigation, missing-investigation, case-similarity and investigation-
  depth anomaly fire for all 50 groups (EXP-X02). Thresholds tuned on synthetic
  fixtures do not discriminate on this real distribution.

## Deployment limitations

- Container build/startup and the compose topology (PostgreSQL, SeaweedFS,
  migration, API, worker) have **not been executed** locally: Docker is not
  installed. The CI job `saas-topology-smoke` exists but has not run (nothing
  pushed).
- **Live PostgreSQL is untested**: `SATSA_TEST_POSTGRES_DSN` unavailable; 72
  PostgreSQL tests skip.
- **Live S3/SeaweedFS is untested.**
- The only HTTP end-to-end run used separate local API and worker processes
  with SQLite and local storage (EXP-D01, 18/18).
- Hosted deployment of the API/worker is not verified.

## Statistical limitations

- No hypothesis tests or p-values; all intervals are percentile bootstrap
  intervals, uncorrected across many comparisons (EXP-O01, EXP-PR01, EXP-X02).
- Population ablation used 5 seeds and is exploratory (EXP-A01).
- Timing results are repeated measurements on one Windows machine with SQLite;
  some runs overlapped with unrelated processes (EXP-PR01, EXP-A01).
- Five scenarios, one trust workflow and 96 engineered peer cells are
  mechanism observations, not samples of a population.

## External-validity limitations

- SAT-SA's risk score showed no association with the external SLA-miss rate
  (Spearman ρ −0.11, 95% interval −0.42 to +0.21, n = 50 groups), while a
  slowest-median-resolution rule was strongly associated (ρ 0.94) — expected,
  because SLA miss is itself a timeliness outcome (EXP-X02). SAT-SA's
  priority placed the last high-SLA-miss group at the bottom of the ranking
  (review volume 50 of 50).
- One external organisation; no second external dataset was available with
  workflow fields (GUIDE, CIC-IDS2017 and BOTS lack them; see
  [EXTERNAL_DATASETS.md](EXTERNAL_DATASETS.md)).

## Human-evaluation limitations

- No human study has been executed; the protocol is ready
  ([HUMAN_REVIEW_PROTOCOL.md](HUMAN_REVIEW_PROTOCOL.md)). No claim about
  review time, accuracy, agreement or trust can be made.
- No session runner exists; running the study needs interface work outside
  the backend scope.

## Architectural limitations

- **No recency/assessment-period validation:** records shifted 1 or 40 days
  outside the period were accepted with no warning and no output change
  (15/15, EXP-R01b).
- **No cross-record contradiction detection:** contradictory dispositions and a
  closed case with an open alert were accepted silently (EXP-R01b).
- Hosted validation is all-or-nothing: one orphaned investigation step rejects
  the whole submission (3/25–14/25 omission replicates rejected, EXP-R01b).
- Peer findings depend strongly on cohort size and spread; below 3 peers the
  worker abstains, wide cohorts flag only extremes (EXP-P01).
- Hosted peer baselines abstain by design until a governed cross-tenant
  aggregate exists; peer evidence comes from the legacy path.

## Security limitations

- The mutation matrix covers one workflow and 13 single-field mutations; it is
  not a detection rate and does not cover coordinated replacement of database,
  key and ledger (EXP-T01).
- Signing keys and ledger are local files; there is no external trust anchor
  or HSM in the evaluated configuration.
- Verification proves integrity of recorded state, not truth of submitted
  evidence.

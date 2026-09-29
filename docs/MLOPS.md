# SAT-SA MLOps lifecycle (Phase 21)

This is product documentation for the hosted system. It does not change any
research claim; the frozen paper and its evidence are unaffected.

## What the model is, and what it is not

SAT-SA's analytical workers are deterministic by design (documented risk
weights, median/MAD anomaly statistics, edit-distance case similarity,
delta-based drift). They are unchanged. Phase 21 adds **one** model where
learning has a justified function:

**Review-outcome model.** For a completed analysis run it estimates the
probability that a supervisor will *confirm or escalate* the run rather than
*dismiss* it. The labels are the organization's own recorded supervisory
decisions, the one labelled signal the product generates. The score is
**advisory**: it orders the review queue. It never changes findings, risk,
recommendations or the decision, and a human supervisor makes every decision.

Candidates considered and not chosen:

| Candidate | Why not in this phase |
|---|---|
| Replace anomaly / peer / drift workers with learned models | They are explainable, deterministic and part of the frozen research claims; a learned replacement would remove examiner-verifiable reasoning |
| Unsupervised anomaly model (e.g. isolation forest) | Duplicates the deterministic anomaly worker and has no ground truth to evaluate against |
| Finding-level classifier | The hosted review decision is run-level; there are no finding-level labels |

## Architecture

```
satsa/mlops/
  policy.py      versioned governance thresholds (satsa-ml-governance/1)
  features.py    feature pipeline review-outcome-features/1 (single implementation)
  datasets.py    immutable dataset snapshots + validation
  training.py    logistic regression training + holdout evaluation
  artifact.py    data-only JSON model artifact (no pickle)
  registry.py    passport, states, approval, deployment, rollback, retirement
  inference.py   advisory scoring with explicit abstention
  monitoring.py  monitoring, PSI drift, retraining triggers
  jobs.py        worker queue for validation / training / drift
  service.py     tenant-scoped, permission-checked operations for the API
satsa/api/ml_routes.py   24 routes (below)
qsmlops/database/migrations.py   migration 17 (satsa_ml_* tables)
```

Reused from the existing platform rather than rebuilt: the tenancy and
permission model (`model.read/train/approve/deploy/rollback` already existed in
`qsmlops/security/permissions`), the audit log, the artifact storage
abstraction (local volume or S3), the worker process, the migration runner,
PSI from `qsmlops.ml.drift`, the SHA3-256 canonical digests, and the state
vocabulary of the retained QSMLOps registry (registered, verified, quarantined,
approved). The retained QSMLOps registry itself is not used by the hosted
product: it keeps its own SQLite file and keystore and has no tenant scope.

Responsibilities are separated:

* MLOps lifecycle (validation, training, drift): background jobs in the worker.
* Supervisory analysis: LangGraph (`model_inference` node between
  `recommendations` and `human_review`), or the standard path before review.
* Inference: one analytical capability consumed by the supervisory workflow.

## Lifecycle

```
dataset -> validation -> features -> training -> evaluation -> passport
  -> registration (+ verification gate) -> approval -> deployment
  -> inference -> monitoring -> drift -> retraining decision -> rollback
```

Every stage is executable and tested end to end
(`tests/test_phase21_mlops_lifecycle.py`).

### Dataset registry

`POST /api/v1/ml/datasets` snapshots every run of the organization that has a
recorded supervisory decision and a persisted risk profile into canonical JSON
(`run_id`, `decision_id`, feature vector, label). The SHA3-256 of the snapshot
is its identity. Identical content returns the existing version (200); new
content becomes the next version (201). Content columns are never updated.

The creator declares the **data origin**: `organizational`, `synthetic`,
`controlled` or `external`. It is stored, attributed, shown in the workbench,
and copied into every passport, so synthetic decisions are never presented as
real supervisory labels. The workbench always declares `organizational`
because it builds from the organization's own decisions; tests and demos that
generate decisions declare `synthetic`.

Lineage records the source table, the number of decisions considered, runs
skipped for lack of features, and a digest of the decision ids.

### Validation

A worker job (`POST .../datasets/{id}/validate`, 202). States: `created ->
validating -> valid | invalid` (`archived` is reserved for retention). Checks,
all persisted with their details: integrity (stored bytes match the digest),
schema, types, missingness, duplicate runs, invalid values, label
availability, minimum rows, class balance, and train/evaluation compatibility
(the deterministic holdout must contain both classes). Training refuses any
dataset that is not `valid`.

### Features

`review-outcome-features/1`, 11 numeric features derived from results the
deterministic workers already persisted: the risk total, the seven documented
risk-dimension scores, the signal count, the insufficient-data count and mean
signal confidence. One function (`run_features`) serves training snapshots and
inference, so there is no train/serve skew. A run without a risk profile has no
features (nothing is imputed from other runs). Models record the feature
version and refuse vectors from another version.

### Training and evaluation

A worker job (`POST /api/v1/ml/training-runs`, 202). L2-regularized logistic
regression (scikit-learn, lbfgs, `class_weight=balanced`) on standardized
features. Hyperparameters are whitelisted and bounded. The holdout split is
deterministic and stratified: SHA3(seed, run id) orders each class and 25%
is held out. With the same dataset, seed, hyperparameters and library versions
the artifact is byte-identical; the passport records Python, numpy and
scikit-learn versions because bit-identical results across versions are not
guaranteed.

Evaluation scores the holdout with the same function inference uses: ROC-AUC,
PR-AUC, Brier score, precision/recall/F1 at 0.5, confusion matrix and a
calibration table. If the holdout lacks rows or a class, supervised metrics are
reported `unavailable`.

### Passport and registration

On success the worker stores the artifact (content-addressed), re-reads and
verifies it, and seals the passport: model id and version, organization,
training run, dataset (id, version, digest, origin, counts), training
population, feature version and definitions, algorithm, hyperparameters, seed,
environment, artifact digest and format, evaluation, verification result,
intended use, known limitations, creation time. The passport JSON and its
SHA3-256 are written once and never updated. Approval and deployment are
recorded as events and deployment rows and composed with the passport for
display; the passport carries no mutable status field.

Registration immediately applies the verification gate
(`satsa-ml-governance/1`): holdout ROC-AUC >= 0.60 and Brier <= 0.25, with
supervised metrics available. Passing models become `verified`, others
`quarantined` (never approvable). A retried training job reuses its
deterministic ids and never registers a second model.

### States

```
registered -> verified -> approved -> retired
           -> quarantined ----------> retired
              verified -------------> retired
```

Deployment is not a model state: the active model is the single
`satsa_ml_deployments` row with `active=1` (a unique partial index enforces
one per organization). History is every earlier row.

### Approval

`POST .../models/{id}/approve` requires `model.approve` (supervisor, admin), a
justification, and the model in `verified`. The user who requested the
training may not approve its model (separation of duties; applies to admins
too). Approval is an event plus an audit record.

### Deployment

`POST .../models/{id}/deploy` requires `model.deploy` and an `approved` model.
Before activation the stored artifact is read, its SHA3-256 compared with the
registry record, the passport digest and the passport's artifact digest
checked, and the JSON schema validated. Any failure refuses the deployment.
Activation and deactivation of the previous row happen in one transaction; a
concurrent deployment loses on the unique index and receives 409.

### Inference and abstention

The worker scores each supervised run once (idempotent) before human review.
The record holds run id, model id, deployment id, artifact digest, feature
version, features, status, score or abstention reason, latency and a content
digest. Abstention reasons: `no_deployed_model`, `model_unavailable`,
`feature_version_mismatch`, `missing_features`, `out_of_distribution` (any
standardized feature beyond 4 standard deviations of training), `low_confidence`
(probability within 0.05 of 0.5), `inference_error`. An inference failure never
fails the run.

### Provenance and TRUST-SAT

TRUST-SAT is unchanged. When a run has an inference record, the supervisory
canonical document that the decision freezes and the finalization signs gains a
`model_inference` block: record id, model id, deployment id, artifact digest,
feature version, status, abstention reason, score and the record's content
digest. The record digest is recomputed from its fields at verification, so an
altered score or model identity makes verification report `inconsistent`.
Runs without an inference record produce exactly the document they did before
Phase 21. The provenance therefore distinguishes deterministic findings (worker
rows), the ML-derived advisory score (the inference block, with model identity)
and the human decision (the decision block).

### Monitoring

`GET /api/v1/ml/monitoring`, computed from inference records only:
`no_deployed_model`, `no_observations` or `observed` with inference volume,
scored/abstained counts, abstentions by reason, missing-feature rate, score and
latency quantiles, and realized performance: ROC-AUC of scores against
supervisory decisions recorded later, reported only with at least 20 labelled
inferences of both classes (otherwise `insufficient_labels`).

### Drift

A worker job (`POST /api/v1/ml/drift-checks`, 202). Baseline: the deployed
model's scores over its own training dataset (recomputed from the stored
snapshot and artifact). Current: up to the last 500 scored inferences. Metric:
PSI over the score distribution (10 bins, threshold 0.20), plus per-feature PSI
for diagnosis. With fewer than 30 observations in either window the result is
`insufficient_data`. Each report records windows, sample sizes, metric,
threshold, result, policy version and model.

### Retraining decision

Separate, separately recorded states: drift detected (report) -> retraining
recommended (open request) -> retraining started (a supervisor accepts, a
training job starts) -> model registered/verified -> approved -> deployed.
Requests open automatically after two consecutive `drift` reports or when
realized ROC-AUC falls below 0.55; analysts can open one manually. At most one
open request per trigger. Nothing retrains or deploys automatically.

### Rollback

`POST /api/v1/ml/rollback` requires `model.rollback`. Without a target it
restores the most recent previously deployed model that is still `approved`;
with one, the target must exist in the organization and be `approved`. It
inserts a new deployment row (`kind=rollback`), deactivates the current one,
and changes no model's state: the newer model stays approved and its history
is kept.

## Tenancy

Every MLOps object is organization-scoped (`organization_id` on every table,
every query filtered by it). There are no global or shared models. Another
organization's dataset, training run, job, model, inference or report resolves
as not found; its models cannot be approved, deployed, retired or rolled back
to.

## Authorization

| Operation | viewer | analyst | supervisor | auditor | admin |
|---|---|---|---|---|---|
| Read datasets, runs, jobs, models, deployments, monitoring, drift, requests, run inference | yes | yes | yes | yes | yes |
| Build/validate datasets, start training, cancel jobs, start drift checks, request retraining | | yes | yes | | yes |
| Approve, deploy, retire, roll back, accept/dismiss retraining | | | yes | | yes |

Enforced server-side in `satsa/mlops/service.py`; the workbench only hides
controls.

## Model artifact security

* Production artifacts are JSON (`satsa-logistic-regression/1`): arrays of
  numbers and feature names. Loading is `json.loads` plus schema validation;
  no artifact can execute code.
* Artifacts are only produced by the training job and addressed by their
  SHA3-256. There is no upload route for model artifacts.
* Every load verifies the digest against the registry record, and the passport
  digest, before use. A missing or altered artifact blocks deployment and makes
  inference abstain (`model_unavailable`).
* The worker caches a verified model by digest; a digest names immutable
  content, so the cache cannot serve different bytes.
* Retained QSMLOps modules still contain `pickle.loads` and `torch.load` for
  their standalone registry. Those loaders now refuse any bytes not matching an
  expected SHA3-256 digest from a trusted source (`verified_artifact_bytes`),
  and `torch.load` uses `weights_only=True`. They are not reachable from the
  hosted API.

## Jobs and worker behaviour

Jobs follow the analysis queue's rules: leased claim with a generation number,
reclaim after lease expiry, `lease_exhausted` failure after the maximum
attempts (3), backoff retries for transient errors, immediate failure for
validation errors, cancellation of queued jobs immediately and of running jobs
at the next boundary before results commit. A job that dies mid-training never
leaves a training run `running` or a dataset `validating`.

## Offline SQLite

The full lifecycle runs on SQLite with local artifact storage (all Phase 21
tests run on SQLite and PostgreSQL). The five-CSE offline demo is unaffected:
offline runs are not supervised through the hosted worker and produce no
inference records.

## Observability

Logs carry `ml_job_id`, `kind`, `organization_id`, `run_id`, `model_id`,
inference `status` and `abstain_reason`. They carry no features, credentials or
artifact bytes.

## Limitations (not claimed)

* No continuous or autonomous learning; no automatic retraining or promotion.
* One model; not multi-model orchestration. Scores are computed when a run is
  analysed, not in real time.
* The model reproduces the organization's past supervisory decisions,
  including their biases. It says nothing about whether a finding is correct.
* A new organization has no decisions; its first dataset validates `invalid`
  until at least 30 decided runs with both outcomes exist.
* Tests and demos use synthetic decisions and say so; no real SOC performance
  is claimed.
* Realized-performance monitoring needs decisions recorded after scoring and is
  reported only above the policy minimum.
* No explainability claim beyond the passport's feature definitions and the
  linear model's coefficients.

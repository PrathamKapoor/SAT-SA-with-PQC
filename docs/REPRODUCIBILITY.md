# SAT-SA Evaluation Reproducibility

## Run a controlled experiment

From the repository root, with the existing project dependencies installed:

```powershell
python scripts/run_controlled_benchmark.py --out C:\sat-sa-results --seed 42 --population 10 --pathological 4 --random-trials 200 --experiment-id pilot-seed-42
```

The command executes the existing controlled benchmark against an isolated
scratch SQLite database and local scratch keys. It writes the legacy
`controlled-benchmark-results.json` for compatibility and an immutable
directory under `C:\sat-sa-results\experiments\pilot-seed-42\` containing:

```text
manifest.json
config.json
raw/results.json
processed/metrics.json
processed/metrics.csv
summary.md
```

Do not reuse an experiment ID: the artifact writer refuses to overwrite an
existing bundle. Choose a new ID for a rerun. The default ID contains a UTC
timestamp and workload seed. `--no-ablation` skips the ablation experiment;
`--random-trials` controls the random-order comparison. Use a small population
for a smoke run and record that it is only a smoke run.

Run the controlled TRUST-SAT mutation protocol separately:

```powershell
python scripts/run_trust_integrity_experiment.py --out C:\sat-sa-results\trust --experiment-id trust-pilot-001
```

It creates a temporary isolated SQLite database, ingests a small synthetic
submission, executes the existing worker, records an authorized supervisor
decision, finalizes and verifies TRUST-SAT, and performs reversible single
mutations. It writes the same immutable bundle shape; scratch DB, artifact,
key, and ledger files are removed after execution.

Run the peer-cohort sensitivity experiment:

```powershell
python scripts/run_peer_sensitivity_experiment.py --out C:\sat-sa-results\peers --experiment-id peer-pilot-001
```

This compares the actual peer worker on synthetic cohorts with 2/3/4 peers and
subject closure times of 30/400/750 seconds. Each cohort is isolated by
explicit sector/environment labels in a temporary local database. It is not a
production cross-tenant query.

## Manifest and hashes

The manifest records experiment status, UTC creation time, controlled dataset
identity/version/origin, ground-truth source, a canonical descriptor digest,
seed, canonical configuration digest, Git commit/branch/dirty flag, runtime
platform, relevant installed package versions, and SHA-256 values for bundle
artifacts. Raw scenario output also carries hashes of generated CSV inputs.
SHA-256 here identifies research files/configurations; it is distinct from
TRUST-SAT's SHA3-256 canonical evidence digest and does not change its domain
semantics.

The dirty flag is important: an artifact created from modified code is
reproducible only when those exact changes are also preserved. Archive the
source diff or commit the experiment code before treating results as a
reproducible paper artifact. Hashes detect changes; they do not guarantee
dataset availability or scientific validity.

## Status and failure handling

Completed bundles contain result/metric exports and `measurement_status` is
`measured`. Failed, cancelled, or partial bundles contain their configuration,
environment and failure reason, but no successful metrics export. Do not cite
non-completed runs as measured outcomes. The manifest and outputs are
write-once by experiment ID; retain the complete directory as an immutable
run record.

## Reproduction protocol

1. Check out the exact recorded commit and preserve any dirty-code patch.
2. Install the same Python version and dependencies; the manifest records
   Python and key package versions. The repository lock/dependency definition
   remains the environment source of truth.
3. Run the recorded command/configuration and seed with a new output ID.
4. Compare canonical metrics JSON and input/config hashes. Timestamps, host
   details and cryptographic signatures/keys may differ; bit-for-bit artifact
   identity is not promised.
5. Confirm synthetic provenance and limitations before citing values.

## Data separation

Production data is accessed through the SaaS API and is not an evaluation
input. Research evaluation creates a temporary local database and generated
fixtures. Demo input files are separately marked synthetic and are not
automatically loaded into production. Never place production artifacts or
credentials beneath the research output root.

## Current limits

The current executable benchmark is synthetic/controlled. Actual CIC-IDS2017
and BOTS files, external expert labels, a human-review study, PostgreSQL/S3
service-boundary performance, and hosted deployment are not part of an
executed Phase 8 run. The benchmark has no independent random-seed replication
or inferential statistical analysis; do not report statistical significance.

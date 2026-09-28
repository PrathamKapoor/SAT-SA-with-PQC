# SAT-SA single-host failure model

Deployment: `deploy/compose.production.yml` on one Linux VM (Caddy, web, API,
worker, PostgreSQL, optional bundled object storage, one durable volume for
the ledger and signing key). This lists what fails, what users see, what is
lost, and how service returns. "Tested" names where the behaviour is
exercised; the rest follows from the design and is stated as such.

## Component failures

| Failure | Effect | Data loss | Recovery | Tested |
|---|---|---|---|---|
| Worker stopped or killed | runs stay `queued`; a running stage stops; the UI shows the run waiting | none: a killed worker's lease expires and the run is resumed from the last completed stage | `restart: unless-stopped`; `$COMPOSE up -d --scale worker=2` for capacity | CI: worker stopped mid-smoke, restarted, run completes; `test_queue_claim_and_lease_recovery_are_fenced`, `test_expired_lease_exhaustion_becomes_durable_failure` |
| Worker crashes during TRUST-SAT finalization | run stays short of `completed`; verify says `not_finalized` | none: finalization resumes at its last durable boundary (prepared, signed, recorded, ledger appended, verified) with the same receipt | next claim of the run | `test_finalization_recovers_at_durable_boundaries` (every boundary), `test_cancellation_during_finalization_does_not_claim_trusted_completion` |
| Signing key missing or invalid | supervised runs never complete; readiness fails | none | restore the durable volume (the key must match existing receipts; never generate a new one for old data) | `test_missing_signing_key_never_completes_a_supervised_run`, `test_provisioned_trust_key_self_test_rejects_mismatched_keypair` |
| API restarted | in-flight requests fail; sessions survive (server-side, in PostgreSQL) | none | automatic | CI: `API restart keeps sessions and serves the site` |
| Web tier restarted | pages unavailable for seconds; sessions survive (cookie + backend) | none | automatic | design |
| Caddy down | site unreachable | none | automatic restart; certificates persist in `caddy_data` | design |
| PostgreSQL unavailable | API readiness 503, requests return a generic service error with a request ID; the worker process exits on its next queue claim and Docker restarts it until the database returns | none for committed work; the request in flight is rolled back | automatic once PostgreSQL is back; leases recover interrupted runs | readiness test `test_readiness_requires_database_migration_and_storage`; restart behaviour by design |
| PostgreSQL rejects a write mid-transaction | that operation fails as a whole (transactions around decisions, uploads, validation, finalization) | none | retry the operation; idempotency keys return the original object | `test_phase20_concurrency.py`, upload/validation tests |
| Validation interrupted (process lost, unexpected error) | the version returns to `uploaded`, not stranded in `validating` | none | call validate again | `test_interrupted_validation_does_not_strand_the_version` (fixed in Phase 20) |
| Object storage unavailable or wrong digest | uploads fail with a storage error; validation reports `failed` with a generic reason; readiness fails | none: an upload is recorded as `uploading` before the write and completed after it; a retry with the same key resumes | retry after storage returns | `test_upload_retry_and_invalid_file`, storage tests in `test_phase2_artifact_storage.py` |
| Cancel requested during execution | the worker stops at the next stage boundary; a run is never finalized after a cancel | none | none needed | `test_running_worker_observes_supervisor_cancellation_at_boundary`, `test_cancel_during_a_decision_waits_and_is_not_lost` |
| Retry budget exhausted | run `failed` with a sanitized error code | partial results stay unfinalized | a new run on the same version | `test_retryable_failure_retries_then_exhausts_without_duplicate_stages` |
| Disk full | PostgreSQL and ledger writes fail; the ledger append and finalization are resumable | none committed is lost; the failing operation is refused | free space, restart | design |

## Host-level failures

| Failure | Effect | Recovery point | Recovery |
|---|---|---|---|
| VM reboot | services restart (`unless-stopped`); leases recover runs | no loss | automatic |
| Disk or VM lost | total outage | last `deploy/backup.sh` run | new host, `deploy/restore.sh`, `$COMPOSE up -d`, `deploy/smoke.sh`; CI proves the restored runs still verify |
| Durable volume lost, database intact | finalized runs report `inconsistent` (receipts cannot be bound to the ledger) and no new supervised run completes | ledger and key since the last backup | restore the durable volume from the same backup set as the database |
| Database restored from an older backup than the durable volume | ledger has entries the database lacks; old runs verify, newer finalizations are absent | older of the two | always restore a whole backup set (the scripts only produce whole sets) |
| Signing key disclosed | an attacker with the ledger could forge new receipts | n/a | rotate: stop, archive the old key with the backup (old receipts stay verifiable), provision a new key, record the rotation; review `KEY_MANAGEMENT.md` |

## Not provided by a single host

High availability, zero-downtime updates, off-site replication and
point-in-time recovery. Recovery point equals the backup interval (schedule
`deploy/backup.sh`, for example daily, and copy the encrypted set off the
host); recovery time is a restore plus start, minutes for typical volumes.
Managed PostgreSQL and object storage with their own replication are the
step up when that is not enough.

# SAT-SA backup / restore

This procedure is proven, not just described: it is exactly what
`tests/test_phase68_satsa_doctor_and_backup_restore.py::test_backup_restore_preserves_full_trust_chain`
performs and asserts. If this doc and that test ever diverge, trust
the test and fix this file.

## What to back up

Two things, together — one without the other is not a valid backup:

1. **The SQLite database file** (`--db`, e.g. `./satsa.db`). Holds
   every entity, assessment, submission, finding, risk computation,
   review decision, and trust receipt.
2. **The trust key directory** (`--trust-key-dir`, e.g. `./keys`).
   Holds `satsa_trust_key.json` — the ML-DSA keypair every receipt in
   the database is signed against. A database backup without its
   matching key directory cannot be verified after restore (the
   `TrustService` would generate a *new* keypair on demand, which
   cannot verify old signatures).

## Procedure

```bash
# 1. Backup (the platform must not be actively writing during copy —
#    SQLite is single-writer; stop the CLI/UI process first, or use a
#    filesystem-consistent snapshot if the platform never stops)
mkdir -p ./backup
cp ./satsa.db ./backup/satsa.db
cp -r ./keys ./backup/keys

# 2. Restore (to the same location, or a fresh machine)
cp ./backup/satsa.db ./satsa.db
cp -r ./backup/keys ./keys

# 3. Verify the restore actually preserved the trust chain — do not
#    assume; check:
sat-sa --db ./satsa.db --trust-key-dir ./keys doctor
sat-sa --db ./satsa.db --trust-key-dir ./keys verify <run_id>
```

`sat-sa doctor` (added this phase) confirms the restored database
connects, has the expected `satsa_*` tables, and that the restored
keystore can still perform a live ML-DSA sign+verify roundtrip.
`sat-sa verify <run_id>` re-derives each finding's digest from the
*restored* row and checks it against the *restored* receipt — proving
the restore preserved both sides of the signed relationship, not just
that files of the right name exist.

## What this does NOT protect against

Per `docs/TRUST_MODEL.md`'s tampering matrix: a backup taken *after*
an undetected tamper faithfully preserves that tamper — backup/restore
is not a substitute for `sat-sa verify` run regularly. Restoring an
*older* backup over a *newer*, legitimate database silently discards
real work; there is no confirmation prompt in the copy commands above
because this is a filesystem operation, not a SAT-SA feature — treat
it with the same care as any other destructive file copy.

## Upgrade / rollback

SAT-SA's SQLite schema is migrated by
`qsmlops.database.migrations.MigrationRunner`, which is idempotent and
additive (`CREATE TABLE IF NOT EXISTS`, versioned migration rows) —
running a newer `sat-sa` binary against an older database applies any
pending migrations automatically on first connect. There is currently
no automated *downgrade* path: rolling back to an older `sat-sa`
binary against a database a newer version has already migrated is
unsupported and untested. If a rollback is needed, restore the
pre-upgrade backup (see above) rather than attempting to run an older
binary against an already-migrated database.

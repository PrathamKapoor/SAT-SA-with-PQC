#!/usr/bin/env bash
# Consistent backup of a SAT-SA single-host deployment.
#
#   COMPOSE="docker compose -f deploy/compose.production.yml [-f deploy/compose.objectstore.yml] \
#            --env-file deploy/production.env" deploy/backup.sh /secure/backups
#
# Writes <dir>/satsa-<UTC timestamp>/ containing:
#   database.dump   PostgreSQL custom-format dump (pg_restore)
#   durable.tar.gz  TRUST-SAT ledger, identity audit ledger and the SIGNING KEY
#   objects.tar.gz  bundled object storage (only with compose.objectstore.yml)
#   SHA3-256SUMS    digests of the three files
#
# The API and worker are stopped for the duration (typically under a minute)
# so the database, the append-only ledgers and stored evidence are captured at
# one point in time: a finalization row must never reference a ledger entry
# the backup lacks. The web tier stays up and shows the service as
# unavailable. The backup contains the TRUST-SAT private signing key and all
# tenants' evidence: store it encrypted, access-controlled and off this host.
set -euo pipefail

: "${COMPOSE:?set COMPOSE to the docker compose command used to run the stack}"
destination="${1:?usage: deploy/backup.sh <backup directory>}"
project="${SATSA_PROJECT:-satsa}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${destination%/}/satsa-${stamp}"
umask 077
mkdir -p "$out"

bundled=false
if $COMPOSE config --services | grep -qx objectstore; then bundled=true; fi

restart() { $COMPOSE start api worker >/dev/null 2>&1 || true; }
trap restart EXIT

echo "stopping api and worker for a consistent snapshot"
$COMPOSE stop api worker

echo "dumping PostgreSQL"
$COMPOSE exec -T database pg_dump -U satsa -d satsa --format=custom --no-owner \
  > "$out/database.dump"

volume_tar() {  # volume name, archive path
  docker run --rm --network none -v "$1:/volume:ro" -v "$(cd "$(dirname "$2")" && pwd):/backup" \
    alpine:3 tar -C /volume -czf "/backup/$(basename "$2")" .
}

echo "archiving the durable volume (ledgers, signing key)"
volume_tar "${project}_satsa_durable" "$out/durable.tar.gz"
if $bundled; then
  echo "archiving bundled object storage"
  $COMPOSE stop objectstore
  volume_tar "${project}_object_data" "$out/objects.tar.gz"
  $COMPOSE start objectstore
fi

restart
trap - EXIT

( cd "$out" && for f in database.dump durable.tar.gz objects.tar.gz; do
    [ -f "$f" ] && printf '%s  %s\n' "$(openssl dgst -sha3-256 -r "$f" | cut -d' ' -f1)" "$f"
  done > SHA3-256SUMS )
echo "backup written to $out"
cat "$out/SHA3-256SUMS"

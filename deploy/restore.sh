#!/usr/bin/env bash
# Restore a backup made by deploy/backup.sh onto a host with NO running stack
# and NO existing SAT-SA volumes (a rebuilt host, or after `down -v`).
#
#   COMPOSE="docker compose -f deploy/compose.production.yml [-f deploy/compose.objectstore.yml] \
#            --env-file deploy/production.env" deploy/restore.sh /secure/backups/satsa-<stamp>
#
# Then start the stack as usual (`$COMPOSE up -d`) and run deploy/smoke.sh.
# The migrate service brings an older database forward; key-init finds the
# restored signing key and does not generate a new one.
set -euo pipefail

: "${COMPOSE:?set COMPOSE to the docker compose command used to run the stack}"
source_dir="$(cd "${1:?usage: deploy/restore.sh <backup directory>}" && pwd)"
project="${SATSA_PROJECT:-satsa}"

( cd "$source_dir" && while read -r digest file; do
    actual="$(openssl dgst -sha3-256 -r "$file" | cut -d' ' -f1)"
    [ "$actual" = "$digest" ] || { echo "digest mismatch: $file" >&2; exit 1; }
  done < SHA3-256SUMS )
echo "backup digests verified"

if [ -n "$($COMPOSE ps -q 2>/dev/null)" ]; then
  echo "the stack is running; stop it first (restore never overwrites live data)" >&2
  exit 1
fi
for volume in postgres_data satsa_durable object_data; do
  if docker volume inspect "${project}_${volume}" >/dev/null 2>&1; then
    echo "volume ${project}_${volume} exists; restore only onto empty volumes" >&2
    exit 1
  fi
done

volume_untar() {  # volume name, archive path
  docker volume create --label "com.docker.compose.project=${project}" \
    --label "com.docker.compose.volume=${1#"${project}"_}" "$1" >/dev/null
  docker run --rm --network none -v "$1:/volume" -v "$(dirname "$2"):/backup:ro" \
    alpine:3 tar -C /volume -xzf "/backup/$(basename "$2")"
}

echo "restoring the durable volume (ledgers, signing key)"
volume_untar "${project}_satsa_durable" "$source_dir/durable.tar.gz"
if [ -f "$source_dir/objects.tar.gz" ]; then
  echo "restoring bundled object storage"
  volume_untar "${project}_object_data" "$source_dir/objects.tar.gz"
fi

echo "restoring PostgreSQL"
$COMPOSE up -d database
for attempt in $(seq 1 60); do
  # TCP: the image's first-start initialisation server listens on a socket only.
  if $COMPOSE exec -T database pg_isready -h 127.0.0.1 -U satsa -d satsa >/dev/null 2>&1; then break; fi
  sleep 2
done
$COMPOSE exec -T database pg_restore -U satsa -d satsa --no-owner --exit-on-error \
  < "$source_dir/database.dump"
echo "restore complete; start the stack with: \$COMPOSE up -d"

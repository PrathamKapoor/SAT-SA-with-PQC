#!/usr/bin/env bash
# SAT-SA deployment on the EC2 instance (run as root, normally through SSM:
# deploy/aws/publish.sh sends it). No step is best effort: any failed check
# stops the deployment with a non-zero exit.
#
#   deploy.sh deploy <git-commit>   deploy the release published for that commit
#   deploy.sh bootstrap-admin       create the first organization and administrator
#                                   (once; the credential goes to Secrets Manager)
#   deploy.sh snapshot              coordinated RDS + EBS snapshot with writes stopped
#   deploy.sh status                deployed version and service health
#   deploy.sh public-e2e            browser end-to-end against the public URL
set -euo pipefail
umask 077

STACK_ENV=/etc/satsa/stack.env
RUNTIME_ENV=/etc/satsa/production.env
DEPLOYED=/etc/satsa/deployed.json
RELEASES=/opt/satsa/releases
CURRENT=/opt/satsa/current

die() { echo "deploy: FAILED: $*" >&2; exit 1; }
log() { echo "deploy: $*"; }

[ "$(id -u)" = 0 ] || die "run as root"
[ -r "$STACK_ENV" ] || die "$STACK_ENV missing (instance bootstrap has not completed)"
# shellcheck disable=SC1090
set -a; . "$STACK_ENV"; set +a
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

compose() {
  docker compose -p satsa -f "$CURRENT/deploy/compose.production.yml" \
    -f "$CURRENT/deploy/aws/compose.aws.yml" --env-file "$RUNTIME_ENV" "$@"
}

# ------------------------------------------------------------------ /data
prepare_data() {
  if ! mountpoint -q /data; then
    local id=${SATSA_DATA_VOLUME_ID//-/} dev=""
    for _ in $(seq 1 60); do
      dev=$(readlink -f "/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${id}" 2>/dev/null || true)
      [ -b "$dev" ] && break
      [ -b /dev/xvdf ] && dev=/dev/xvdf && break
      sleep 2
    done
    [ -b "$dev" ] || die "data volume $SATSA_DATA_VOLUME_ID is not attached"
    if ! blkid "$dev" >/dev/null 2>&1; then
      log "formatting new data volume $dev"
      mkfs.xfs -q -L satsa-data "$dev"
    fi
    mkdir -p /data
    local uuid; uuid=$(blkid -s UUID -o value "$dev")
    grep -q "$uuid" /etc/fstab || echo "UUID=$uuid /data xfs defaults,nofail 0 2" >> /etc/fstab
    mount /data
  fi
  mountpoint -q /data || die "/data is not a mounted volume"
  # The backend runs as UID 10001; only it can read the ledger and signing key.
  install -d -m 700 -o 10001 -g 10001 /data/satsa /data/satsa/keys
}

# --------------------------------------------------------------- settings
render_env() {
  local tag=$1 secret user password
  secret=$(aws secretsmanager get-secret-value --secret-id "$SATSA_DB_SECRET_ARN" \
    --query SecretString --output text) || die "database secret unavailable"
  user=$(jq -r .username <<<"$secret"); password=$(jq -r .password <<<"$secret")
  [ -n "$user" ] && [ "$password" != null ] && [ -n "$password" ] || die "database secret incomplete"
  local encoded
  encoded=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$password")
  [ -r /etc/satsa/rds-ca.pem ] || die "RDS CA bundle /etc/satsa/rds-ca.pem missing"
  cat > "$RUNTIME_ENV.new" <<EOF
SATSA_SITE_ADDRESS=$SATSA_SITE_ADDRESS
SATSA_DATABASE_URL=postgresql://$user:$encoded@$SATSA_DB_HOST:$SATSA_DB_PORT/$SATSA_DB_NAME?sslmode=verify-full&sslrootcert=/etc/satsa/rds-ca.pem
SATSA_S3_BUCKET=$SATSA_S3_BUCKET
SATSA_S3_REGION=$SATSA_S3_REGION
SATSA_S3_PREFIX=$SATSA_S3_PREFIX
SATSA_BACKEND_IMAGE=$SATSA_BACKEND_IMAGE
SATSA_WEB_IMAGE=$SATSA_WEB_IMAGE
SATSA_IMAGE_TAG=$tag
SATSA_LOG_GROUP=$SATSA_LOG_GROUP
EOF
  chmod 600 "$RUNTIME_ENV.new"
  mv "$RUNTIME_ENV.new" "$RUNTIME_ENV"
}

# Model-provider configuration for the worker: the secret is a JSON object of
# environment variables (SATSA_LLM_CHAIN plus the key variables it names). No
# secret configured = model assistance off (deterministic briefings).
render_llm_env() {
  local out=/etc/satsa/llm.env.new value
  : > "$out"; chmod 600 "$out"
  if value=$(aws secretsmanager get-secret-value --secret-id "${SATSA_LLM_SECRET_ID:-satsa/$SATSA_ENV_NAME/llm-providers}"       --query SecretString --output text 2>/dev/null); then
    jq -e 'type == "object" and all(.[]; type == "string")' <<<"$value" >/dev/null       || die "model provider secret must be a JSON object of string values"
    jq -r 'to_entries[] | "\(.key)=\(.value)"' <<<"$value" > "$out"
    grep -q '^SATSA_LLM_CHAIN=' "$out" || die "model provider secret has no SATSA_LLM_CHAIN"
    log "model providers configured ($(jq -r '.SATSA_LLM_CHAIN | fromjson | map(.name) | join(" -> ")' <<<"$value"))"
  else
    log "no model provider secret: briefings will be deterministic"
  fi
  mv "$out" /etc/satsa/llm.env
}

wait_healthy() {
  local service
  for service in api worker web; do
    for attempt in $(seq 1 60); do
      state=$(docker inspect -f '{{.State.Health.Status}}' "$(compose ps -q "$service")" 2>/dev/null || echo missing)
      [ "$state" = healthy ] && break
      [ "$attempt" = 60 ] && { compose logs --tail 50 "$service" >&2 || true; die "$service is $state"; }
      sleep 5
    done
    log "$service healthy"
  done
  for attempt in $(seq 1 60); do
    if curl -fsS -o /dev/null --max-time 10 "https://$SATSA_SITE_ADDRESS/login"; then
      log "https://$SATSA_SITE_ADDRESS serves the workbench"
      return 0
    fi
    sleep 5
  done
  die "https://$SATSA_SITE_ADDRESS is not reachable with a valid certificate"
}

# ----------------------------------------------------------------- deploy
cmd_deploy() {
  local commit=${1:-}
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "deploy needs the full 40-character Git commit"
  local tag=${commit:0:12}
  prepare_data
  systemctl is-active --quiet docker || die "docker is not running"

  local dir=$RELEASES/$commit
  if [ ! -d "$dir/deploy" ]; then
    mkdir -p "$dir"
    aws s3 cp --only-show-errors "s3://$SATSA_S3_BUCKET/releases/$commit/deploy.tgz" "$dir/deploy.tgz" \
      || die "release bundle for $commit not published"
    aws s3 cp --only-show-errors "s3://$SATSA_S3_BUCKET/releases/$commit/deploy.tgz.sha256" "$dir/deploy.tgz.sha256" \
      || die "release checksum missing"
    (cd "$dir" && sha256sum -c --quiet deploy.tgz.sha256) || die "release bundle checksum mismatch"
    tar -xzf "$dir/deploy.tgz" -C "$dir"
  fi
  ln -sfn "$dir" "$CURRENT"
  render_env "$tag"
  render_llm_env

  # A lost signing key must not be replaced silently: records already signed
  # with it would stop verifying. Only a never-initialized volume gets a key.
  if [ -e /data/satsa/.initialized ] && [ ! -s /data/satsa/keys/satsa_trust_key.json ]; then
    die "TRUST-SAT signing key missing from an initialized /data volume; restore it from backup"
  fi

  aws ecr get-login-password | docker login --username AWS --password-stdin \
    "${SATSA_BACKEND_IMAGE%%/*}" >/dev/null || die "ECR login failed"
  compose pull --quiet migrate web caddy || die "images for $tag are not in ECR"
  compose config --quiet || die "compose configuration invalid"
  log "migrating the database"
  compose run --rm migrate || die "migration failed (database unreachable or schema error)"
  compose run --rm key-init || die "TRUST-SAT key initialization failed"
  [ -s /data/satsa/keys/satsa_trust_key.json ] || die "signing key not present after key-init"
  touch /data/satsa/.initialized && chown 10001:10001 /data/satsa/.initialized
  compose up -d --no-build --remove-orphans api worker web caddy
  wait_healthy
  jq -n --arg commit "$commit" --arg tag "$tag" --arg site "$SATSA_SITE_ADDRESS" \
    --arg backend "$SATSA_BACKEND_IMAGE:$tag" --arg web "$SATSA_WEB_IMAGE:$tag" \
    --arg at "$(date -u +%FT%TZ)" \
    '{commit:$commit, image_tag:$tag, backend_image:$backend, web_image:$web, site:$site, deployed_at:$at}' \
    > "$DEPLOYED"
  chmod 644 "$DEPLOYED"
  log "deployed $commit as $tag"; cat "$DEPLOYED"
}

cmd_bootstrap_admin() {
  [ -L "$CURRENT" ] || die "deploy a release first"
  local current; current=$(aws secretsmanager get-secret-value --secret-id "$SATSA_ADMIN_SECRET_ARN" \
    --query SecretString --output text)
  if jq -e .credential >/dev/null 2>&1 <<<"$current"; then
    die "an administrator was already bootstrapped (credential is in Secrets Manager)"
  fi
  local out org credential
  out=$(compose run --rm -T migrate python scripts/bootstrap_satsa_admin.py \
    --database-url "$(grep '^SATSA_DATABASE_URL=' "$RUNTIME_ENV" | cut -d= -f2-)" \
    --ledger /data/identity-audit-ledger.jsonl \
    --name "${SATSA_ADMIN_NAME:-SAT-SA administrator}" --email "${SATSA_ADMIN_EMAIL:-admin@satsa.invalid}" \
    --organization "${SATSA_ORGANIZATION_NAME:-SAT-SA}") || die "bootstrap failed"
  org=$(grep '^organization_id=' <<<"$out" | cut -d= -f2); credential=$(tail -n 1 <<<"$out")
  [ -n "$org" ] && [ -n "$credential" ] || die "bootstrap produced no credential"
  aws secretsmanager put-secret-value --secret-id "$SATSA_ADMIN_SECRET_ARN" \
    --secret-string "$(jq -n --arg o "$org" --arg c "$credential" '{organization_id:$o, credential:$c}')" >/dev/null
  log "organization $org created; administrator credential stored in Secrets Manager (not printed)"
}

# A coordinated backup: no application write happens between the RDS and the
# EBS snapshot because the API and worker are stopped. The two snapshots are
# not one atomic operation; the stopped writers are what makes them coherent.
cmd_snapshot() {
  [ -L "$CURRENT" ] || die "nothing deployed"
  local stamp; stamp=$(date -u +%Y%m%dT%H%M%SZ)
  log "stopping writers (web keeps serving its error page)"
  compose stop worker api
  trap 'compose start api worker >/dev/null 2>&1 || true' EXIT
  sync
  aws rds create-db-snapshot --db-instance-identifier "$SATSA_DB_INSTANCE_ID" \
    --db-snapshot-identifier "satsa-$SATSA_ENV_NAME-$stamp" >/dev/null || die "RDS snapshot failed"
  local ebs; ebs=$(aws ec2 create-snapshot --volume-id "$SATSA_DATA_VOLUME_ID" \
    --description "SAT-SA /data $stamp (coordinated with RDS satsa-$SATSA_ENV_NAME-$stamp)" \
    --tag-specifications "ResourceType=snapshot,Tags=[{Key=satsa-backup,Value=$stamp}]" \
    --query SnapshotId --output text) || die "EBS snapshot failed"
  # Writers may resume once both snapshots have their point in time; waiting
  # for the RDS snapshot to become available keeps the pair unambiguous.
  aws rds wait db-snapshot-available --db-snapshot-identifier "satsa-$SATSA_ENV_NAME-$stamp" \
    || die "RDS snapshot did not complete"
  compose start api worker
  trap - EXIT
  wait_healthy
  jq -n --arg t "$stamp" --arg r "satsa-$SATSA_ENV_NAME-$stamp" --arg e "$ebs" \
    '{taken_at:$t, rds_snapshot:$r, ebs_snapshot:$e}' | tee -a /etc/satsa/snapshots.jsonl
}

# Browser end-to-end against the public HTTPS URL, run from this instance so the
# test credentials never leave AWS. First use provisions an analyst and a
# supervisor through the API; their credentials stay in a root-only file.
cmd_public_e2e() {
  [ -L "$CURRENT" ] || die "deploy a release first"
  local dir=/root/satsa-e2e creds=/root/satsa-e2e/credentials.json
  install -d -m 700 "$dir"
  if [ ! -s "$creds" ]; then
    local admin org credential members
    admin=$(aws secretsmanager get-secret-value --secret-id "$SATSA_ADMIN_SECRET_ARN"       --query SecretString --output text) || die "admin credential unavailable"
    org=$(jq -r .organization_id <<<"$admin"); credential=$(jq -r .credential <<<"$admin")
    [ "$credential" != null ] || die "run bootstrap-admin first"
    members=$(compose exec -T api python scripts/provision_members.py --api http://api:8000       --credential "$credential" --organization "$org"       --member analyst "E2E analyst" e2e-analyst@satsa.invalid       --member supervisor "E2E supervisor" e2e-supervisor@satsa.invalid) || die "member provisioning failed"
    jq -n --arg o "$org" --arg a "$credential" --argjson m "$members"       '{organization_id:$o, admin:$a} + $m' > "$creds"
    chmod 600 "$creds"
  fi
  rm -rf "$dir/work" && mkdir -p "$dir/work"
  cp -r "$CURRENT/web/e2e" "$CURRENT/web/playwright.config.ts" "$dir/work/"
  docker run --rm --network host --ipc host -e CI=1     -e SATSA_E2E_BASE_URL="https://$SATSA_SITE_ADDRESS" -e SATSA_E2E_CREDENTIALS=/creds.json     -v "$creds:/creds.json:ro" -v "$dir/work:/work" -w /work     mcr.microsoft.com/playwright:v1.63.0-noble     bash -c 'npm init -y >/dev/null && npm install --no-save --no-audit --no-fund @playwright/test@1.63.0 >/dev/null && npx playwright test --reporter=list'     || die "public browser end-to-end failed"
  log "public browser end-to-end passed against https://$SATSA_SITE_ADDRESS"
}

cmd_status() {
  [ -r "$DEPLOYED" ] && cat "$DEPLOYED" || echo "nothing deployed"
  [ -L "$CURRENT" ] && compose ps
}

case "${1:-}" in
  deploy) shift; cmd_deploy "$@" ;;
  bootstrap-admin) cmd_bootstrap_admin ;;
  snapshot) cmd_snapshot ;;
  status) cmd_status ;;
  public-e2e) cmd_public_e2e ;;
  *) echo "usage: deploy.sh deploy <commit> | bootstrap-admin | snapshot | status | public-e2e" >&2; exit 2 ;;
esac

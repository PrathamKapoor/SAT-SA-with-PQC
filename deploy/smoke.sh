#!/usr/bin/env bash
# Deployment smoke for a running SAT-SA production stack (deploy/README.md).
#
# Checks the public HTTPS entry point (reachability, HTTP->HTTPS redirect,
# security headers), the API's liveness and readiness, the worker's readiness,
# then runs scripts/deployment_smoke.py inside the stack's network: sign-in by
# credential, organization scope, submission, upload, validation, a real run on
# the worker, findings, risk, recommendations, evidence records, priorities,
# the supervisor decision, TRUST-SAT finalization and verification, audit.
#
# Required environment:
#   SATSA_SMOKE_ORGANIZATION_ID
#   SATSA_SMOKE_ANALYST_CREDENTIAL, SATSA_SMOKE_SUPERVISOR_CREDENTIAL, SATSA_SMOKE_AUDITOR_CREDENTIAL
# Optional:
#   COMPOSE        compose command (default: the production files with deploy/production.env)
#   SATSA_PUBLIC_URL   public base URL (default: https://$SATSA_SITE_ADDRESS)
#   SMOKE_INSECURE_TLS=1   accept a local-CA certificate (verification hosts only)
#
# The smoke creates durable, audited records: point it at a test organization.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=${COMPOSE:-"docker compose -f deploy/compose.production.yml -f deploy/compose.database.yml --env-file deploy/production.env"}
if [[ -z "${SATSA_PUBLIC_URL:-}" ]]; then
  SITE=$(grep -E '^SATSA_SITE_ADDRESS=' deploy/production.env 2>/dev/null | cut -d= -f2- || true)
  SATSA_PUBLIC_URL="https://${SITE:?set SATSA_PUBLIC_URL or SATSA_SITE_ADDRESS}"
fi
CURL=(curl -sS --max-time 20)
[[ "${SMOKE_INSECURE_TLS:-0}" == "1" ]] && CURL+=(-k)
: "${SATSA_SMOKE_ORGANIZATION_ID:?}" "${SATSA_SMOKE_ANALYST_CREDENTIAL:?}" "${SATSA_SMOKE_SUPERVISOR_CREDENTIAL:?}" "${SATSA_SMOKE_AUDITOR_CREDENTIAL:?}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# 1. Public entry point.
code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$SATSA_PUBLIC_URL/login") || fail "public site unreachable"
[[ "$code" == "200" ]] || fail "GET /login returned $code"
pass "public site reachable over HTTPS ($SATSA_PUBLIC_URL)"
headers=$("${CURL[@]}" -D - -o /dev/null "$SATSA_PUBLIC_URL/login")
for h in strict-transport-security x-content-type-options x-frame-options referrer-policy; do
  grep -qi "^$h:" <<<"$headers" || fail "missing security header $h"
done
pass "security headers present"
http_url="http://${SATSA_PUBLIC_URL#https://}"
redirect=$("${CURL[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "$http_url/login" || true)
[[ "$redirect" == 30[178]\ https://* ]] || fail "plain HTTP is not redirected to HTTPS ($redirect)"
pass "HTTP redirects to HTTPS"
code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$SATSA_PUBLIC_URL/workbench")
[[ "$code" == "307" ]] || fail "unauthenticated /workbench returned $code, expected a redirect to sign-in"
pass "workbench requires a session"
# Redirects must stay on the public origin, never the web server's internal one.
for path in /workbench "/logout?reason=expired"; do
  target=$("${CURL[@]}" -o /dev/null -w '%{redirect_url}' -H 'Cookie: satsa_session=invalid' "$SATSA_PUBLIC_URL$path")
  [[ "$target" == "$SATSA_PUBLIC_URL/"* ]] || fail "redirect from $path leaves the public origin: $target"
done
pass "redirects stay on the public origin"

# 2. API and worker readiness (inside the stack; the API is not published).
$COMPOSE exec -T api python -c "import urllib.request as u; u.urlopen('http://api:8000/health/live', timeout=5)" \
  || fail "API liveness"
$COMPOSE exec -T api python -m satsa.api.healthcheck --role api || fail "API readiness (database, schema, storage)"
$COMPOSE exec -T worker python -m satsa.api.healthcheck --role worker || fail "worker readiness"
pass "API live and ready; worker ready"

# 3. The supervisory workflow through the API, on the real worker.
$COMPOSE exec -T \
  -e SATSA_SMOKE_API_URL=http://api:8000 \
  -e SATSA_SMOKE_ORGANIZATION_ID \
  -e SATSA_SMOKE_ANALYST_CREDENTIAL \
  -e SATSA_SMOKE_SUPERVISOR_CREDENTIAL \
  -e SATSA_SMOKE_AUDITOR_CREDENTIAL \
  -e SATSA_SMOKE_TIMEOUT_SECONDS="${SATSA_SMOKE_TIMEOUT_SECONDS:-600}" \
  api python scripts/deployment_smoke.py || fail "workflow smoke"
pass "workflow smoke through API, worker, PostgreSQL, object storage and TRUST-SAT"

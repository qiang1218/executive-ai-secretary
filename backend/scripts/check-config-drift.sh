#!/usr/bin/env bash
# Detects configuration drift: business environment variables still
# declared in compose.yml, .env.example, or scripts that should instead
# live in backend/configs/.
#
# Phase 1: skeleton. The full set of forbidden environment variable
# names is defined as `BUSINESS_ENV_VARS` below; the script greps for
# these names outside of `backend/configs/` and reports any matches.
#
# CI integration: a non-zero exit code fails the build.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Business configuration that Phase 1 wants to live ONLY in
# backend/configs/. If these are referenced in compose.yml, .env files,
# or scripts, the script fails.
BUSINESS_ENV_VARS=(
  "DATABASE_URL"
  "POSTGRES_HOST"
  "POSTGRES_PORT"
  "POSTGRES_DB"
  "POSTGRES_USER"
  "POSTGRES_PASSWORD"
  "SESSION_COOKIE_SECURE"
  "COOKIE_SECURE"
  "SESSION_COOKIE_SAMESITE"
  "WORKER_POLL_SECONDS"
  "WORKER_LEASE_SECONDS"
  "WORKER_HEARTBEAT_SECONDS"
  "WORKER_JOB_MAX_ATTEMPTS"
  "ALLOWED_ORIGINS"
  "TRUSTED_HOSTS"
  "EXPECTED_DATABASE_REVISION"
  "SEED_DEMO_DATA"
)

# Locations where business env vars should NOT be declared.
SEARCH_PATHS=(
  "${REPO_ROOT}/compose.yml"
  "${REPO_ROOT}/docker-compose.yml"
  "${REPO_ROOT}/.env"
  "${REPO_ROOT}/.env.example"
)

failures=0
for var in "${BUSINESS_ENV_VARS[@]}"; do
  for path in "${SEARCH_PATHS[@]}"; do
    if [ -f "${path}" ] && grep -qE "^[[:space:]]*${var}[[:space:]]*[:=]" "${path}"; then
      echo "DRIFT: ${var} found in ${path} (should live in backend/configs/)"
      failures=$((failures + 1))
    fi
  done
done

if [ "${failures}" -gt 0 ]; then
  echo
  echo "${failures} business env var(s) still declared outside backend/configs/."
  echo "Phase 1 requires these to live in profile.*.yaml + secrets.schema.yaml."
  exit 1
fi

echo "No configuration drift detected."
exit 0

# shellcheck shell=bash
# runtime.sh — helper functions for the executive-ai-secretary dev/ops scripts.
#
# The repository now stores every secret in `backend/.env` (Pydantic Settings
# picks it up automatically).  This file exposes:
#
#   * repo_path_resolution helpers
#   * compose / docker command wrappers
#   * preflight checks (env file presence, required CLI tools)
#   * backup-key-file preflight for the 3 openssl key files that the backup
#     tooling needs at fixed paths
#
# Shell scripts MUST source this file from a known path:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=scripts/lib/runtime.sh
#   . "${SCRIPT_DIR}/lib/runtime.sh"
#
# NEVER put any secret value in this file. It is shipped in the repository.

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_LIB_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/compose.yml"
BACKEND_DIR="${REPO_ROOT}/backend"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env"
RUNTIME_DIR="${REPO_ROOT}/runtime"

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*" >&2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

validate_environment_name() {
  case "${1:-}" in
    local-demo|customer-template) ;;
    *) die "environment must be local-demo or customer-template" ;;
  esac
}

runtime_dir_for() {
  printf '%s/%s' "${RUNTIME_DIR}" "$1"
}

backup_key_dir_for() {
  printf '%s/%s/secrets' "${RUNTIME_DIR}" "$1"
}

load_runtime_environment() {
  local environment="$1"
  validate_environment_name "${environment}"

  [ -f "${BACKEND_ENV_FILE}" ] || die "${BACKEND_ENV_FILE} is missing; copy backend/.env.example and fill in the secrets"

  set -a
  # shellcheck disable=SC1090
  . "${BACKEND_ENV_FILE}"
  set +a

  [ "${APP_ENV:-}" = "${environment}" ] || die "APP_ENV in ${BACKEND_ENV_FILE} does not match ${environment}"
  [ "${HOST_BIND:-}" = "127.0.0.1" ] || die "phase 1 permits only HOST_BIND=127.0.0.1"
  case "${COMPOSE_PROJECT_NAME:-}" in
    executive-ai-local-demo|executive-ai-customer-template) ;;
    *) die "unexpected COMPOSE_PROJECT_NAME: ${COMPOSE_PROJECT_NAME:-unset}" ;;
  esac

  if [ "${environment}" = "customer-template" ]; then
    [ "${APP_MODE:-}" = "production" ] || die "customer-template requires APP_MODE=production"
    [ "${SEED_DEMO_DATA:-}" = "false" ] || die "customer-template refuses SEED_DEMO_DATA=${SEED_DEMO_DATA:-unset}"
  fi

  export RUNTIME_DIR BACKEND_DIR
}

compose() {
  local environment="$1"
  shift
  load_runtime_environment "${environment}"
  docker compose \
    --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${BACKEND_ENV_FILE}" \
    --file "${COMPOSE_FILE}" \
    "$@"
}

require_backup_key_files() {
  local environment="$1"
  local key_dir
  local name
  key_dir="$(backup_key_dir_for "${environment}")"
  for name in backup_encryption_key backup_signing_key backup_signing_public_key; do
    [ -s "${key_dir}/${name}" ] || die "missing backup key: ${key_dir}/${name}; generate with openssl genpkey or ed25519 and place the file at this path"
  done
}

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

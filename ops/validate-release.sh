#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-source}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "falta la variable requerida ${name}"
}

validate_digest() {
  local value="$1"
  [[ "$value" =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ ]] || fail "la imagen debe ser una referencia completa fijada por digest sha256"
}

case "$mode" in
  source)
    for name in GCP_PROJECT_ID GCP_REGION AR_REPOSITORY API_SERVICE PWA_SERVICE MIGRATION_JOB; do
      require_env "$name"
    done
    [[ -f backend/api/Dockerfile ]] || fail "falta backend/api/Dockerfile"
    [[ -f frontend/apps/nodo-web/Dockerfile ]] || fail "falta frontend/apps/nodo-web/Dockerfile"
    grep -Eq 'COPY[[:space:]].*alembic\.ini' backend/api/Dockerfile || fail "la imagen API no copia alembic.ini"
    grep -Eq 'COPY[[:space:]].*migrations' backend/api/Dockerfile || fail "la imagen API no copia migrations/"
    ;;
  digests)
    require_env API_IMAGE
    require_env PWA_IMAGE
    validate_digest "$API_IMAGE"
    validate_digest "$PWA_IMAGE"
    ;;
  *)
    fail "modo inválido; usar source o digests"
    ;;
esac

printf 'Release preflight OK (%s).\n' "$mode"

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
    require_env SOURCE_IMAGE_PREFIX
    [[ "$SOURCE_IMAGE_PREFIX" =~ ^[a-z][a-z0-9-]*-docker\.pkg\.dev/[a-z][a-z0-9-]+/[a-z0-9][a-z0-9._-]*$ ]] || fail "el origen aprobado debe ser un registro regional de Artifact Registry, proyecto y repositorio"
    validate_digest "$API_IMAGE"
    validate_digest "$PWA_IMAGE"
    [[ "${API_IMAGE%@sha256:*}" == "${SOURCE_IMAGE_PREFIX}/api" ]] || fail "API fuera del repositorio/origen aprobado"
    [[ "${PWA_IMAGE%@sha256:*}" == "${SOURCE_IMAGE_PREFIX}/pwa" ]] || fail "PWA fuera del repositorio/origen aprobado"
    ;;
  *)
    fail "modo inválido; usar source o digests"
    ;;
esac

printf 'Release preflight OK (%s).\n' "$mode"

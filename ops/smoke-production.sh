#!/usr/bin/env bash
set -Eeuo pipefail

: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:?Define GCP_REGION}"
: "${API_SERVICE:?Define API_SERVICE}"
: "${PWA_SERVICE:?Define PWA_SERVICE}"

command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'ERROR: python3 no está instalado.\n' >&2; exit 1; }
: "${SMOKE_ADMIN_EMAIL:?Define SMOKE_ADMIN_EMAIL para la cuenta sintética autorizada}"
: "${SMOKE_ADMIN_PASSWORD:?Define SMOKE_ADMIN_PASSWORD por canal secreto}"
: "${SMOKE_EXPECTED_ALEMBIC_REVISION:?Define la revisión esperada del SHA promovido}"

api_url="$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --format='value(status.url)')"
pwa_url="$(gcloud run services describe "$PWA_SERVICE" --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --format='value(status.url)')"
[[ -n "$api_url" && -n "$pwa_url" ]] || { printf 'ERROR: servicios sin URL lista.\n' >&2; exit 1; }

# A custom canonical domain must be supplied explicitly when BFF origin checks
# reject the generated run.app hostname. Both URLs are validated by the client.
export SMOKE_PWA_URL="${SMOKE_PWA_URL:-$pwa_url}" SMOKE_API_URL="$api_url"
export SMOKE_API_ID_TOKEN
SMOKE_API_ID_TOKEN="$(gcloud auth print-identity-token --audiences="$api_url")"
trap 'unset SMOKE_API_ID_TOKEN' EXIT
# No tokens/passwords in command arguments, stdout, temporary files or reports.
python3 "$(dirname "$0")/smoke-authenticated.py"

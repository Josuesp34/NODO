#!/usr/bin/env bash
set -Eeuo pipefail

: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:?Define GCP_REGION}"
: "${API_SERVICE:?Define API_SERVICE}"
: "${PWA_SERVICE:?Define PWA_SERVICE}"

command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }
command -v curl >/dev/null || { printf 'ERROR: curl no está instalado.\n' >&2; exit 1; }

api_url="$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --format='value(status.url)')"
pwa_url="$(gcloud run services describe "$PWA_SERVICE" --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --format='value(status.url)')"
[[ -n "$api_url" && -n "$pwa_url" ]] || { printf 'ERROR: servicios sin URL lista.\n' >&2; exit 1; }

curl --fail --silent --show-error --retry 5 --retry-all-errors --max-time 20 \
  --output /dev/null "$pwa_url/"

id_token="$(gcloud auth print-identity-token --audiences="$api_url")"
curl --fail --silent --show-error --retry 5 --retry-all-errors --max-time 20 \
  --header "Authorization: Bearer ${id_token}" --output /dev/null "$api_url/health"

printf 'Smoke OK: PWA / y API /health respondieron sin imprimir cuerpos ni tokens.\n'

#!/usr/bin/env bash
set -Eeuo pipefail

: "${EXPECTED_GCP_ACCOUNT:?Define EXPECTED_GCP_ACCOUNT con la identidad aprobada}"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:?Define GCP_REGION}"

command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
active_project="$(gcloud config get-value project 2>/dev/null)"

[[ "$active_account" == "$EXPECTED_GCP_ACCOUNT" ]] || {
  printf 'ERROR: cuenta activa distinta de EXPECTED_GCP_ACCOUNT.\n' >&2
  exit 1
}
[[ "$active_project" == "$GCP_PROJECT_ID" ]] || {
  printf 'ERROR: proyecto activo distinto de GCP_PROJECT_ID.\n' >&2
  exit 1
}

gcloud projects describe "$GCP_PROJECT_ID" --format='table(projectId,lifecycleState)'
gcloud billing projects describe "$GCP_PROJECT_ID" --format='table(projectId,billingEnabled)'
gcloud compute regions describe "$GCP_REGION" --project "$GCP_PROJECT_ID" --format='table(name,status)'
gcloud services list --enabled --project "$GCP_PROJECT_ID" \
  --filter='config.name:(run.googleapis.com OR sqladmin.googleapis.com OR artifactregistry.googleapis.com OR secretmanager.googleapis.com)' \
  --format='table(config.name,state)'

printf 'Preflight de sólo lectura completado. No se creó ni modificó ningún recurso.\n'

#!/usr/bin/env bash
set -Eeuo pipefail

: "${CONFIRM_ROLLBACK:?Define CONFIRM_ROLLBACK=YES}"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:?Define GCP_REGION}"
: "${CLOUD_RUN_SERVICE:?Define CLOUD_RUN_SERVICE}"
: "${TARGET_REVISION:?Define TARGET_REVISION}"

[[ "$CONFIRM_ROLLBACK" == "YES" ]] || { printf 'ERROR: confirmación inválida.\n' >&2; exit 1; }
command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }

gcloud run revisions describe "$TARGET_REVISION" --service "$CLOUD_RUN_SERVICE" \
  --project "$GCP_PROJECT_ID" --region "$GCP_REGION" \
  --format='table(metadata.name,status.conditions[0].status,status.conditions[0].message)'
gcloud run services update-traffic "$CLOUD_RUN_SERVICE" \
  --to-revisions "${TARGET_REVISION}=100" \
  --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --quiet

printf 'Tráfico dirigido a %s. Ejecutar ops/smoke-production.sh y registrar evidencia.\n' "$TARGET_REVISION"

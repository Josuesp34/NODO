#!/usr/bin/env bash
set -Eeuo pipefail

: "${CONFIRM_BACKUP:?Define CONFIRM_BACKUP=YES para crear una copia administrada}"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${CLOUD_SQL_INSTANCE:?Define CLOUD_SQL_INSTANCE}"

[[ "$CONFIRM_BACKUP" == "YES" ]] || { printf 'ERROR: confirmación inválida.\n' >&2; exit 1; }
command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }

gcloud sql instances describe "$CLOUD_SQL_INSTANCE" --project "$GCP_PROJECT_ID" \
  --format='table(name,region,databaseVersion,state)'
gcloud sql backups create --instance "$CLOUD_SQL_INSTANCE" --project "$GCP_PROJECT_ID" --async

if [[ -n "${EXPORT_URI:-}" || -n "${DATABASE_NAME:-}" ]]; then
  [[ -n "${EXPORT_URI:-}" && -n "${DATABASE_NAME:-}" ]] || {
    printf 'ERROR: EXPORT_URI y DATABASE_NAME se definen juntos.\n' >&2
    exit 1
  }
  [[ "$EXPORT_URI" =~ ^gs://[^[:space:]]+\.sql\.gz$ ]] || {
    printf 'ERROR: EXPORT_URI debe ser gs://...sql.gz dentro del bucket aprobado.\n' >&2
    exit 1
  }
  gcloud sql export sql "$CLOUD_SQL_INSTANCE" "$EXPORT_URI" \
    --database "$DATABASE_NAME" --project "$GCP_PROJECT_ID" --async
fi

printf 'Backup solicitado. Verificar SUCCEEDED en Cloud SQL antes de usarlo como evidencia.\n'

#!/usr/bin/env bash
set -Eeuo pipefail

: "${CONFIRM_RESTORE:?Define CONFIRM_RESTORE=RESTORE_TO_NEW_INSTANCE}"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${SOURCE_INSTANCE:?Define SOURCE_INSTANCE}"
: "${TARGET_INSTANCE:?Define TARGET_INSTANCE con un nombre nuevo}"
: "${POINT_IN_TIME:?Define POINT_IN_TIME en RFC3339 UTC}"

[[ "$CONFIRM_RESTORE" == "RESTORE_TO_NEW_INSTANCE" ]] || { printf 'ERROR: confirmación inválida.\n' >&2; exit 1; }
[[ "$SOURCE_INSTANCE" != "$TARGET_INSTANCE" ]] || { printf 'ERROR: el destino debe ser una instancia nueva.\n' >&2; exit 1; }
[[ "$POINT_IN_TIME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || {
  printf 'ERROR: POINT_IN_TIME debe usar RFC3339 UTC, por ejemplo 2026-01-31T23:59:00Z.\n' >&2
  exit 1
}
command -v gcloud >/dev/null || { printf 'ERROR: gcloud no está instalado.\n' >&2; exit 1; }

gcloud sql instances describe "$SOURCE_INSTANCE" --project "$GCP_PROJECT_ID" \
  --format='table(name,region,databaseVersion,state)'
if gcloud sql instances describe "$TARGET_INSTANCE" --project "$GCP_PROJECT_ID" >/dev/null 2>&1; then
  printf 'ERROR: TARGET_INSTANCE ya existe; no se sobrescribe.\n' >&2
  exit 1
fi

gcloud sql instances clone "$SOURCE_INSTANCE" "$TARGET_INSTANCE" \
  --point-in-time "$POINT_IN_TIME" --project "$GCP_PROJECT_ID" --async

printf 'Clon PITR solicitado. Validar datos y controles de acceso antes de cualquier cambio de tráfico.\n'

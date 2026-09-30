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
command -v python3 >/dev/null || { printf 'ERROR: python3 no está instalado.\n' >&2; exit 1; }
[[ "$TARGET_INSTANCE" =~ ^[a-z]([a-z0-9-]{0,96}[a-z0-9])?$ ]] || { printf 'ERROR: nombre destino inválido.\n' >&2; exit 1; }
python3 - <<'PY'
import os
from datetime import datetime
try:
    datetime.fromisoformat(os.environ['POINT_IN_TIME'].replace('Z', '+00:00'))
except ValueError:
    raise SystemExit('ERROR: POINT_IN_TIME no representa una fecha válida.') from None
PY

gcloud sql instances describe "$SOURCE_INSTANCE" --project "$GCP_PROJECT_ID" \
  --format='table(name,region,databaseVersion,state)'
# A permission/network error must never be interpreted as target-not-found.
target_exists="$(gcloud sql instances list --project "$GCP_PROJECT_ID" --filter="name=$TARGET_INSTANCE" --format='value(name)')"
if [[ -n "$target_exists" ]]; then
  printf 'ERROR: TARGET_INSTANCE ya existe; no se sobrescribe.\n' >&2
  exit 1
fi

export RECOVERY_CLONE_START_SECONDS
RECOVERY_CLONE_START_SECONDS="$(date +%s)"
operation="$(gcloud sql instances clone "$SOURCE_INSTANCE" "$TARGET_INSTANCE" \
  --point-in-time "$POINT_IN_TIME" --project "$GCP_PROJECT_ID" --async --format='value(name)')"
[[ -n "$operation" ]] || { printf 'ERROR: no se obtuvo operación PITR.\n' >&2; exit 1; }
gcloud sql operations wait "$operation" --project "$GCP_PROJECT_ID" --timeout=1800 >/dev/null
state="$(gcloud sql instances describe "$TARGET_INSTANCE" --project "$GCP_PROJECT_ID" --format='value(state)')"
[[ "$state" == "RUNNABLE" ]] || { printf 'ERROR: clon PITR aún no está RUNNABLE.\n' >&2; exit 1; }
export RECOVERY_CLONE_END_SECONDS
RECOVERY_CLONE_END_SECONDS="$(date +%s)"
python3 - <<'PY'
import json, os
print(json.dumps({
    'event': 'pitr_clone_verified', 'clone_ready': True,
    'provision_seconds': int(os.environ['RECOVERY_CLONE_END_SECONDS']) - int(os.environ['RECOVERY_CLONE_START_SECONDS']),
    'application_restored': False, 'rto_measured': False,
}))
PY

printf 'PITR completó el clon; faltan validar datos, reejecutar borrados y medir recuperación funcional antes de tráfico.\n'

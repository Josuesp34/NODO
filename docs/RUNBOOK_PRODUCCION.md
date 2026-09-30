# Runbook de producción

## Despliegue normal

1. CI verde en el SHA exacto: backend, migraciones PostgreSQL, frontend, contenedores, Terraform y seguridad.
2. Despliegue manual a `staging` con el GitHub Environment protegido.
3. Confirmar job Alembic, smoke, flujos coach/atleta y ausencia de regresiones con datos sintéticos.
4. Registrar los digests API/PWA generados en staging.
5. Aprobar la promoción en el Environment `production` y proporcionar esos mismos digests.
6. Confirmar migración, revisiones activas, smoke y alertas.

La primera publicación, un cambio destructivo y cualquier operación sobre datos reales requieren aprobación humana explícita.

## Fallo de migración

El workflow se detiene antes de actualizar los servicios. Conservar logs sin PII, clasificar el fallo y corregir con una nueva migración. No ejecutar `alembic downgrade` en producción sin análisis de compatibilidad y backup/restauración probada.

## Fallo de nueva revisión

Seleccionar una revisión conocida del mismo servicio y ejecutar:

```bash
export CONFIRM_ROLLBACK=YES
export GCP_PROJECT_ID='proyecto-aprobado'
export GCP_REGION='region-aprobada'
export CLOUD_RUN_SERVICE='servicio'
export TARGET_REVISION='revision-verificada'
bash ops/rollback-cloud-run.sh
```

Después ejecutar `bash ops/smoke-production.sh` y registrar revisión, hora, causa y resultado. Si la revisión antigua no es compatible con el esquema actual, aplicar un forward fix; no asumir que el rollback de código basta.

## Incidente de seguridad o privacidad

1. Detener el acceso afectado sin borrar evidencia ni datos.
2. Revocar sesión/token/versión de secreto concreta; no deshabilitar facturación ni borrar el proyecto.
3. Preservar logs restringidos y línea de tiempo sin copiar PII a chats.
4. Evaluar alcance, usuarios afectados y obligaciones legales con responsables humanos.
5. Corregir, rotar, validar y documentar. La comunicación externa requiere aprobación humana.

## Evidencia mínima por release

SHA de `main`, checks, digests, ejecución de migración, revisión Cloud Run, URL HTTPS, smoke, responsable, hora, costo/alertas y cualquier excepción aprobada.

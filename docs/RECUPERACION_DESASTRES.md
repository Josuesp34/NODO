# Recuperación ante desastres

Objetivos iniciales propuestos: **RPO ≤ 24 h** y **RTO ≤ 4 h**. Son objetivos, no resultados medidos. No se consideran cumplidos hasta ejecutar un restore drill cronometrado.

## Capas

- Cloud SQL: backups automáticos y PITR.
- Exportación lógica opcional a bucket privado con retención.
- Cloud Storage: versionado y retención; `force_destroy=false`.
- Código e infraestructura: Git, lockfiles e imágenes por digest.

## Backup bajo demanda

```bash
export CONFIRM_BACKUP=YES
export GCP_PROJECT_ID='proyecto-aprobado'
export CLOUD_SQL_INSTANCE='instancia-origen'
bash ops/backup-cloud-sql.sh
```

El script sólo solicita la copia. La evidencia válida exige confirmar estado `SUCCEEDED`.

## Restore drill aislado

Elegir un instante dentro de la ventana PITR y un nombre de instancia que no exista:

```bash
export CONFIRM_RESTORE=RESTORE_TO_NEW_INSTANCE
export GCP_PROJECT_ID='proyecto-aprobado'
export SOURCE_INSTANCE='instancia-origen'
export TARGET_INSTANCE='instancia-drill-nueva'
export POINT_IN_TIME='AAAA-MM-DDThh:mm:ssZ'
bash ops/restore-cloud-sql.sh
```

Validar en aislamiento: integridad, migración Alembic, conteos no sensibles, autorización cruzada negativa y smoke de API. Registrar inicio, fin, RPO observado y RTO observado. Eliminar la instancia de drill sólo con aprobación y después de preservar evidencia necesaria.

## Criterio para abrir piloto

Una configuración de backups no equivale a restauración. El piloto sigue bloqueado hasta que un drill haya terminado, sus tiempos estén dentro de objetivos o exista una excepción humana documentada y el runbook haya sido corregido con lo aprendido.

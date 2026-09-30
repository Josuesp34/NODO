# Plataforma GCP de NODO

Terraform define entornos aislados `staging` y `prod` conforme a `docs/ADR/0008-despliegue-gcp.md`. No contiene IDs de proyecto, región, precios ni valores secretos. Nada en este directorio ha sido aplicado a una cuenta real.

## Qué crea el módulo

- VPC y subred para Direct VPC egress.
- Cloud SQL PostgreSQL 16 con IP privada, backups automáticos y PITR.
- Artifact Registry con etiquetas inmutables.
- buckets privados y versionados para FIT, exportaciones y copias lógicas.
- contenedores de Secret Manager; sus valores nunca entran en Terraform.
- cuentas de servicio separadas, IAM mínimo y Workload Identity Federation para GitHub.
- Cloud Run API/PWA, job de migración y worker pool opcional.
- budget y alertas opcionales, desactivados hasta aprobar importe, canales y umbrales.

## Aplicación en dos etapas

1. Verificar identidad y cuenta con `bash ops/preflight-gcp.sh`.
2. Copiar `backend.hcl.example` y `terraform.tfvars.example` fuera de Git, completar sólo datos aprobados e inicializar el backend remoto.
3. Ejecutar `terraform plan` con `deploy_workloads=false`. Un humano revisa recursos, región, cuotas y costo en la calculadora oficial. Terraform no realiza el `apply` automáticamente.
4. Aplicar la base sólo con aprobación de infraestructura y finanzas.
5. Cargar versiones de secretos por canal seguro, construir imágenes, ejecutar scans y fijarlas por `@sha256`.
6. Ejecutar un segundo plan con bindings de secretos explícitos y `deploy_workloads=true`.
7. Desplegar primero `staging`; promoción a `production` reutiliza exactamente los mismos digests.

Ejemplo de validación sin credenciales ni estado remoto:

```bash
terraform fmt -check -recursive infra
cd infra/environments/staging
terraform init -backend=false
terraform validate
```

La configuración fue validada localmente con Terraform 1.13.3 y proveedores `hashicorp/google` y `hashicorp/google-beta` 7.46.1. Los lockfiles fijan esas selecciones. Un `plan` real sigue pendiente porque requiere project ID, región, cuenta de facturación, permisos y APIs reales.

## Estado y secretos

El bucket de estado no se autocrea para evitar el problema circular de guardar el estado que crea su propio almacén. Debe habilitar versionado, acceso uniforme, prevención de acceso público y permisos limitados a operadores aprobados. No usar estado local para `staging` o `prod`.

Terraform crea únicamente los nombres de secretos. Cargar los valores con Secret Manager, nunca con `terraform.tfvars`, GitHub secrets, argumentos de shell o outputs. Los servicios reciben sólo los secretos declarados en su mapa de bindings.

## Particiones PostgreSQL

Cloud SQL soporta `pg_partman` y `pg_cron`, pero no se asume un background worker de `pg_partman`. La migración de aplicación debe crear la extensión y programar mantenimiento explícito con `pg_cron` o Cloud Scheduler. Eso se prueba en `staging` antes de habilitar el piloto.

## Nombres que esperan los workflows

Los GitHub Environments `staging` y `production` deben requerir reviewers y definir variables, no secretos: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `AR_REPOSITORY`, `API_SERVICE`, `PWA_SERVICE`, `MIGRATION_JOB`, `WORKER_ENABLED` y, si aplica, `WORKER_POOL`. La federación restringe repositorio y refs; no se crean llaves JSON.

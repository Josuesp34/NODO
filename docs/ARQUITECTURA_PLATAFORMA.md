# Arquitectura de plataforma

Estado: **definida y validada sintácticamente; no aprovisionada**.

## Topología

```text
Internet -> Cloud Run PWA/BFF -> Cloud Run API -> Cloud SQL PostgreSQL 16 privado
                                |              -> Cloud Storage privado
                                |              -> tabla jobs
                                +-> worker pool (sin HTTP)

GitHub OIDC -> WIF -> cuenta deploy -> Artifact Registry / Cloud Run
Cloud Run job -> Alembic -> Cloud SQL
```

`staging` y `prod` son raíces Terraform separadas y deben apuntar a proyectos GCP distintos. Cada entorno tiene VPC, SQL, buckets, identidades, secretos, registro y workloads propios. La PWA es pública; la API queda privada detrás del BFF salvo una decisión explícita y revisada. El worker es opcional hasta que `app.worker` exista y sus reintentos/idempotencia estén probados.

## Límites de responsabilidad

- Terraform crea infraestructura y contenedores de secretos, nunca valores secretos.
- GitHub Actions construye y escanea; staging produce digests y producción recibe exactamente esos digests.
- El job de migración termina correctamente antes de actualizar servicios.
- Cloud Run conserva revisiones para rollback de aplicación. Un rollback de aplicación no revierte automáticamente el esquema.
- PostgreSQL usa particiones, BRIN, `pg_partman` y mantenimiento programado. No se usa TimescaleDB.

## Decisiones pendientes antes de un plan real

- IDs de proyectos dedicados, región efectiva y requisitos de residencia.
- cuenta de facturación, vigencia de créditos, cuota disponible y tier de Cloud SQL.
- dominio/DNS, canales de alerta, retención final y RPO/RTO aprobados.
- proveedor/región de IA y permisos de intervals.icu.

La fuente ejecutable es [`infra/README.md`](../infra/README.md). Las decisiones normativas están en ADR 0007/0008 y el contrato de producto en `PLAN_MAESTRO_NODO.md`.

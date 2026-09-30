# Matriz requisito → código → prueba → evidencia

Actualizada: 23 de septiembre de 2026. Esta matriz distingue **código presente** de **evidencia de producción**. `Pendiente` no se convierte en hecho por existir documentación, un mock o CI local.

| Requisito | Código / configuración | Prueba o gate | Evidencia exigida | Estado verificable |
|---|---|---|---|---|
| Identidad multirol y asignación | `backend/api/app/infrastructure/database/models/`, rutas auth | `tests/api/test_identity_and_planning.py`, acceso propio/denegado | CI del SHA + E2E multirol | Código y E2E local verificados; despliegue pendiente |
| Sesión BFF segura | `frontend/apps/nodo-web`, ADR 0004 | cookie `httpOnly`, refresh, logout y cache | navegador + headers HTTPS | Código, build y navegador local verificados; HTTPS pendiente |
| Planeación y CAS | rutas/modelos de planning | publish idempotente y conflicto concurrente | E2E coach→atleta | E2E local completo; recorrido público pendiente |
| Actividad con dueño e idempotencia | modelos/migraciones, ingesta FIT | `test_fit_ingestion.py`, duplicados/acceso cruzado | importación staging | Código/pruebas locales verificados; staging pendiente |
| PostgreSQL 16 particionado | migración `0004`, ADR 0007 | upgrade/check/downgrade/upgrade + particiones | Cloud SQL staging | PostgreSQL 16 local verificado; Cloud SQL pendiente |
| intervals.icu | servicio adapter | `test_intervals_adapter.py`, contrato simulado | OAuth/webhook/backfill/revocación reales | Sólo simulación/local hasta verificar proveedor |
| Cola persistente | servicio jobs y worker sobre Postgres | `test_jobs.py`, retry/lease/idempotencia | worker pool staging + métrica de cola | Código/pruebas locales verificados; despliegue pendiente |
| Correo e identidad recuperable | Resend outbox, migración 0005, PWA `/password-reset` | `test_email_recovery.py`: cifrado, respuesta genérica, revocación y envío simulado | dominio verificado, worker, entrega/bounce reales | Código y PostgreSQL local verificados; proveedor real pendiente |
| PWA única responsive/offline | `frontend/apps/nodo-web`, `DESIGN_SYSTEM.md` | `pwa-contract.test.mjs`, build y QA visual | Safari iOS y Chrome Android físicos | Build/navegador local verificados; dispositivos pendientes |
| Molestias y revisión | API/PWA según plan maestro | reglas de prioridad y no ocultamiento | recorrido coach/persona | API/PWA y pruebas locales presentes; staging pendiente |
| Copiloto coach | API simulada + `LLM_COACH.md` | `EVALUACIONES_LLM.md` + hard gates | proveedor real, trazas y aprobación | Simulación funcional; IA real pendiente |
| Asistente persona | API simulada + `LLM_ATLETA.md` | `EVALUACIONES_LLM.md` + hard gates | proveedor real, trazas y aprobación | Simulación funcional; IA real pendiente |
| Datos sintéticos 70 × 12 semanas | generador/fixtures objetivo | integridad, deportes/unidades/casos límite | artefacto de evaluación versionado | Pendiente |
| API/PWA Cloud Run | `infra/modules/nodo_platform/workloads.tf` | Terraform validate, build containers, smoke | revisión/URL HTTPS | Configuración validada; no aprovisionada |
| Worker pool y job migración | mismo módulo | build con Alembic + job antes de servicios | ejecuciones Cloud Run | Configuración y preflight validados; build/ejecución pendientes |
| Cloud SQL privado | `infra/modules/nodo_platform/main.tf` | Terraform plan + conexión desde Cloud Run | inventario GCP y `/health` | Configuración validada; plan/apply pendientes |
| Storage/Secret Manager | mismo módulo | policy scan + acceso mínimo | inventario/IAM real | Configuración validada; valores secretos externos |
| IAM/WIF sin llaves | `iam.tf`, deploy workflows | OIDC de refs aprobadas, ref negada | audit log GitHub/GCP | Configuración validada; conexión externa pendiente |
| Supply chain | workflows `security.yml`, backend/frontend | CodeQL, OSV, Trivy, dependency review, SBOM | checks del SHA/digests | Definido; debe correr en GitHub |
| Backups/PITR | Terraform + `ops/backup-cloud-sql.sh` | restore drill aislado | RPO/RTO medidos | Configurado en código; drill pendiente |
| Rollback | `ops/rollback-cloud-run.sh` | revisión previa + smoke | incidente/drill fechado | Runbook listo; no ejecutado |
| Costos/alertas | `monitoring.tf`, `COSTOS.md` | plan/cotización y canales | budget/alertas reales | Desactivado hasta aprobación humana |
| Seguridad/privacidad | `SEGURIDAD.md`, aplicación | acceso cruzado, rate limit, export/delete, pentest | aprobaciones y reporte | Controles locales presentes; pentest/gates humanos pendientes |
| Lanzamiento vendible | `LANZAMIENTO.md`, `PILOT_READINESS.md` | checklist GO/NO-GO completo | URL, release, soporte, precio/legal | Piloto acompañado listo en código; **NO-GO producción** |

## Evidencia de plataforma generada en esta rama

- `terraform fmt -check -recursive infra`: verde con Terraform 1.13.3.
- `terraform validate`: verde para `staging` y `prod` con proveedores 7.46.1, sin backend/credenciales.
- `bash -n ops/*.sh`: verde.
- parseo YAML de todos los workflows: verde.
- backend: `50 passed` y `ruff check` verde.
- PostgreSQL 16 local: 0001→0005, `alembic check`, downgrade base y upgrade head verdes.
- PWA: typecheck, `9/9` pruebas, build Next y E2E local coach→atleta previo verdes.

Eso valida estructura local, no recursos GCP, IAM real, costos, restauración, despliegue ni producto publicado.

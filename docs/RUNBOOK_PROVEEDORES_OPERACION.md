# Preparación operativa y proveedores de NODO

Estado: código y contratos sintéticos; **no aplicado, no desplegado y sin recuperación Cloud ejecutada**. La instrucción vigente de Brandon excluye cualquier creación, cambio o despliegue en Google Cloud. Estos pasos son para una futura ejecución autorizada de Josué sobre proyectos dedicados de NODO; Vibe Conversa no forma parte de esta entrega.

## Contrato Terraform y secretos

`staging` y `prod` exponen las mismas variables. `deploy_workloads`, `enable_worker`, `enable_intervals`, `enable_web_push`, `enable_vertex_ai` y alertas permanecen desactivados por defecto. No ejecutar workflows manuales ni `terraform apply` como parte de la preparación. Validación local: `terraform init -backend=false -lockfile=readonly`, `terraform validate` y pruebas con ambos providers declarados como mocks.

Definir `public_app_url` como origen HTTPS PWA. Terraform fuerza `NODO_APP_ORIGIN`, cookies Secure, URL/audience de API privada y deriva callback OAuth en `/athlete/connections/intervals/callback`. El webhook Intervals apunta a `/api/providers/intervals/webhook` en la PWA; ésta relayea por IAM a la API. No conceder `allUsers` a API ni conectar al proveedor directamente a Cloud Run privado.

| Proceso | Variables secretas | Versión/ubicación |
|---|---|---|
| API y worker | `DATABASE_URL`, `RESEND_API_KEY`, `EMAIL_QUEUE_KEY` | Bindings explícitos por servicio; API/worker con mismo contrato operativo |
| Migración | `DATABASE_URL` | Cuenta de migración y secreto de base solamente |
| OAuth API | `INTERVALS_CLIENT_ID`, `INTERVALS_CLIENT_SECRET`, `INTERVALS_WEBHOOK_SECRET`, `PROVIDER_TOKEN_ENCRYPTION_KEY` | `provider_secret_versions`; versiones numéricas, sin `latest` |
| Sincronización/desconexión worker | `PROVIDER_TOKEN_ENCRYPTION_KEY` | Sin client secret OAuth ni webhook secret innecesarios |
| Web Push API/worker | `WEB_PUSH_PRIVATE_KEY`, `PUSH_ENCRYPTION_KEY` | VAPID privada y Fernet separado de OAuth |
| PWA | Ninguno de los secretos anteriores | BFF conserva tokens de sesión en cookies httpOnly; no expone valores a JavaScript |

El operador carga valores fuera de Terraform y Git, por Secret Manager y canal privado. `web_push_public_key` y `web_push_contact` son públicos; el sujeto VAPID debe ser `mailto:` o `https:`. No reciclar claves OAuth, push y correo. Los contenedores legacy `ai-api-key`/SMTP no autorizan su uso: Vertex emplea ADC, sin clave JSON ni API key. Registrar propietario, finalidad, versión, rotación y última comprobación de cada binding sin copiar su valor.

## Vertex y presupuesto

`enable_vertex_ai=true` añade únicamente `aiplatform.googleapis.com` y un rol custom con `aiplatform.endpoints.predict` a la cuenta API. Worker/PWA/migración no reciben ese permiso. Josué debe confirmar modelo, región efectiva, disponibilidad, cuota, términos y tarifas actuales antes de definir `ai_configuration`; las ubicaciones de Vertex y Cloud SQL pueden diferir. El plan rechaza Vertex sin modelo/ubicación y topes/tarifas positivos.

Los límites mensuales de solicitudes, tokens y costo por usuario/organización llegan a la aplicación. La reserva conservadora se toma antes del proveedor y persiste en error/cancelación; no equivale a una factura exacta. El budget GCP tiene avisos del 25/50/75/90/100% y **no corta el gasto**. Confirmar cuenta de billing, `monthly_budget_units`, canales y responsables. Comparar las reservas agregadas de aplicación con Billing; no enviar prompts, conversaciones o datos de salud a métricas.

## Archivos y borrado

API y worker reciben `STORAGE_BACKEND=gcs` y `STORAGE_BUCKET` privado automáticamente. El adapter actual usa un bucket con prefijos `fit/<athlete>/` y `export/<athlete>/`; la retención lifecycle se acota por prefijo (365/30 días por defecto), y no se añaden holds/retention locks que impidan un borrado solicitado. El bucket de exportaciones separado permanece disponible para registros de assets; no asumir que el adapter actual lo usa. `PRIVACY_GCS_BUCKETS` autoriza sólo esos dos buckets para cleanup registrado.

Los buckets de usuario tienen soft delete explícito a **0**, acceso uniforme y prevención de acceso público. FIT tiene versionado: cleanup enumera y elimina cada generación. Lifecycle no sustituye el borrado por solicitud y puede tener demora; validar versiones actuales/no actuales y ausencia física con un FIT sintético autorizado. Cambiar soft delete a 0 no elimina copias soft-deleted que ya existan: inventariarlas antes de afirmar borrado completo y esperar su plazo original.

Backups lógicos: versionado, lifecycle 30 días y soft delete **7 días** explícito; una generación eliminada al día 30 puede seguir recuperable hasta el día 37, además de la demora de lifecycle. Cloud SQL: backups automáticos retenidos 14 y WAL/PITR 7 días. Son ventanas de recuperación distintas de datos activos. El responsable legal debe aprobarlas y documentar que una copia de recuperación aún puede contener datos borrados. Tras un restore, reejecutar solicitudes de eliminación/revocación posteriores al punto restaurado **antes de abrir tráfico**. No afirmar eliminación inmediata de esas copias ni bajar retención sin decisión del propietario.

## Alertas y lectura operativa

Preparadas: 5xx, disco SQL, jobs dead, cola vencida/lease obsoleto, fallos de correo, proveedores/push y ausencia de heartbeat. Root emite JSON puro `worker_health` cada 60 s con `pending_count`, `dead_count`, `oldest_pending_age_seconds`, `stale_running_count`; nunca IDs, destinatarios, texto, tokens ni payloads. Cada proyecto queda aislado por entorno. Heartbeat absence requiere una serie previamente emitida; confirmar nombre/tipo de recurso Cloud Run worker pool y simular parada/arranque antes de dar la alerta por verificada.

`enable_monitoring_alerts=true` requiere canales existentes aprobados y comprobar su entrega. Las políticas se validan localmente, pero no hay evidencia de recepción real en esta entrega. Alertas de error de backup incluyen auditoría de operaciones SQL fallidas; la antigüedad y resultado efectivo se comprueban con `python3 ops/check-backups.py` (sólo lectura), `GCP_PROJECT_ID`, `CLOUD_SQL_INSTANCE` y `BACKUP_MAX_AGE_HOURS` (36 por defecto). Salida agregada `backup_check`, con retorno no-cero si falta inventario, falla el último backup o el último éxito está vencido. Su ejecución periódica y envío del JSON a Logging quedan como tarea del operador; no se presume programado ni activo. Una solicitud de backup no acredita `SUCCESSFUL`.

## Smoke autenticado y entrega de evidencia

`bash ops/smoke-production.sh` requiere `GCP_PROJECT_ID`, `GCP_REGION`, `API_SERVICE`, `PWA_SERVICE`; credenciales de una cuenta **sintética autorizada** `SMOKE_ADMIN_EMAIL`, `SMOKE_ADMIN_PASSWORD`, y `SMOKE_EXPECTED_ALEMBIC_REVISION` del SHA que se publica. Con dominio personalizado, definir también `SMOKE_PWA_URL` igual a `public_app_url`; el hostname generado `run.app` no sustituye el origen canónico del BFF. Deben llegar por variables/secretos del Environment, nunca argumentos, reportes o logs. La identidad WIF necesita invocación de API/lectura de servicios; no ampliar privilegios automáticamente ante un 403. API recibe ID token con audience del servicio y el producto se lee mediante cookie PWA. Si falta cualquiera de esas condiciones el smoke falla.

Se verifica login/me/logout cookie, `/health`, `/admin/operations`, revisión Alembic exacta y única, worker reciente, leases no vencidos, ausencia de dead letters y listado autorizado de atletas. Credenciales opcionales `SMOKE_COACH_EMAIL/PASSWORD` y `SMOKE_ATHLETE_EMAIL/PASSWORD` agregan lectura de listado y sesiones propias publicadas; cada par debe estar completo. El smoke imprime sólo resultado agregado. La lectura no garantiza publicación/confirmación ni entrega real de correo: esos recorridos requieren E2E y pruebas de proveedores independientes.

En deploy workflows mantener `workflow_dispatch` y mapear las credenciales desde GitHub Environment secrets y la revisión desde una variable verificada. No usar `.env` de otro proyecto. Guardar SHA → CI → digest → migración → revisión → URL → smoke/E2E con operador y UTC, sin cuerpos con PII. Un plan, test con mocks o job solicitado no acredita publicación ni disponibilidad real.

## Ensayo futuro de recuperación/PITR

1. Con autorización nueva, crear un testigo sintético por API, anotar hora UTC de escritura y verificar lectura. Guardar sólo ID/hash fuera de Git y nunca contenido real. Tomar/confirmar backup y punto PITR válidos; simular revocación/borrado posteriores para comprobar que su ledger se reaplica tras restaurar.
2. Anotar `incident_started_at` y último write recuperable; elegir `TARGET_INSTANCE` nuevo, mismo proyecto NODO y red privada. Revisar costo y permisos. `ops/restore-cloud-sql.sh` exige `CONFIRM_RESTORE=RESTORE_TO_NEW_INSTANCE`; un fallo de permisos al listar el destino bloquea el clon y nunca se interpreta como ausencia.
3. El script espera la operación PITR, confirma `RUNNABLE` y mide `provision_seconds`. Eso **no es RTO funcional** ni integridad del producto. No ejecutar downgrade ni cambiar el `DATABASE_URL` de producción automáticamente.
4. Montar API/worker aislados contra el clon con secretos acotados y acceso restringido. Comprobar Alembic/revisión, integridad, listados, testigo, conservación del FIT, 401/403, revocaciones y ausencia de datos que ya debían estar borrados. Reaplicar ledger de borrado/consent antes de cualquier exposición.
5. Medir RTO desde incidente hasta último readback funcional autorizado; medir RPO con el último testigo realmente recuperado, no con el timestamp solicitado al clon. Registrar `application_verified_at`, RTO/RPO observado, revisión, punto restaurado, resultado/hash del testigo, ajustes de privacidad, costo y responsable.
6. Restauración y rollback quedan pendientes hasta ejecutar esa prueba real. No borrar el clon/backup automáticamente. Conservar o limpiar únicamente tras decisión explícita del operador conforme a retención.

Fuentes primarias consultadas para el contrato: [ADC/IAM generativo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/access-control), [GCS soft delete](https://docs.cloud.google.com/storage/docs/soft-delete), [backupRuns y estados](https://docs.cloud.google.com/sql/docs/postgres/admin-api/rest/v1beta4/backupRuns), [PITR PostgreSQL](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/pitr), [recursos monitoreados](https://docs.cloud.google.com/monitoring/api/resources), [provider Google 7.46.1](https://github.com/hashicorp/terraform-provider-google/tree/v7.46.1/website/docs/r) y [mocks Terraform](https://developer.hashicorp.com/terraform/language/tests/mocking).

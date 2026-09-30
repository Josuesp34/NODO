# Validación de privacidad, Push y administración

Fecha: 2026-09-30. Base aislada: `b3eea4b`, rama `codex/privacidad-push`.
Las pruebas utilizaron cuentas, actividades, claves y pagos sintéticos. No hubo envíos a teléfonos,
operaciones de cobro ni creación, modificación o despliegue de recursos en Google Cloud.

## Evidencia local

| Verificación | Resultado |
| --- | --- |
| Ruff, `app migrations tests` | Correcto |
| Pytest completo, PostgreSQL 16 y SQLite con FK activas | 88 correctas, 1 omitida; dos avisos de deprecación del cliente de pruebas |
| Caso omitido | Carrera de cupos en SQLite: se ejecutó y pasó en PostgreSQL, que admite el bloqueo de fila requerido |
| Alembic PostgreSQL | `upgrade head`, `check`, `downgrade 0005_password_reset`, `upgrade head`, `check`: correctos |
| Frontend, TypeScript Web y Lab | Correcto |
| Frontend, pruebas Web | 38 correctas, incluidas cuatro pruebas Push nuevas |
| Build Web y Lab con Webpack | Correctos; Web se volvió a compilar tras el último cambio |
| Build habitual con Turbopack | Bloqueado en este worktree porque `node_modules` es un enlace externo; verificar la compilación habitual al integrar con dependencias locales |
| OSV, dependencias resueltas de `pywebpush==2.5.0` | 20 paquetes comprobados, sin hallazgos registrados en esta consulta |

La prueba de transporte utiliza la implementación real de pywebpush y cifrado `aes128gcm`, interceptando
la petición HTTP antes de salir: comprueba que no aparece el mensaje en claro, que no se siguen redirecciones
y que el timeout se aplica. Esto demuestra cifrado y contrato HTTP, no entrega a un dispositivo.
La resolución aislada usó `cryptography==50.0.2`; la base tenía `50.0.1`. La auditoría y suite de la
resolución final deben repetirse después de integrar requirements. No se modificó la `.venv` compartida.

## Casos cubiertos

- Preferencias por finalidad, zona horaria y silencio; suscripciones con endpoint y claves cifradas;
  outbox con sólo `delivery_id`; deduplicación por evento/dispositivo; 404/410 y expiración destruyen las claves.
- Revocación y revalidación bajo bloqueo del usuario; baja de dispositivos con permisos propios;
  revocar otro dispositivo conserva la suscripción de este navegador. El service worker ignora texto y URLs
  privados del payload y siempre abre `/app`.
- Consentimiento deportivo revocado impide uso futuro, cancela procesamiento, borra tokens y estados OAuth,
  y mantiene disponible la exportación de los datos propios anteriores. Exportar como coach no entrega
  recomendaciones, decisiones o chats de atletas cuyo acceso terminó.
- Borrado de atleta y coach con relaciones FK, sesiones, planes, telemetría, conversaciones derivadas y
  outbox relacionado; conservación de datos independientes de otras cuentas; registro financiero con identidad
  desidentificada; organización sin otro propietario activo suspendida.
- Borrado físico local idempotente y rechazo de rutas fuera del almacén privado; limpieza externa permanece
  en trabajos con reintento hasta que el adaptador confirma el borrado.
- Retención por fecha del hecho deportivo, no por `updated_at`; eliminación de fuentes y derivados, planes
  antiguos, perfiles cerrados, chats vacíos, tokens vencidos y outbox antiguo. Los trabajos de limpieza y
  revocación remota pendientes se conservan. Maintenance periódico tiene dedupe y bloqueo advisory en PostgreSQL.
- Catálogo administrativo autenticado, altas manuales, moneda/fechas, referencia de pago idempotente,
  cupos por organización y carrera real de reservas. Una segunda organización activa no evade la suspensión
  de la organización de la asignación.

## Integración requerida

1. Encadenar `0008_privacy_push` después de las migraciones paralelas: en esta rama depende de `0005_password_reset`.
2. Montar `app.api.privacy_routes.router` antes de product y retirar los handlers legacy duplicados de
   consentimientos, exportación/borrado y POST administrativos. Verificar OpenAPI además del orden de routing.
3. Añadir `pywebpush==2.5.0` a requirements y verificar la resolución final con la auditoría bloqueante de CI.
4. Integrar las settings acordadas: `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, `WEB_PUSH_CONTACT`,
   `PUSH_ENCRYPTION_KEY`, `PUSH_ENDPOINT_HOSTS`, `WEB_PUSH_TTL_SECONDS`, `RETENTION_JOB_INTERVAL_HOURS`,
   `RETENTION_OUTBOX_DAYS`, `PRIVACY_STORAGE_ROOT`, `PRIVACY_GCS_BUCKETS`; `DATA_RETENTION_DAYS` ya existe.
5. En `run_once`, ejecutar `await schedule_retention(db)` y confirmar antes de reclamar trabajos.
   `dispatch_privacy_job(db, job)` atiende `send_web_push`, `privacy_retention`, `privacy_delete_file`
   y `privacy_delete_user_files`. `PushDeferred` conserva el nuevo `run_after`, vuelve a pending sin
   consumir intento y libera lease sin rollback; usar las comprobaciones de dueño/token del worker.
6. Enlazar `queue_notification(db, user_id=..., category=..., event_key=...)` antes del commit del evento:
   publicación de plan → atleta; revisión/propuesta/molestia → coach; error de sincronización → atleta.
   La función no hace commits. La categoría reminder admite eventos con clave estable; no incluye un
   calendario automático de recordatorios diarios en esta rama.
7. Integrar `object_store.delete_athlete_files` y `prune_expired_files`; deben borrar todos los objetos y
   versiones del usuario en el almacenamiento configurado. Registrar otros archivos con `register_artifact`.
   El handler falla y conserva reintento si el adaptador no está disponible; no informa limpieza completada.
8. Integrar `intervals_real.queue_remote_disconnect` antes de borrar tokens. El job de revocación remota
   conserva sólo el token cifrado y se elimina después de confirmar la revocación; no lleva IDs del usuario.
9. Repetir suite y ciclo Alembic combinado con los modelos nuevos de proveedores. El selector administrativo
   usa entidades autorizadas del servidor; no admite introducir identificadores numéricos arbitrarios.

## Pendientes operativos y límites

- Recepción real de Push con teléfono/cuenta consentidos, claves VAPID de cada entorno y HTTPS.
  La cola deduplica filas y el tag agrupa avisos visibles; una caída entre envío y commit puede repetir
  el transporte, que tiene semántica de al menos una entrega. No se afirma exactamente una entrega de red.
- Una cuenta distinta no puede transferir un endpoint existente. En un dispositivo compartido debe
  darse de baja la suscripción del navegador y crear una nueva para la cuenta actual.
- Escenarios específicos precompetencia y dashboard comercial de costos IA no fueron implementados
  por este paquete. Las métricas de comparación genéricas y el calendario de competencias no prueban esos escenarios.
- Aviso de privacidad definitivo, duración/base de conservación financiera, recuperación y vencimiento
  efectivo de backups requieren decisiones y pruebas independientes. Los backups no se reescriben al borrar una cuenta.
- La exportación es JSON autenticado de datos estructurados y chats propios; no es un archivo ZIP de FIT.
  Un JSON ya descargado o una copia en otro dispositivo no puede retirarse a distancia.
- La UI limpia el cache del dispositivo donde se revoca o borra; la invalidación entre pestañas y expiración
  offline se integra en el carril raíz. Verificar el comportamiento tras reconexión de otro dispositivo.
- Google Cloud queda pendiente para Josué por instrucción expresa de Brandon; este documento no es evidencia
  de despliegue ni de pruebas de almacenamiento remoto.

API del proveedor verificada en [pywebpush](https://github.com/web-push-libs/pywebpush),
versión consultada en [PyPI](https://pypi.org/project/pywebpush/), y contrato del navegador en
[PushManager.subscribe](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe).

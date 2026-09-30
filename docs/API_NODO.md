# API NODO v1

Actualizado: 30 de septiembre de 2026.

La API FastAPI es la fuente de verdad para NODO y NODO Lab. El contrato ejecutable está en `/docs` cuando el servidor está activo. Este documento describe capacidades y permisos; los schemas exactos se consultan en OpenAPI.

Base del backend: `/api/v1`. La PWA accede por `/api/nodo/<ruta>` y por los handlers `/api/session/*`; no conecta desde JavaScript directamente a Cloud Run privado. Los endpoints de esta página se expresan relativos a la base del backend, salvo donde se indica PWA.

Estado: contratos implementados y comprobados con datos sintéticos. Esto no acredita despliegue ni disponibilidad externa de correo, OAuth, Vertex o Web Push. La preparación operativa está en [RUNBOOK_PROVEEDORES_OPERACION.md](RUNBOOK_PROVEEDORES_OPERACION.md); Google Cloud queda pendiente de ejecución autorizada por Josué.

## Identidad y sesión

| Acción | Endpoint | Acceso |
|---|---|---|
| Alta local de coach | `POST /auth/coaches` | Sólo desarrollo con bandera explícita |
| Bootstrap de superusuario | `POST /auth/superusers` | Sólo desarrollo, bandera y secreto |
| Login / refresh / logout | `POST /auth/login`, `/refresh`, `/logout` | Cuenta válida |
| Identidad actual | `GET /auth/me`, `/identity` | Sesión |
| Invitar/listar atletas | `POST/GET /auth/athletes` | Coach |
| Activar atleta | `POST /auth/athletes/activate` | Código de un solo uso |
| Solicitar recuperación | `POST /auth/password-reset/request` | Pública; respuesta genérica `202` |
| Confirmar recuperación | `POST /auth/password-reset/confirm` | Correo, código y nueva contraseña |
| Revocar asignación | `DELETE /auth/athletes/{athlete_id}` | Coach asignado |
| Añadir rol | `POST /auth/users/{user_id}/roles/{role}` | Superusuario |

La PWA no recibe tokens en JavaScript: el BFF guarda acceso y refresh en cookies `httpOnly`, `SameSite=Lax` y `Secure` fuera de la demo HTTP loopback explícita. Refresh rota la sesión y logout la revoca. La autenticación IAM del servicio viaja por `X-Serverless-Authorization`; `Authorization` conserva la sesión de NODO.

Las escrituras del BFF exigen `Origin` canónico y rechazan origen ausente/diferente o Fetch Metadata de otro sitio con `403`, antes de llamar al backend. El cuerpo se lee con un límite incremental que no confía en `Content-Length`: sesión 16 KiB, JSON 1 MiB y FIT 10 MiB más 64 KiB de multipart por defecto. Son configurables mediante `NODO_BFF_SESSION_MAX_BYTES`, `NODO_BFF_JSON_MAX_BYTES` y `NODO_BFF_FIT_MAX_BYTES`; el backend mantiene su propio límite FIT. Un cuerpo excedido recibe `413` y un tamaño declarado inconsistente recibe `400`.
En producción la invitación requiere correo configurado y devuelve `invitation_token: null`; el código se encola cifrado para Resend. En desarrollo sin correo configurado se conserva la entrega manual de código. Recuperación requiere correo configurado, expira en 30 minutos, limita reenvíos a 15 minutos, invalida el código tras usarlo y revoca todas las sesiones previas. La cola confirma aceptación, no entrega final.

## Planificación

Los bloques y sesiones cuelgan de `/athletes/{athlete_id}`.

| Acción | Endpoint |
|---|---|
| Crear/listar bloques | `POST/GET /blocks` |
| Crear/listar sesiones | `POST/GET /workouts` |
| Editar borrador | `PUT /workouts/{workout_id}` |
| Publicar | `POST /workouts/{workout_id}/publish` |

Edición y publicación usan `expected_version`; una copia obsoleta recibe `409`. El atleta sólo puede leer sesiones publicadas. Los pasos y sus objetivos conservan tipo, duración/distancia, repeticiones y unidades; la planificación manual continúa disponible cuando falla un proveedor.

## Perfil, contexto y seguimiento

- `GET/PUT /athletes/{athlete_id}/profile`
- `GET /athletes/{athlete_id}/profile/history`
- `GET/POST /athletes/{athlete_id}/competitions`
- `PUT/DELETE /athletes/{athlete_id}/competitions/{competition_id}`
- `GET/POST /athletes/{athlete_id}/observations`
- `GET /athletes/{athlete_id}/checkins`
- `PUT /athletes/{athlete_id}/checkins/{local_date}`
- `GET/POST /athletes/{athlete_id}/complaints`
- `POST /complaints/{complaint_id}/updates`
- `GET /complaints/{complaint_id}`
- `GET /review-items`
- `POST /review-items/{item_id}/decision`

## Actividades y FIT

- `POST /athletes/{athlete_id}/activities/fit`: importación autenticada.
- `GET /athletes/{athlete_id}/activities`: historial con `limit` (1–100), `offset`, `X-Total-Count` y `X-Next-Offset`.
- `GET /athletes/{athlete_id}/activities/page`: página `{items,total,next_offset}`.
- `GET /athletes/{athlete_id}/activities/{activity_id}`: detalle, laps y cantidad de puntos de telemetría.
- `PUT /athletes/{athlete_id}/activities/{activity_id}/link`: vínculo explícito a una sesión publicada de la misma disciplina, con `expected_version`; `null` desvincula.
- `GET /athletes/{athlete_id}/activities/comparison?start&end`: comparación canónica en días locales del atleta, hasta 93 días inclusivos.
- `GET /athletes/{athlete_id}/activities/{activity_id}/file`: descarga privada del original `manual_fit`, con permiso y consentimiento revalidados, sin URL pública o firmada.
- `POST /upload-fit/`: ruta heredada cerrada con `410`.

FIT valida extensión, contenido, una sola sesión y límite de 10 MiB; deduplica por atleta/hash, conserva laps/telemetría y encola carga diaria. La persistencia del original debe completarse antes de confirmar una importación fuera de desarrollo; un fallo de almacenamiento devuelve `503` y revierte los registros. La descarga usa `private, no-store`, `nosniff` y nombre fijo. La comparación usa datos compatibles y vínculo confirmado: devuelve estados de datos insuficientes, falta de sincronización, disciplinas incompatibles o varias actividades ambiguas, sin inferir incumplimiento ni un triatlón desde archivos separados.

Las operaciones deportivas exigen `training_data_processing` vigente. Desarrollo admite fixtures sin consentimiento; nunca permite una revocación explícita. La asignación de coach no concede acceso a otra cuenta y su revocación invalida lecturas posteriores.

## Grupos, plantillas y recomendaciones

- `POST/GET /groups`
- `POST/GET /groups/{group_id}/members`
- `PUT/DELETE /groups/{group_id}/members/{athlete_id}`
- `POST/GET /templates`
- `PUT /templates/{template_id}` y `GET /templates/{template_id}/assignments`
- `POST /templates/{template_id}/apply`
- `POST/GET /recommendations`
- `POST /recommendations/{recommendation_id}/decision`

La aplicación de plantillas es idempotente. Las recomendaciones protegen la versión base del plan.

## Privacidad y cuenta

- `GET /privacy/purposes`: finalidades y versión aceptada por el servidor.
- `POST/GET /consents`
- `DELETE /consents/{consent_id}`
- `GET /account/export`
- `DELETE /account`
- `GET /account/retention`
- `GET/PUT /notification-preferences`
- `GET/POST /push-subscriptions`
- `DELETE /push-subscriptions/{subscription_id}`
- `POST /admin/privacy/retention`: superusuario; agenda barrido idempotente (`202`).

Las finalidades aceptadas son `training_data_processing`, `ai_assistant` y `web_push`, versión `pilot-v1`; el servidor rechaza nombres/versiones arbitrarios. Revocar procesamiento deportivo cancela trabajos vinculados, elimina credenciales del proveedor y agenda su desconexión remota cifrada. El export de cuenta y las opciones de consentimiento continúan disponibles para la persona tras retirar una finalidad o suspender la organización.

Eliminar la cuenta exige contraseña y `confirmation: "ELIMINAR MI CUENTA"`. Borra relaciones operativas y sesiones, desidentifica la identidad necesaria para relaciones financieras y agenda limpieza física de archivos. `204` acredita aceptación, no que todos los trabajos remotos o backups ya desaparecieron. Los handlers de almacenamiento eliminan cada generación vigente/no actual; los fallos conservan el trabajo para reintento. La retención deportiva usa fecha del evento; los originales se rigen por creación/ingesta del archivo y la política de Storage. Las ventanas y la reaplicación de borrados tras restore están en el runbook.

Web Push requiere consentimiento propio, permiso del navegador y claves VAPID/configuración válida. Sólo acepta endpoints HTTPS de hosts autorizados, cifra la suscripción, respeta preferencias/horarios y envía texto genérico sin métricas ni nombres. El envío se encola y se revalida antes del transporte; una suscripción ajena no puede revocarse desde otra cuenta. La recepción en dispositivos reales sigue pendiente.

## Comercial administrado

- `POST /admin/commercial/plans`
- `POST /admin/commercial/subscriptions`
- `POST /admin/commercial/payments`
- `GET /admin/commercial/catalog` y `GET /commercial/status`
- `PATCH /admin/organizations/{organization_id}`
- `PATCH /admin/commercial/subscriptions/{subscription_id}`

Las escrituras administradas y el catálogo requieren superusuario; el estado comercial se lee con la sesión correspondiente. Registra acuerdos manuales; no procesa tarjetas ni inventa precio. Una organización/suscripción suspendida no puede seguir operando rutas deportivas bajo su asignación; las rutas de privacidad permanecen accesibles.

## Asistentes

- `POST /assistant/threads`
- `GET /assistant/threads?role=coach|athlete`
- `POST /assistant/threads/{thread_id}/messages`
- `POST /assistant/threads/{thread_id}/messages/stream`: SSE con eventos `run`, resultado final validado o error; no publica fragmentos sin validar.
- `GET /assistant/threads/{thread_id}/messages`
- `POST /assistant/tools/read?role=coach|athlete`
- `GET /assistant/threads/{thread_id}/confirmations`
- `POST /assistant/confirmations/{confirmation_id}`
- `POST /assistant/runs/{run_id}/cancel`
- `GET /assistant/status`

Ambos roles usan conversaciones persistidas. `ai_assistant` y el consentimiento deportivo de cada atleta consultado son obligatorios; permisos y evidencia se revalidan también al leer historial o reutilizar un resultado. Herramientas tipadas: perfil, calendario, actividades, comparación, observaciones, resumen, molestias, revisión, grupos y calidad. Contexto/historial tienen límites y señalan ausencia/truncamiento; las citas salen de lecturas autorizadas de NODO.

`request_key` evita duplicar un run de la misma conversación; reutilizarla con otro payload produce `409`. Las escrituras permitidas sólo generan preview tipado: molestia propia del atleta o borrador de sesión del coach. La confirmación exige hash vigente, expiración, permisos y versión base; consumida una vez, repetir no duplica la escritura. La IA no publica sesiones ni escribe métricas deportivas.

Existe adaptador Vertex por ADC y proveedor determinista `simulated`; Vertex requiere modelo, ubicación, tarifas y topes positivos configurados explícitamente. Antes de llamar se reserva cuota mensual de solicitudes/tokens/microUSD por usuario y organización; fallos/cancelaciones conservan una reserva prudente. `GET /assistant/status` devuelve uso agregado estimado, no factura. Timeout, salida inválida, agotamiento de presupuesto y cancelación dejan las herramientas manuales disponibles. La llamada real, gasto y política de tratamiento externa quedan pendientes para Josué.

## Intervals.icu real

- `POST /connections/intervals/{athlete_id}/authorize`: sólo el atleta dueño; entrega URL de autorización y scopes.
- `POST /connections/intervals/callback`: cuerpo `state`, `code` o `error`, con la sesión que inició autorización.
- `GET /connections/intervals/{athlete_id}`: estado, último sync, scopes y estado de trabajo; sin credenciales.
- `POST /connections/intervals/{athlete_id}/sync`: solicita trabajo durable (`202`).
- `DELETE /connections/intervals/{athlete_id}`: desconexión remota y cancelación local; preserva FIT manual.
- `POST /connections/intervals/webhook`: relay de servicio con cuerpo autenticado del proveedor, no sesión de usuario.

El callback público es la página PWA `/athlete/connections/intervals/callback`; el navegador conserva la sesión `SameSite=Lax` y entrega el código al backend a través del BFF. El webhook público es `/api/providers/intervals/webhook` en la PWA, que relayea con IAM a la API privada. No exponer `/api/v1` con `allUsers` para resolver callbacks.

Estado OAuth ligado a sesión, vencimiento de cinco minutos y consumo único; el código se intercambia una vez y el token se cifra en reposo. Scopes mínimos de lectura: `ACTIVITY:READ`, `WELLNESS:READ`, `CALENDAR:READ`; no se publican entrenamientos externos. El contrato oficial no ofrece refresh token: ante credencial inválida se marca `reconnect_required` y se pide autorizar de nuevo.

El webhook compara `secret` del cuerpo en tiempo constante, limita tamaño a 1 MiB y eventos a 100, identifica al atleta por conexión vigente y deduplica eventos. No se inventa una firma HMAC. Backfill de 90 días y sincronización periódica trabajan por ventanas, conservan origen/calidad y revalidan autorización antes de persistir. Datos Strava u orígenes no admitidos se excluyen; los intervalos externos no se presentan como laps FIT. Desconexión fallida conserva un trabajo cifrado para reintento sin reactivar ingesta. Las escrituras heredadas `POST/DELETE /athletes/{athlete_id}/connections/intervals` devuelven `410` y señalan la ruta nueva; el `GET` heredado permite consultar estado histórico. La PWA real usa las rutas nuevas.

OAuth, webhook, backfill y desconexión tienen pruebas de contratos HTTP, pero la app del proveedor, credenciales, términos y recorrido contra Intervals real siguen pendientes. FIT es respaldo permanente.

## Operación y errores

`GET /admin/operations` requiere superusuario: devuelve revisiones Alembic, heartbeat reciente y cola agregada por tipo/estado, sin payloads. `GET /health` comprueba conexión de sólo lectura a PostgreSQL; `503` no expone detalles internos. El smoke autenticado verifica revisión esperada única, worker reciente y ausencia de leases vencidos/dead letters; sus credenciales son sintéticas y llegan por Environment secrets.

Los clientes distinguen `401` (sesión), `403` (finalidad/rol/suspensión), `404` (recurso inaccesible o ausente), `409` (versión/idempotencia/conexión), `413` (tamaño), `422` (contrato), `429` (cuota) y `503` (servicio/configuración/proveedor). Datos externos son datos, nunca instrucciones que conceden permisos.

## Validación externa pendiente

- correo Resend y recuperación implementados en código, pero no operativos hasta verificar dominio, secretos y envío real;
- Web Push implementado; faltan configuración y recepción comprobada en dispositivos;
- Vertex implementado; faltan proyecto ADC autorizado, modelo/tarifas/topes aprobados y llamada real;
- Intervals.icu real implementado; faltan registro/secretos y OAuth/sync/webhook/desconexión reales;
- comparación y workflows manuales implementados; el release debe conservar su evidencia E2E;
- infraestructura preparada en código, no desplegada.

El inventario completo y sus estados están en [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md).

# API NODO v1

Actualizado: 23 de septiembre de 2026.

La API FastAPI es la fuente de verdad para NODO y NODO Lab. El contrato ejecutable está en `/docs` cuando el servidor está activo. Este documento describe capacidades y permisos; los schemas exactos se consultan en OpenAPI.

Base: `/api/v1`.

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

La PWA no recibe tokens en JavaScript: el BFF guarda acceso y refresh en cookies `httpOnly`. Refresh rota la sesión y logout la revoca.
En producción la invitación requiere correo configurado y devuelve `invitation_token: null`; el código se encola cifrado para Resend. En desarrollo sin correo configurado se conserva la entrega manual de código. Recuperación requiere correo configurado, expira en 30 minutos, limita reenvíos a 15 minutos, invalida el código tras usarlo y revoca todas las sesiones previas. La cola confirma aceptación, no entrega final.

## Planificación

Los bloques y sesiones cuelgan de `/athletes/{athlete_id}`.

| Acción | Endpoint |
|---|---|
| Crear/listar bloques | `POST/GET /blocks` |
| Crear/listar sesiones | `POST/GET /workouts` |
| Editar borrador | `PUT /workouts/{workout_id}` |
| Publicar | `POST /workouts/{workout_id}/publish` |

Edición y publicación usan `expected_version`; una copia obsoleta recibe `409`. El atleta sólo puede leer sesiones publicadas.

## Perfil, contexto y seguimiento

- `GET/PUT /athletes/{athlete_id}/profile`
- `GET/POST /athletes/{athlete_id}/competitions`
- `GET/POST /athletes/{athlete_id}/observations`
- `PUT /athletes/{athlete_id}/checkins/{local_date}`
- `GET/POST /athletes/{athlete_id}/complaints`
- `POST /complaints/{complaint_id}/updates`
- `GET /review-items`
- `POST /review-items/{item_id}/decision`

## Actividades y FIT

- `POST /athletes/{athlete_id}/activities/fit`: importación autenticada.
- `GET /athletes/{athlete_id}/activities`: historial básico.
- `POST /upload-fit/`: ruta heredada cerrada con `410`.

FIT valida extensión, contenido, una sola sesión y límite de 10 MiB; deduplica por atleta/hash, conserva laps/telemetría y encola carga diaria. Fuera de desarrollo exige consentimiento vigente.

## Grupos, plantillas y recomendaciones

- `POST/GET /groups`
- `POST/GET /groups/{group_id}/members`
- `POST/GET /templates`
- `POST /templates/{template_id}/apply`
- `POST/GET /recommendations`
- `POST /recommendations/{recommendation_id}/decision`

La aplicación de plantillas es idempotente. Las recomendaciones protegen la versión base del plan.

## Privacidad y cuenta

- `POST/GET /consents`
- `DELETE /consents/{consent_id}`
- `GET /account/export`
- `DELETE /account`

Eliminar la cuenta requiere contraseña y desidentifica al usuario después de borrar o revocar sus datos operativos y sesiones.

## Comercial administrado

- `POST /admin/commercial/plans`
- `POST /admin/commercial/subscriptions`
- `POST /admin/commercial/payments`

Sólo superusuario. Registra acuerdos manuales; no procesa tarjetas ni inventa precio.

## Asistentes

- `POST /assistant/threads`
- `POST /assistant/threads/{thread_id}/messages`
- `GET /assistant/threads/{thread_id}/messages`
- `POST /assistant/confirmations/{confirmation_id}`

Actualmente funciona con proveedor determinista `simulated`. Las escrituras permitidas generan preview, hash, expiración y requieren confirmación explícita. No existe adaptador de modelo real aprobado.

## Intervals.icu

- `GET /athletes/{athlete_id}/connections/intervals`: consulta estado persistido o `not_connected`.
- `POST /athletes/{athlete_id}/connections/intervals`: persiste modo simulado o `authorization_pending`.
- `DELETE /athletes/{athlete_id}/connections/intervals`: revoca y elimina tokens persistidos.

No hay todavía inicio/callback OAuth, webhook ni backfill. La documentación vigente del proveedor no publica refresh token; si un token deja de ser válido, NODO debe marcar la conexión caída y pedir reconexión. El modo real no debe ofrecerse como operativo.

## Límites vigentes

- correo Resend y recuperación implementados en código, pero no operativos hasta verificar dominio, secretos y envío real;
- sin notificaciones Web Push;
- IA real no integrada/configurada;
- Intervals.icu real incompleto;
- sin comparación completa prescrita vs. ejecutada en una pantalla;
- infraestructura preparada en código, no desplegada.

El inventario completo y sus estados están en [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md).

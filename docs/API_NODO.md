# API inicial de NODO y NODO Lab

Esta API es la fuente de datos única de NODO y NODO Lab. El contrato se encuentra en `/docs` cuando el servidor está activo. La versión inicial es `/api/v1`; no cambiar contratos publicados de forma incompatible sin introducir versión o un periodo de compatibilidad.

## Flujo de identidad

1. En desarrollo, crear un entrenador con `POST /auth/coaches` tras activar `ALLOW_COACH_REGISTRATION=true`.
2. Iniciar sesión con `POST /auth/login`. La respuesta entrega un token de acceso breve y un token de renovación.
3. Incluir el token de acceso en `Authorization: Bearer <token>`.
4. El entrenador crea una invitación con `POST /auth/athletes`.
5. El atleta activa su cuenta con `POST /auth/athletes/activate` y define su contraseña.

Para el equipo de desarrollo existe `POST /auth/superusers`. Sólo responde en `development` si `ALLOW_SUPERUSER_BOOTSTRAP=true` y el header `X-NODO-Development-Key` coincide con `DEV_SUPERUSER_BOOTSTRAP_TOKEN`. La clave vive únicamente en `.env`. El superusuario es una capacidad administrativa de aplicación; no sustituye los futuros roles múltiples de entrenador y atleta.

El endpoint de invitación devuelve el token en la respuesta únicamente durante esta fase de desarrollo. La aplicación móvil no debe almacenarlo después de activar la cuenta. Antes del piloto externo, sustituir ese retorno por un canal de entrega verificado y agregar recuperación de contraseña.

`POST /auth/refresh` rota el token de renovación: un token que ya se usó deja de servir. `POST /auth/logout` revoca la sesión actual. NODO almacena tokens opacos solo en su forma resumida en la base de datos; la aplicación debe guardarlos en almacenamiento seguro de cada plataforma, no en logs ni URLs.

## Planificación

Los endpoints cuelgan de `/athletes/{athlete_id}`.

| Acción | Endpoint | Quién puede hacerlo |
|---|---|---|
| Crear bloque | `POST /blocks` | Entrenador asignado |
| Consultar bloques | `GET /blocks` | Entrenador asignado o atleta dueño |
| Crear sesión | `POST /workouts` | Entrenador asignado |
| Consultar sesiones | `GET /workouts?start=YYYY-MM-DD&end=YYYY-MM-DD` | Entrenador asignado o atleta dueño |
| Reemplazar borrador | `PUT /workouts/{workout_id}` | Entrenador asignado |
| Publicar sesión | `POST /workouts/{workout_id}/publish` | Entrenador asignado |

Una sesión contiene pasos explícitos: calentamiento, trabajo, recuperación o vuelta a la calma; cada paso tiene duración o distancia, y opcionalmente un objetivo de ritmo, potencia, frecuencia cardiaca o esfuerzo percibido. Un grupo de pasos tiene repeticiones, por lo que el contrato expresa intervalos sin depender de texto libre.

Las modificaciones y publicaciones requieren `expected_version`. Si el calendario cambió desde que se abrió en NODO Lab, el servidor responde `409`; la interfaz debe refrescar y pedir una decisión, no sobrescribir el cambio de otra persona.

## Límites actuales

- No hay aún organizaciones con varios entrenadores, notificaciones, recuperación de contraseña ni correo de invitación.
- El atleta se vincula a un entrenador. La asociación con equipos llegará antes del piloto de varios coaches.
- La importación FIT vigente sigue siendo un prototipo local, separada de esta identidad. El siguiente bloque la asociará a un atleta autenticado e incorporará deduplicación.
- Las sesiones se guardan con pasos JSON validados. La comparación contra vueltas FIT todavía no está implementada.
- No usar credenciales reales en el archivo `.env` ni tokens de API en documentación, capturas o commits.

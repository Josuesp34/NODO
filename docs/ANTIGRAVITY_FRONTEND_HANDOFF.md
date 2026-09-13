# Relevo de frontend para Antigravity

Actualizado: 13 de septiembre de 2026. Este documento es la fuente de contexto para iniciar el desarrollo visual sin alterar los límites del MVP.

## Producto y decisión arquitectónica

NODO ayuda al atleta a ejecutar, registrar cómo se siente y revisar su entrenamiento desde el teléfono. NODO Lab permite al entrenador organizar atletas, crear planes por bloques, editar sesiones estructuradas y publicarlas. La inteligencia artificial será un copiloto que propone cambios para aprobación del entrenador; no toma decisiones ni modifica planes por sí sola.

El repositorio es un monorepo. Hay dos aplicaciones con una API y cuentas compartidas:

- `frontend/apps/nodo-lab`: Next.js, uso de escritorio para entrenadores.
- `frontend/apps/nodo-mobile`: Expo/React Native, uso móvil para atletas.
- `frontend/packages/api-client`: tipos y cliente HTTP común. Compartir contratos y lógica sin interfaz; no intentar reutilizar pantallas web en React Native.
- `backend/fit-parser`: API FastAPI, PostgreSQL/TimescaleDB y migraciones Alembic.

La marca se escribe **NODO** para el atleta y **NODO Lab** para el entrenador.

## Estado comprobado hoy

El backend ya implementa autenticación, sesiones opacas con rotación de refresh token, relación entrenador-atleta, invitaciones de atleta, bloques y sesiones estructuradas con publicación y control de versión. La autorización se comprueba en el servidor; la interfaz no debe sustituirla con ocultar botones.

También existe `is_superuser` para el equipo de desarrollo. Se crea sólo mediante el bootstrap local protegido descrito en `API_NODO.md`; es una capacidad de plataforma y se mantiene separada de la futura combinación de capacidades de atleta y entrenador.

Docker funciona en este equipo:

- API: `http://127.0.0.1:8000`
- Swagger/OpenAPI: `http://127.0.0.1:8000/docs`
- Health: `GET http://127.0.0.1:8000/health` responde `200`.
- TimescaleDB: `localhost:5433`; el puerto 5432 está ocupado por otro proceso local.
- Servicios: desde `backend/fit-parser`, `docker compose up -d`.
- Migración: `backend/fit-parser/.venv/Scripts/alembic.exe -c alembic.ini upgrade head`.

Las 35 pruebas actuales del backend pasan con `backend/fit-parser/.venv/Scripts/python.exe -m pytest backend/fit-parser/tests -q`. La API Docker y CORS para `http://localhost:3000` se validaron hoy.

## Estado del frontend

Existe una base mínima, deliberadamente sin pantallas de producto terminadas:

- NODO Lab tiene inicio/cierre de sesión real en `frontend/apps/nodo-lab/src/app/page.tsx`: usa `/auth/login`, `/auth/me`, `/auth/refresh` y `/auth/logout`; la sesión se limita a `sessionStorage` durante el prototipo.
- NODO móvil muestra la pantalla de entrenamiento del día en `frontend/apps/nodo-mobile/app/index.tsx`.
- `NodoApiClient` contiene un `GET` tipado y la lectura de sesiones; debe evolucionar junto al contrato de backend.
- Las URLs se configuran en `frontend/.env.example`. Cada aplicación debe tener su `.env.local`, que no se versiona.

La instalación de dependencias no se cerró porque OneDrive bloqueó directorios temporales de Expo durante `npm install`. `frontend/node_modules` está ignorado y no es parte del repositorio. Antes de trabajar, pausar la sincronización de OneDrive o cerrar procesos que usen esa carpeta, borrar el `node_modules` incompleto y ejecutar desde `frontend`:

```powershell
npm install
npm run typecheck
npm run dev:lab
npm run dev:mobile
```

La raíz usa npm workspaces. Los paquetes internos se enlazan con `file:../../packages/api-client`, no con `workspace:*`, porque esa sintaxis falló en la instalación de este entorno. Cuando la instalación termine, generar y versionar `frontend/package-lock.json` para fijar dependencias; actualmente no existe lockfile.

Para probar NODO en un teléfono físico, `localhost` no apunta a la laptop. Cambiar `EXPO_PUBLIC_NODO_API_URL` por la IP LAN de la laptop, conservar `/api/v1`, usar la misma red Wi-Fi y permitir el puerto 8000 en el firewall sólo para desarrollo local.

## Contrato que el frontend debe consumir

La base siempre es `NEXT_PUBLIC_NODO_API_URL` o `EXPO_PUBLIC_NODO_API_URL`, por ejemplo `http://127.0.0.1:8000/api/v1`. Consultar la especificación viva en `/docs` y el detalle en `docs/API_NODO.md` antes de añadir tipos.

### Identidad

| Caso | Endpoint | Interfaz esperada |
|---|---|---|
| Bootstrap local de entrenador | `POST /auth/coaches` | Sólo una pantalla/dev tool local; el endpoint estará cerrado fuera de desarrollo. |
| Inicio de sesión | `POST /auth/login` | Formulario de correo y contraseña. La respuesta contiene `access_token` y `refresh_token`. |
| Sesión actual | `GET /auth/me` | Resolver rol y sesión al abrir la app. |
| Renovar sesión | `POST /auth/refresh` | Al recibir 401, renovar una vez y repetir la petición original; el refresh anterior queda invalidado. |
| Cerrar sesión | `POST /auth/logout` | Revocar la sesión y borrar ambos tokens. |
| Invitar atleta | `POST /auth/athletes` | Acción de NODO Lab. La respuesta entrega un token sólo para desarrollo. |
| Activar atleta | `POST /auth/athletes/activate` | Flujo móvil: token de invitación + contraseña, luego guardar la sesión. |

Enviar `Authorization: Bearer <access_token>` en todas las rutas protegidas. No guardar tokens en URL, logs, analytics o estado persistido sin protección. Para NODO móvil usar almacenamiento seguro de Expo; para NODO Lab decidir una estrategia de sesión antes del piloto. No exponer el token de invitación tras activarlo.

### Planeación

Todas las rutas siguientes cuelgan de `/athletes/{athlete_id}`:

| Caso | Endpoint | Regla de UI |
|---|---|---|
| Crear/listar bloques | `POST`/`GET /blocks` | El bloque tiene título, fecha de inicio y fecha de fin. |
| Crear/listar sesiones | `POST /workouts`, `GET /workouts?start=YYYY-MM-DD&end=YYYY-MM-DD` | Mostrar calendario por atleta y consultar por rango. |
| Sustituir borrador | `PUT /workouts/{workout_id}` | Requiere `expected_version`; sólo permite estado `draft`. |
| Publicar sesión | `POST /workouts/{workout_id}/publish` | Requiere `expected_version`; después ya no se edita en esta versión. |

Cada sesión requiere `title`, `scheduled_date`, `sport_type` y `steps`. Los pasos son grupos con `repetitions` y una lista ordenada de pasos `warmup`, `work`, `recovery` o `cooldown`. Cada paso usa duración o distancia y puede incluir un objetivo tipado de ritmo, potencia, frecuencia cardiaca o RPE. Usar formularios estructurados; no reducir la sesión a un campo de texto libre.

Si llega `409`, el plan se modificó desde que se abrió: refrescar datos y pedir al entrenador decidir. Mostrar los errores `401`, `403`, `404`, `409` y `422` con un mensaje específico. No hacer reintentos automáticos de una publicación o edición conflictiva.

## Primeras pantallas que sí corresponden al MVP

### NODO Lab

1. Inicio de sesión y cierre de sesión.
2. Lista de atletas del entrenador. El backend aún no expone un endpoint dedicado de listado; no inventarlo. Para el primer corte, construir la navegación y dejar el origen como una tarea de backend claramente identificada.
3. Perfil/calendario de un atleta: bloques y sesiones por intervalo.
4. Editor de bloque y de sesión estructurada en borrador.
5. Vista previa y publicación con manejo de versión.
6. Invitación de atleta, presentada como enlace/código de desarrollo, no como correo real.

### NODO móvil

1. Activación por invitación e inicio de sesión.
2. Entrenamiento del día y calendario de sesiones publicadas del propio atleta.
3. Estado vacío claro cuando no hay sesión publicada.
4. Preparar rutas de navegación para check-in y recuperación, pero no simular persistencia: sus endpoints no existen todavía.

## Lo que no está implementado

No construir una interfaz que finja que estas capacidades ya funcionan:

- Sincronización Garmin, Apple Health, Health Connect, Polar, COROS u otros relojes.
- Check-ins de recuperación, sueño, HRV, FC de reposo o estrés.
- Registro, revisión o alertas de molestias físicas.
- Equipos u organizaciones con varios entrenadores.
- Recuperación de contraseña, envío de correo y entrega segura de invitaciones.
- Asociación de actividades FIT a atleta, deduplicación e interpretación de laps.
- Notificaciones, pagos, copiloto de IA, predicción de pico o cambios automáticos del plan.

El frontend puede diseñar espacios y estados vacíos para esos flujos, pero debe etiquetarlos como próximos y no persistir datos falsos. Para datos de salud futuros, NODO móvil integrará adaptadores nativos con consentimiento explícito; NODO Lab consumirá sólo información consolidada desde el backend.

## Orden recomendado de implementación

1. Terminar instalación, añadir lockfile y verificar `typecheck`.
2. Completar `@nodo/api-client` con tipos de bloques y métodos de planeación `POST`/`PUT` tipados.
3. Implementar sesión y guardado seguro de tokens en NODO móvil.
4. Construir NODO Lab: calendario y editor estructurado de borradores.
5. Construir NODO móvil: activación, sesión y vista de entrenamiento publicado.
6. Añadir pruebas de UI/cliente para refresh, 409 y restricciones por rol.
7. Pedir al backend el endpoint de lista de atletas antes de implementar una lista con datos reales.

No modificar esquemas de backend ni añadir una biblioteca de estado, componentes o autenticación externa sin justificarlo en un PR. Mantener cambios pequeños y acompañar cualquier endpoint nuevo con documentación, tipos y pruebas.

## Archivos de referencia

- `docs/API_NODO.md`: contrato actual de API.
- `docs/ARQUITECTURA.md`: entidades y límites futuros.
- `docs/ESTADO_TECNICO.md`: decisiones y validación del backend.
- `frontend/README.md`: comandos de desarrollo.
- `backend/fit-parser/tests/api/test_identity_and_planning.py`: flujos reales de autenticación, invitación, permisos, publicación y conflictos.

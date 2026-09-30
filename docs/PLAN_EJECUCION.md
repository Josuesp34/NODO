# NODO — Plan de ejecución hasta producto completo

Versión 2.0 · 17 de septiembre de 2026
Repositorio: `github.com/Josuesp34/NODO` · rama de integración `dev`

**Qué es este documento.** El plan que una sesión de Claude ejecuta fase por fase para llevar NODO de
«fundación de MVP» a producto completo desplegado. Brandon y Josué validan funcionalidad al cierre de
cada fase y son los únicos que cruzan las compuertas humanas marcadas más abajo. Es lo primero que
lee cada sesión nueva.

**Qué cambió respecto de la versión 1.0.** Tres cosas, y todas vienen de haber elegido Google Cloud
como destino:

1. **TimescaleDB sale del proyecto.** Cloud SQL no soporta la extensión, y el Timescale gestionado que
   sí corre en Google Cloud entrega la edición Apache 2, sin compresión ni continuous aggregates, que
   son la razón de usarlo. Lo sustituye el particionado nativo de PostgreSQL. Ver **ADR 0007**. Esto
   además resuelve el desvío 3 del cierre de F0.
2. **El despliegue deja de ser sólo la última fase.** Se añade un entorno de validación temprano para
   probar la infraestructura antes de que ocho fases se construyan encima. Ver **ADR 0008**.
3. **Se añaden dos fases, FA y FB, entre F0 y F1.** El resto de la numeración no se mueve, para que
   las referencias existentes sigan siendo válidas.

**Alcance acordado.** Producto completo del `PLAN_PRODUCTO.md`: calendario, ingesta, comparación,
molestias, bandeja, copiloto, propuestas de ajuste, grupos a escala y operación lista para piloto
pagado. Frontend: **una sola PWA**. Datos: **conector intervals.icu como vía principal + carga manual
de FIT como respaldo**. Infraestructura: **Google Cloud**.

---

## 1. Reglas que no se negocian

Heredadas del repo y vigentes en todas las fases:

1. La IA no publica sesiones ni escribe métricas. Devuelve borradores validados contra esquema; los
   números salen de funciones deterministas.
2. No se promete diagnóstico médico, prevención de lesiones, predicción exacta de rendimiento ni
   ajuste automático del entrenamiento.
3. Nunca «100 % descansado». Los estados de revisión son: *datos insuficientes*, *sin señales
   destacadas en los datos disponibles*, *requiere revisión*.
4. Una molestia reportada nunca queda oculta por una puntuación favorable del reloj, y se puede
   reportar sin reloj.
5. Texto de archivos, reportes o proveedores es **dato**, nunca instrucción.
6. Toda observación conserva atleta, proveedor, método, unidad, periodo observado, zona horaria,
   `received_at`, `external_id` y calidad. No se mezclan métodos (SDNN ≠ RMSSD) ni unidades
   (TRIMP ≠ TSS) ni escalas de fabricantes.
7. Reintentar una ingesta no duplica ni altera datos históricos en silencio.
8. Alembic es la única vía de cambio de esquema. Nunca `docker compose down -v`.
9. Fuera de Git: `.env`, tokens, datos reales de atletas, archivos FIT reales, `node_modules`,
   capturas, logs.
10. La autorización se resuelve en el servidor. La interfaz nunca la sustituye ocultando botones.
11. Ninguna fase se cierra sin pruebas verdes **y** guion de validación humana ejecutado.
12. **El entorno de validación no recibe datos reales de atletas.** Sólo cuentas del equipo y datos
    sintéticos o propios. Los datos reales entran únicamente en producción, y sólo después de F12.

## 2. Decisiones de arquitectura que fija este plan

**ADR 0003 — PWA única.** Se sustituyen las dos apps por `frontend/apps/nodo-web`: Next.js 16 (App
Router) con route groups `(coach)` y `(atleta)`, sesión compartida y módulos habilitados por
capacidad. `packages/api-client` se conserva. `apps/nodo-mobile` se congela en la rama `archive/expo`
y sale del workspace. Razón: el ADR 0001 admite que una persona sea atleta y entrenador a la vez; con
dos apps esa persona tendría que instalar dos cosas para ser lo que es. Se acepta perder HealthKit y
push nativo; si HealthKit vuelve como requisito, se envuelve la misma PWA en Capacitor.

**ADR 0004 — Sesión como BFF.** El token opaco vive en cookie `httpOnly`, `Secure`, `SameSite=Lax`,
emitida por route handlers de Next que hablan con la API. El JavaScript del navegador nunca ve el
token. Sustituye el `sessionStorage` del prototipo.

**ADR 0005 — Conector intervals.icu.** OAuth 2.0 con scopes, tokens cifrados en reposo, webhooks de
actividad/calendario/atleta, backfill inicial y escritura opcional de sesiones planificadas.
Atribución a Garmin cuando el dato provenga de un dispositivo Garmin (campo `device_name`). Se pide al
atleta conectar su reloj **directo** (Garmin, COROS, Polar, Wahoo), no vía Strava, porque los términos
de Strava restringen mostrar datos a entrenadores y procesarlos con IA.

**ADR 0006 — Cola sobre Postgres.** El worker persistente se implementa con una tabla `jobs` y
`SELECT … FOR UPDATE SKIP LOCKED`, no con Redis/Celery. Razón: ya hay Postgres, sobrevive reinicios, y
no añade una pieza de infraestructura al piloto.

**ADR 0007 — Particionado nativo en lugar de TimescaleDB.** `telemetry_records` y `observations` son
tablas particionadas por rango sobre su columna de tiempo, administradas con `pg_partman`, con BRIN
como índice de tiempo. `time_bucket()` se sustituye por `date_bin()`; los continuous aggregates, por
vistas materializadas refrescadas desde la cola `jobs`. Razón y números en el ADR.

**ADR 0008 — Despliegue en Google Cloud.** Dos proyectos, `nodo-staging` y `nodo-prod`. API y PWA en
Cloud Run como servicios; el worker como worker pool de Cloud Run; las migraciones como job de Cloud
Run que corre antes de enrutar tráfico. Cloud SQL para PostgreSQL 16 sin IP pública, con copias
automáticas y recuperación a un punto en el tiempo. Cloud Storage para archivos FIT, Secret Manager
para secretos, Artifact Registry para imágenes, GitHub Actions con Workload Identity Federation para
desplegar y Terraform en `infra/` para todo lo anterior.

**Stack de UI.** Tailwind v4 + componentes propios. Sin librería de componentes pesada: el calendario
y el editor de pasos son a medida de todos modos.

## 3. Modelo de datos objetivo

Lo que debe existir al terminar el plan. Cada fase migra su parte; ninguna fase deja el esquema a
medias.

**Identidad y organización** — `users`, `user_roles(user_id, role)`,
`coach_athlete_assignments(coach_id, athlete_id, status, timestamps)`, `organizations`,
`organization_memberships`, `auth_sessions`, `athlete_invitations`.

**Atleta** — `athlete_profiles(athlete_id, sports, timezone, rest_hr, max_hr, ftp, threshold_pace,
source, valid_from, valid_to)`. Todo parámetro fisiológico lleva fuente y vigencia.

**Planificación** — `training_blocks`, `prescribed_workouts(steps JSONB, status, version)`,
`competitions(date, discipline, priority)`, `groups`, `group_memberships`, `plan_templates`,
`plan_assignments(template_id, athlete_id, overrides JSONB)`.

**Ejecución** — `activities(athlete_id NOT NULL, provider, external_id, file_hash, sport, started_at,
timezone, …)` con `UNIQUE(provider, external_id)` y `UNIQUE(athlete_id, file_hash)`;
`activity_sessions`; `activity_laps`; **`telemetry_records` particionada por rango sobre `timestamp`**.

**Bienestar** — **`observations(athlete_id, metric_type, value, unit, method, source, device_id,
observed_start, observed_end, received_at, timezone, external_id, quality)` particionada por rango
sobre `observed_start`**; `checkins(local_date, fatigue, perceived_rest, stress, session_rpe, notes)`.

**Molestias** — `complaints(zone, laterality, intensity_0_10, started_on, limits_movement, status)`,
`complaint_updates`, `review_items(kind, priority, reason, dedupe_key, status)`.

**Carga y estado** — `daily_load(athlete_id, local_date, load_unit, load_value, ctl, atl, tsb,
formula_version, recomputed_at)`. No particionada: una fila por atleta y día, y es la tabla que evita
que el producto lea telemetría cruda.

**Copiloto** — `recommendations(athlete_id, base_plan_version, evidence JSONB, changes JSONB,
rules_version, model_version, status)`, `decisions(recommendation_id, actor_id, action, note,
decided_at)`.

**Integraciones y operación** — `athlete_connections(provider, external_athlete_id, access_token_enc,
refresh_token_enc, scopes, status, last_sync_at)`, `ingestion_events(provider, external_id,
payload_hash, received_at, status)`, `jobs(kind, payload, run_after, attempts, locked_by, locked_at,
status, last_error)`, `audit_log(actor_id, entity, entity_id, action, before, after, at)`,
`consents(user_id, scope, version, granted_at, revoked_at)`.

## 4. Convenciones de ejecución

- Una rama por fase: `feat/fN-slug`, desde `dev`, PR a `dev`. `main` no se toca.
- Cada PR: objetivo acotado, migración si aplica, pruebas de la capa afectada, documentación
  actualizada. Sin secretos ni datos reales.
- Terminado por fase: `pytest -q` verde, `alembic upgrade head` limpio sobre base nueva,
  `alembic check` sin deriva, `npm run typecheck` y `npm run build:web` verdes, y el guion de
  validación humana ejecutado por Brandon o Josué.
- **El CI corre las migraciones contra `postgres:16` como service container.** Desde FA ya no hace
  falta `timescale/timescaledb-ha`, y `alembic check` deja de mentir.
- **Desde FB, cerrar una fase incluye desplegarla a staging** y que el guion de validación humana se
  ejecute ahí, no sólo en local.
- Cobertura obligatoria en rutas protegidas: permiso propio, permiso denegado, conflicto concurrente.
- Cada fase agrega su ADR o actualiza `ESTADO_TECNICO.md`. Nada se declara implementado sin estarlo.
- Si una fase descubre trabajo no previsto, se anota en la sección 11 «Desvíos» y se decide con el
  equipo antes de expandir alcance.

## 5. Compuertas humanas

Claude **no** hace esto solo. Se detiene y lo pide:

- **Crear los proyectos de Google Cloud, habilitar facturación y fijar un presupuesto con alerta.**
- **Elegir la región** y confirmar el costo en la calculadora antes de crear recursos.
- **Autorizar el primer `terraform apply`** de cada entorno.
- Registrar la aplicación OAuth en intervals.icu y guardar `client_id`/`secret`.
- Elegir proveedor de IA, cuenta y presupuesto máximo mensual.
- Contratar dominio y correo transaccional.
- Desplegar a producción por primera vez y cualquier operación sobre datos reales de atletas.
- Aceptar términos de terceros, redactar aviso de privacidad definitivo o fijar precio.
- Aprobar cualquier cambio de alcance respecto de este plan.

---

## 6. Fases

Cada fase indica objetivo, trabajo, criterio automático (lo que deben decir las pruebas) y guion de
validación humana. El orden es de dependencia.

### F0 · Higiene, contratos y ADR — *hecho, pendiente de merge*

Renombrado de `backend/fit-parser` a `backend/api`, `ruff`, `pre-commit`, `.env.example`, ADR 0003–0006
y este plan en el repo. Rama `feat/f0-higiene`, tres commits, verificada con 39 pruebas verdes.

**Estado al 17 de septiembre:** la rama está en GitHub; falta abrir el PR a `dev`, que el CI pase y
que se ejecute la validación humana de 10 minutos (clonar limpio, levantar Docker, `/health` en 200).

---

### FA · Esquema sin Timescale

**Objetivo.** Dejar el esquema desplegable en PostgreSQL gestionado y que `alembic check` diga la
verdad. Implementa el ADR 0007 y cierra los tres desvíos de F0.

**Trabajo.**

1. Migración `0004` que quita TimescaleDB y particiona:
   - Eliminar de `0001_nodo_core` el `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE` y el
     `SELECT create_hypertable('telemetry_records', …)`. Son las dos únicas apariciones.
   - Convertir `telemetry_records` en `PARTITION BY RANGE (timestamp)`. La clave primaria ya es
     `(activity_id, timestamp)`, así que la clave de partición ya está dentro y **no hay que tocar la
     primaria ni ninguna consulta**. La conversión se hace creando la tabla particionada, copiando e
     intercambiando nombres dentro de la misma transacción; no existe `ALTER TABLE … PARTITION BY`.
   - Crear el índice `telemetry_records_timestamp_idx` explícitamente, **como BRIN sobre
     `timestamp`**. Hoy lo declara el modelo y ninguna migración lo crea: lo creaba
     `create_hypertable`. Ésta es la deriva que hacía fallar `alembic check` contra Postgres plano.
   - Configurar `pg_partman` para crear particiones mensuales por adelantado y retirar las viejas.
2. Limpieza de esquema arrastrada: retirar la columna muerta `acwr` de `activities`, que
   `ESTADO_TECNICO.md` ya declara sin uso desde que se eliminó el cálculo mal etiquetado.
3. `docker-compose.yml`: la imagen `timescale/timescaledb-ha` se sustituye por `postgres:16` fijada
   por digest. El servicio `timescaledb-init`, que existía sólo para el UID de la imagen HA,
   desaparece.
4. CI: el job de migraciones corre contra `postgres:16` como service container y ejecuta
   `alembic upgrade head`, `alembic check` y un `downgrade`/`upgrade` de ida y vuelta.
5. **`ruff format` en un commit aislado**, separado de todo lo demás, para que el diff de formato no
   entierre el diff de esquema. Reactivar la regla en `pre-commit` y en CI. Cierra el desvío 2 de F0.
6. `ESTADO_TECNICO.md` y `ARQUITECTURA.md` dejan de decir TimescaleDB.

**Criterio automático.** `alembic upgrade head` limpio sobre un `postgres:16` nuevo y `alembic check`
sin operaciones pendientes —lo que hoy no ocurre—; `downgrade` a `0003` y vuelta a head limpios; las
39 pruebas siguen verdes; insertar telemetría de dos meses distintos aterriza en dos particiones
distintas; `ruff check` y `ruff format --check` limpios.

**Validación humana.** Clonar limpio, `docker compose up`, `/health` en 200 contra `postgres:16`, subir
un FIT tuyo y ver la actividad. 15 minutos.

---

### FB · Staging en Google Cloud

**Objetivo.** Probar el ADR 0007 contra Cloud SQL real antes de que ocho fases se construyan encima, y
tener algo que abrir en el teléfono para validar cada fase siguiente.

**Compuerta humana previa.** Brandon crea el proyecto `nodo-staging`, habilita facturación, fija un
presupuesto con alerta, elige región y autoriza el primer `terraform apply`.

**Trabajo.** Terraform en `infra/` con módulos reutilizables y `envs/staging`: habilitación de APIs,
VPC, Cloud SQL para PostgreSQL 16 zonal sin IP pública con copias automáticas y recuperación a un
punto en el tiempo, Artifact Registry, Secret Manager, cuentas de servicio con permiso mínimo, y el
servicio de Cloud Run de la API con egreso directo a la VPC. Ajustes de código para Cloud Run: el
`Dockerfile` respeta `$PORT` en vez de fijar 8000, los logs salen en JSON a `stdout` sin datos
personales, y la app confía en `X-Forwarded-Proto`. Job de Cloud Run que ejecuta `alembic upgrade head`.
Workflow de GitHub Actions que, al fusionar a `dev`, construye la imagen, la publica en Artifact
Registry, corre el job de migraciones y sólo entonces despliega la revisión nueva, autenticándose por
Workload Identity Federation y sin llaves JSON. Un `docs/DESPLIEGUE.md` con el runbook: crear el
entorno desde cero, desplegar, revertir a la revisión anterior y restaurar la base.

**Criterio automático.** `terraform plan` sin cambios después de aplicar; el despliegue falla y no
enruta tráfico si el job de migraciones falla; `/health` responde 200 contra Cloud SQL; ningún secreto
aparece en la imagen ni en las variables del repositorio.

**Validación humana.** Brandon abre la URL de staging desde el teléfono y ve `/health`. Josué fusiona
un cambio trivial a `dev` y confirma que aparece desplegado solo. Los dos ejecutan juntos la
restauración de la base desde una copia, una vez, y la anotan con fecha. 30 minutos.

---

### F1 · Identidad multirol

**Objetivo.** Cumplir el ADR 0001 antes de construir pantallas encima del modelo transitorio.

**Trabajo.** Migración que crea `user_roles`, `coach_athlete_assignments`, `organizations`,
`organization_memberships` y copia lo que hoy vive en `users.role` y `users.coach_id`; las columnas
viejas quedan deprecadas y dejan de leerse. `/auth/me` devuelve lista de capacidades. La autorización
pasa a resolverse por asignación activa, nunca por un `athlete_id` del cliente. `accessible_athlete()`
se reescribe sobre la tabla de asignaciones. `is_superuser` se conserva separado. Revisar si conviene
reactivar `UP042` en `ruff.toml`, desactivada porque esta fase rehace `UserRole`.

**Criterio automático.** Persona que es coach y atleta a la vez ve ambos módulos; coach sin asignación
recibe 404; atleta no alcanza a otro atleta; asignación revocada corta el acceso; la migración sobre
una base con datos del modelo viejo preserva las relaciones.

**Validación humana.** Con dos cuentas, confirmar que un coach ve solo a los suyos y que una cuenta
doble muestra las dos zonas. 15 minutos.

---

### F2 · PWA única con sesión BFF

**Objetivo.** Una sola aplicación instalable, con la sesión fuera del alcance del JavaScript.

**Trabajo.** Crear `frontend/apps/nodo-web` (Next.js 16, App Router, Tailwind 4) con route groups
`(coach)` y `(atleta)` y un layout raíz que resuelve capacidades. Route handlers `/api/session/*` que
hacen login, refresh y logout contra la API y manejan la cookie `httpOnly` — esto cierra de paso el
pendiente de «consolidar el refresh en el cliente», porque el refresh deja de vivir en el cliente.
Middleware que protege rutas por capacidad. Manifest, iconos, `theme-color`, service worker con
Serwist y caché de la vista «hoy» para uso sin señal. **La zona del atleta consume
`GET /athletes/{id}/workouts` y muestra las sesiones publicadas** — el bloqueo principal que
`PENDIENTES_MVP.md` señalaba. Portar el login actual. Congelar `apps/nodo-mobile` en `archive/expo` y
sacarlo del workspace. Playwright con un e2e de login, logout y expiración. Añadir la PWA al Terraform
como segundo servicio de Cloud Run y al workflow de despliegue.

**Criterio automático.** `typecheck` y `build:web` verdes; e2e de sesión verde; el token no aparece en
`localStorage`, `sessionStorage` ni en el HTML servido.

**Validación humana.** Instalar la PWA en un Android y un iPhone desde la URL de staging, iniciar
sesión, cerrar la app, volver a abrirla y seguir dentro. Modo avión y confirmar que la pantalla de hoy
carga. 20 minutos.

---

### F3 · Perfil del atleta y parámetros fisiológicos

**Objetivo.** Que los cálculos dejen de depender de parámetros escritos a mano en un formulario.

**Trabajo.** `athlete_profiles` con deportes, zona horaria, FC de reposo y máxima, FTP, ritmo umbral,
cada uno con fuente y vigencia. El coach los edita; el atleta los ve. `POST /upload-fit` deja de
recibir `rest_hr`, `max_hr`, `is_male` y los toma del perfil vigente a la fecha de la actividad. Si no
hay perfil, `trimp_status` explica por qué falta.

**Criterio automático.** TRIMP se calcula desde el perfil; sin perfil devuelve `insufficient_inputs`;
cambiar el perfil no reescribe históricos sin recálculo explícito.

**Validación humana.** Cargar tu propio perfil, subir un FIT tuyo y ver el TRIMP con la fuente del
parámetro visible. 10 minutos.

---

### F4 · Calendario y editor de sesiones

**Objetivo.** El corazón del producto para el coach, y la primera pantalla real para el atleta.

**Trabajo.** Vista de calendario por atleta y por rango; creación de bloques con fechas libres, fases y
competencias. Editor de sesión estructurada: grupos con repeticiones, pasos de
calentamiento/trabajo/recuperación/vuelta a la calma, duración o distancia, objetivo tipado con
unidades — **incluida la selección de ritmo, potencia, FC y RPE que `PENDIENTES_MVP.md` marcaba como
faltante**. **Abrir y editar un borrador existente**, el otro pendiente heredado. Borrador y
publicación con `expected_version`; el 409 muestra qué cambió y pide decisión, sin reintento
automático. Zona del atleta: hoy, semana y detalle de sesión con los pasos legibles.

**Criterio automático.** Pruebas de contrato de pasos (rechazo de objetivos sin unidad, repeticiones
inválidas, pasos vacíos); prueba de edición concurrente que produce 409; pruebas de regresión de
publicación repetida, edición de publicados y rango de bloques; e2e de crear-publicar-ver.

**Validación humana.** Un coach arma un bloque de dos semanas con una sesión de series (6×800 con
recuperación) y lo publica; el atleta lo ve en su teléfono. Dos pestañas editando la misma sesión
producen un aviso claro, no una sobrescritura. 30 minutos.

---

### F5 · Pipeline de ingesta idempotente

**Objetivo.** Cumplir el ADR 0002. Es la fase que desbloquea cualquier conector.

**Trabajo.** `activities` gana `athlete_id NOT NULL`, `provider`, `external_id`, `file_hash` y sus
índices únicos. Tabla `ingestion_events` para registrar toda recepción antes de procesarla. Tabla
`jobs` y `worker.py` con `SKIP LOCKED`, reintentos con backoff, límite de intentos y bandeja de
fallos. Idempotencia también para invitaciones, pendiente heredado. La subida de FIT pasa a ser
autenticada: el atleta sube lo suyo, el coach puede subir en nombre de un atleta asignado; se habilita
fuera de `development`, con límite de cuerpo HTTP en el proxy antes de parsear multipart. `daily_load`
se recalcula desde el día afectado cuando llega una actividad histórica, guardando `formula_version`.
Los archivos FIT pasan a Cloud Storage. El worker se añade al Terraform **como worker pool de Cloud
Run**, con CPU siempre asignada, y al workflow de despliegue.

**Criterio automático.** Subir dos veces el mismo archivo no crea dos actividades; un job interrumpido
a mitad se retoma tras reiniciar el worker; una actividad con fecha de hace un mes recalcula la serie
hacia adelante; fallo repetido termina en bandeja, no en silencio.

**Validación humana.** Subir el mismo FIT tres veces en staging y ver una sola actividad. Matar la
instancia del worker a media carga y confirmar que al levantarla termina el trabajo. 20 minutos.

---

### F6 · Conector intervals.icu

**Objetivo.** Que los datos lleguen solos, sin pagar agregador.

**Compuerta humana previa.** Registrar la app OAuth en intervals.icu y entregar credenciales por un
canal seguro.

**Trabajo.** `athlete_connections` con tokens cifrados, con la clave en Secret Manager y nunca en Git.
Rutas de inicio y callback OAuth con estado anti-CSRF; si el proveedor invalida el token, marcar la
conexión caída y pedir reconexión porque su contrato vigente no publica refresh token. Cliente de la API con
manejo de límites y errores. Receptor de webhooks de actividad, calendario y atleta que sólo registra
en `ingestion_events` y encola. Mapeo a `activities`, `activity_laps` y `observations`, conservando
proveedor, método y unidad. Backfill inicial acotado (90 días por defecto, configurable). Atribución a
Garmin cuando `device_name` lo indique. Pantalla del atleta «conectar mi reloj» con estado y
revocación; panel del coach con estado de sincronización por atleta y aviso de conexión caída.
Escritura de sesiones planificadas al calendario de intervals detrás de una bandera, apagada por
defecto, con NODO como fuente de verdad.

**Criterio automático.** Webhook duplicado no duplica actividad; token inválido marca la conexión caída
y solicita reconexión; revocación deja la conexión en `revoked` y no borra datos ya recibidos; una observación de
HRV conserva su método.

**Validación humana.** Brandon conecta su cuenta real contra staging, hace una actividad y confirma que
aparece con sus laps y su wellness del día, sin duplicados. Desconecta y ve el estado caer. 30 minutos
más una actividad real.

**Riesgo.** intervals.icu es una plataforma pequeña sin SLA y además ofrece funciones de coach por
4 USD al mes. Se documenta como dependencia con plan B: la carga manual de FIT queda funcionando
siempre.

---

### F7 · Observaciones y comparación plan contra ejecución

**Objetivo.** Que el coach vea qué se cumplió y qué no, sin interpretar a mano.

**Trabajo.** Crear `observations` **particionada por rango desde el primer día** —nace bien, no hay que
convertirla— y migrar a ella `daily_physiology`, que `ARQUITECTURA.md` describe como un boceto de una
fila por día incapaz de recibir varios proveedores. Agregación por día local, sueño que cruza
medianoche, cobertura parcial y lecturas tardías; donde TimescaleDB habría usado `time_bucket()` se usa
`date_bin()`, y donde habría usado continuous aggregates se usa una vista materializada refrescada
desde la cola `jobs`. Relleno de huecos escrito a mano con `generate_series` y funciones de ventana.
Vinculación de actividad con sesión prescrita (automática por fecha y disciplina, ajustable a mano).
Comparación de duración, distancia e intervalos contra los pasos prescritos. Estados explícitos:
cumplida, parcial, no realizada, no sincronizada. Resumen diario y semanal con calidad y antigüedad de
los datos visibles.

**Criterio automático.** Una sesión de series se compara contra los laps reales y reporta diferencias
por intervalo; una sesión sin actividad y un atleta sin sincronizar producen estados distintos; sueño
de 23:30 a 6:00 cuenta en el día correcto; la migración de `daily_physiology` no pierde filas.

**Validación humana.** Comparar una sesión real tuya contra lo prescrito y verificar que el veredicto
coincide con lo que pasó. 20 minutos.

---

### F8 · Check-ins, molestias y bandeja de revisión

**Objetivo.** El diferenciador frente a las plataformas de datos: lo que el reloj no ve.

**Trabajo.** Check-in breve del atleta (fatiga, descanso percibido, estrés, RPE de sesión, nota) con
fecha local y sin convertir ausencia en cero. Reporte de molestia con zona, lateralidad, intensidad
0–10, inicio, si limita el movimiento y nota; actualizaciones de evolución; funciona sin reloj. Flujo
reportada → revisada → decisión registrada → seguimiento → cierre, separado del estado de la sesión.
Bandeja de revisión con deduplicación por reporte, prioridad y razón visible; una molestia nueva o que
empeora reabre revisión conservando historial. Los estados de revisión son los tres acordados, nunca un
porcentaje de frescura.

**Criterio automático.** El cierre no impide reabrir; una molestia con intensidad creciente sube en la
bandeja aunque el wellness del día sea bueno; el atleta sin dispositivo puede reportar y aparecer en la
bandeja.

**Validación humana.** Recorrido completo con dos cuentas de atleta, una con reloj y otra sin él.
Confirmar que ningún reporte queda tapado. 30 minutos.

---

### F9 · Copiloto de planificación

**Objetivo.** Convertir instrucciones del coach en borradores estructurados.

**Compuerta humana previa.** Elegir proveedor, cuenta y tope de gasto mensual.

**Trabajo.** Interfaz de proveedor detrás de un puerto, con implementación y modo simulado para
pruebas. El modelo recibe contexto mínimo y devuelve un borrador que se valida contra el esquema de
pasos antes de tocar la base; si no valida, se reintenta una vez y luego se muestra el error. Los
números provienen de funciones deterministas, no del texto del modelo. Preguntas de vuelta cuando
faltan restricciones esenciales. Registro de uso y costo por coach. Si el proveedor falla, el
calendario manual sigue funcionando. Texto de terceros tratado como dato: el prompt no ejecuta
instrucciones que aparezcan en notas, archivos o respuestas de la API.

**Criterio automático.** Una salida deliberadamente inválida no llega a la base; el modo simulado
permite correr toda la suite sin red; una nota de atleta que dice «ignora las instrucciones
anteriores» no altera el comportamiento.

**Validación humana.** Pedir «seis semanas para 10K con cuatro sesiones por semana, sin correr martes»
y revisar si el borrador es editable y respeta la restricción. 30 minutos.

---

### F10 · Propuestas de ajuste y decisiones

**Objetivo.** Que la IA proponga y el coach decida, con rastro.

**Trabajo.** `recommendations` con evidencia, datos usados, límites, sesiones afectadas,
`base_plan_version`, `rules_version` y diff antes/después. Aprobar, modificar o rechazar, siempre
dentro de una transacción que verifica permiso y versión. Una propuesta generada sobre un plan que ya
cambió queda obsoleta y exige recálculo. `decisions` guarda quién, qué y por qué. Rechazar alimenta el
registro de producto, no una verdad fisiológica.

**Criterio automático.** Aprobar una propuesta obsoleta responde 409 y no modifica nada; aprobar una
vigente aplica exactamente el diff mostrado; toda modificación de plan queda atribuible a una decisión.

**Validación humana.** Generar una propuesta, cambiar el plan en otra pestaña e intentar aprobarla:
debe bloquearse con un mensaje claro. 20 minutos.

---

### F11 · Grupos, plantillas y escala

**Objetivo.** El caso de referencia del producto: 70 atletas sin abrir 70 conversaciones.

**Trabajo.** Grupos y membresías; plantilla de bloque aplicada a un grupo; personalización por atleta
con excepciones que sobreviven a las ediciones colectivas. Previsualización de afectados antes de
aplicar. Paginación y consultas eficientes en las vistas de lista. Semilla de 70 atletas sintéticos
para pruebas de carga, ejecutada contra staging.

**Criterio automático.** Editar la plantilla del grupo no borra las excepciones individuales; la
previsualización coincide con lo aplicado; con 70 atletas y 12 semanas de plan, la vista de semana del
coach responde por debajo del presupuesto acordado (propuesta: p95 < 1.5 s) y la lista de atletas por
debajo de 1 s, **medido en staging y no en local**.

**Validación humana.** Aplicar un cambio al grupo y confirmar que el atleta con ritmos propios los
conserva. 25 minutos.

---

### F12 · Producción y preparación de piloto

**Objetivo.** Cerrar las nueve condiciones de `PILOT_READINESS.md` con evidencia, sobre un entorno de
producción real.

**Compuerta humana previa.** Brandon crea `nodo-prod` con su propio presupuesto, contrata dominio y
correo transaccional, y autoriza el primer despliegue.

**Trabajo.** `envs/prod` en el mismo Terraform, con instancia mínima en la API para evitar arranques en
frío, dominio propio y HTTPS gestionado. Consentimiento versionado al activar cuenta; exportación y
borrado de datos del atleta; política de retención implementada con `pg_partman`. **Invitación por
correo real y recuperación de contraseña: el token deja de volver en la respuesta** —el último
pendiente de desarrollo que quedaba de `PENDIENTES_MVP.md`. Rate limiting y bloqueo progresivo en
login, activación y refresh. Secretos en Secret Manager con rotación documentada, imágenes fijadas por
digest. Copias automáticas con **una restauración probada y documentada con fecha y responsable**.
`audit_log` para cambios de plan, molestias y aprobaciones. Observabilidad: logs sin datos personales,
métricas de la cola, alerta de conexiones caídas, de jobs en bandeja, de errores 5xx y de presupuesto.
Prueba de carga y recorrido completo con el equipo sintético.

**Criterio automático.** Suite completa verde; prueba que verifica que un error no filtra datos
personales; prueba de rate limiting; restauración de copia documentada; `terraform plan` sin cambios
en producción después de aplicar.

**Validación humana.** Ejecutar el checklist de `PILOT_READINESS.md` punto por punto y firmarlo. Ésta
es la compuerta que autoriza invitar atletas reales. 1 hora.

---

### F13 · Notificaciones y escenarios

**Objetivo.** Lo último del alcance completo.

**Trabajo.** Web push para PWA instalada (recordatorio de sesión, molestia nueva para el coach,
propuesta pendiente), con preferencias por usuario y degradación limpia en iOS no instalado.
Escenarios precompetencia: comparación de alternativas de carga con supuestos y límites visibles, sin
prometer fecha de máximo rendimiento ni marca.

**Criterio automático.** Las notificaciones respetan preferencias y no se envían a sesiones revocadas;
los escenarios muestran supuestos junto a cada número.

**Validación humana.** Recibir un recordatorio real en el teléfono y revisar que un escenario no
promete resultados. 20 minutos.

---

## 7. Orden, esfuerzo y ritmo

| Fase | Depende de | Sesiones estimadas |
|---|---|---|
| F0 Higiene y ADR | — | 1 *(hecha)* |
| **FA Esquema sin Timescale** | F0 | **1** |
| **FB Staging en Google Cloud** | FA | **2** |
| F1 Identidad multirol | FA | 2 |
| F2 PWA y sesión BFF | F1, FB | 2 |
| F3 Perfil del atleta | F1 | 1 |
| F4 Calendario y editor | F2, F3 | 3 |
| F5 Pipeline de ingesta | F1, F3, FB | 2 |
| F6 Conector intervals | F5 | 3 |
| F7 Observaciones y comparación | F5, F6 | 2 |
| F8 Check-ins y molestias | F4, F7 | 2 |
| F9 Copiloto | F4 | 3 |
| F10 Propuestas y decisiones | F9, F7 | 2 |
| F11 Grupos y escala | F4 | 2 |
| F12 Producción y piloto | todas | 3 |
| F13 Notificaciones y escenarios | F12 | 2 |

Total: alrededor de **33 sesiones de trabajo**, tres más que la versión 1.0. En calendario, con
validación humana entre fases y las compuertas que dependen de terceros, el rango realista sigue
siendo de **15 a 21 semanas**. Lo que más lo mueve: qué tan rápido se validan las fases, cuándo llegan
las credenciales de intervals y del proveedor de IA, y si aparece trabajo no previsto en F5 y F6, que
son las más propensas a sorpresas.

FA es corta y desbloquea todo lo demás; conviene hacerla inmediatamente después de fusionar F0. F4, F5
y F6 pueden solaparse parcialmente si Josué toma frontend mientras la sesión avanza backend, pero el
plan está escrito para ejecución secuencial y validación ordenada.

## 8. Lo que este plan mide

Se instrumenta desde F4 y se revisa en F12:

- Tiempo mediano de planificación y de revisión por atleta (la meta del documento de producto es
  reducirlo 30 %; hace falta la línea base antes de afirmarlo).
- Porcentaje de sesiones con actividad sincronizada dentro de 24 horas.
- Alertas de la bandeja calificadas como útiles o no útiles.
- Duplicados de actividad: cero. Accesos cruzados en pruebas: cero.
- Costo de IA, de integración y **de infraestructura** por coach y por atleta activo.

## 9. Riesgos y planes B

| Riesgo | Señal temprana | Plan B |
|---|---|---|
| intervals.icu cambia términos, cae o limita la API | errores repetidos en la cola, aviso en su foro | la carga manual de FIT nunca se retira; agregador de pago sólo si el MRR lo sostiene |
| Datos que entran vía Strava | `source` de la actividad indica Strava | pedir conexión directa del reloj; no mostrar ni procesar con IA lo que venga de Strava |
| intervals compite por 4 USD/mes | coaches piloto dicen «esto ya lo tengo» | el valor de NODO es escala del coach, español, molestias y propuestas aprobadas, no la gráfica de forma |
| Costo de IA sin control | gasto por coach arriba del tope | tope duro por cuenta, caché de borradores, modelo más barato para tareas simples |
| Alcance que se estira | fases que no cierran en las sesiones estimadas | recortar primero F13, escritura a intervals y escenarios; nunca recortar permisos, idempotencia ni molestias |
| **Costo de Google Cloud sin control** | alerta de presupuesto del proyecto | presupuesto con alerta desde el día uno; staging escala a cero; revisar el worker, que es lo único siempre encendido |
| **El particionado no rinde al crecer** | consultas de telemetría lentas con varios millones de filas | reducir el tamaño de partición, añadir índices por `activity_id`; si aun así no basta, TimescaleDB autoalojado o Tiger Cloud: volver es reimportar, no rehacer |
| **Dependencia de un solo proveedor de nube** | — | la aplicación sigue siendo contenedores y Postgres, y `docker compose` se mantiene funcionando. Mudarse es rehacer Terraform, no el producto |

## 10. Cómo arrancar la ejecución en otro chat

Abrir una sesión nueva —en el proyecto **Fit OS** de Claude, o en Claude Code dentro de un clon del
repositorio— y pegar el prompt de abajo tal cual. La sesión detecta sola la fase siguiente; para
forzar una, cambiar la línea «Fase a ejecutar».

**Requisito práctico:** la sesión necesita permiso de escritura en el repositorio para empujar la rama
y abrir el PR. El conector de GitHub usado el 17 de septiembre sólo tenía lectura sobre
`Josuesp34/NODO`; Josué, como dueño del repositorio, tiene que concederle escritura. Mientras tanto,
lo que funciona es Claude Code en un clon local, con las credenciales de git de quien lo corre.

```
Vas a continuar el desarrollo de NODO, una plataforma para entrenadores de resistencia y sus atletas. Repositorio: `github.com/Josuesp34/NODO`. Rama de integración: `dev`. `main` no se toca.

Tú desarrollas; Brandon y Josué validan cada fase a mano y son los únicos que cruzan las compuertas humanas. Trabaja en español.

## 1. Encuentra el plan vigente

Es `PLAN_EJECUCION.md` versión 2.0 (lo dice al inicio: «Versión 2.0»). Búscalo en este orden y usa el primero que exista:

1. `docs/PLAN_EJECUCION.md` en la rama `dev`, si es la versión 2.0.
2. El documento `claude/nodo-plan-ejecucion.md` del proyecto Fit OS de Claude.
3. La carpeta `Claude outputs/plan-v2-gcp/` del vault Body OS.

Si sólo encuentras la versión 1.0 —la que todavía habla de TimescaleDB— detente y avísame: es un plan obsoleto. Los ADR 0007 y 0008 están junto al plan (en el proyecto: `claude/nodo-adr-0007-postgres-particionado.md` y `claude/nodo-adr-0008-despliegue-gcp.md`).

Lee el plan completo y, del repo: `AGENTS.md`, `CONTRIBUTING.md`, `docs/ARQUITECTURA.md`, `docs/API_NODO.md`, `docs/ESTADO_TECNICO.md`, `docs/PENDIENTES_MVP.md` y los ADR que cite la fase.

## 2. Diagnostica antes de tocar nada

Revisa en GitHub qué fases están fusionadas en `dev`, qué PR están abiertos y el último commit de `dev`. Repórtamelo en cinco líneas como máximo: última fase fusionada, qué está abierto, qué falta para la siguiente y cuál vas a ejecutar.

Si el plan v2 no está en el repo, tu primer trabajo es ponerlo en camino, sin fusionar nada: abre el PR de `feat/f0-higiene` a `dev` si no existe, y crea la rama `docs/plan-v2-gcp` con los tres documentos y su PR, usando el mensaje de commit y el cuerpo de PR de `COMO_APLICAR.md` (en el proyecto: `claude/nodo-como-aplicar-v2.md`).

## 3. Ejecuta una sola fase

Fase a ejecutar: la siguiente pendiente.

Si no te indico una, elige la siguiente según la tabla de dependencias de la sección 7. El orden es F0 → FA → FB → F1 → F2 → …

Si la fase anterior no está fusionada en `dev`, no la fusiones tú: fusionar es la validación humana. Pregúntame si espero o si ramificas encima de la rama pendiente. Trabaja en `feat/<fase>-<slug>` con commits pequeños cuyo mensaje explique el porqué, y abre un PR a `dev` con el formato de los anteriores.

## 4. Reglas

- Sólo esa fase. No adelantes la siguiente ni amplíes alcance. Trabajo no previsto va a la sección 11 «Desvíos» del plan, y me preguntas antes de hacerlo.
- No cruces las compuertas de la sección 5: proyectos o facturación de Google Cloud, `terraform apply`, credenciales de intervals.icu o del proveedor de IA, dominio, correo, producción, datos reales de atletas, precio, aviso de privacidad. Deja todo listo hasta ese punto y detente a pedírmelo.
- Nada de secretos, `.env`, archivos FIT reales ni datos de atletas en Git.
- No inventes endpoints ni declares implementado lo que no está. `ESTADO_TECNICO.md` debe reflejar la realidad al cerrar.
- Las migraciones se verifican contra PostgreSQL 16 real: `alembic upgrade head`, `alembic check` sin deriva, y downgrade y vuelta. Si no tienes Docker, instala PostgreSQL 16 en el entorno. TimescaleDB ya no forma parte del proyecto (ADR 0007).
- Si no puedes hacer push o abrir un PR, no reintentes: dime el motivo exacto y entrégame un `git bundle` de la rama junto con el texto del PR.

## 5. Al cerrar, entrégame

1. El enlace al PR, o el bundle.
2. La evidencia resumida: pytest, ruff, alembic, typecheck y build.
3. Los desvíos que encontraste.
4. El guion de validación humana de la fase, paso a paso y con tiempo estimado.
5. Lo que la fase siguiente necesita de mí antes de arrancar.
```

## 11. Desvíos

Se registran aquí conforme aparezcan, con fecha, fase, qué se encontró y qué se decidió.

**14 de septiembre de 2026 · F0 · `dev` iba por delante del plan.** El plan v1 decía 36 pruebas; eran
36 en `main` y 39 en `dev`, que además traía `0003_align_indexes`, pantallas reales de NODO Lab y
`docs/PENDIENTES_MVP.md`. **Resuelto:** 39 es la línea base.

**14 de septiembre de 2026 · F0 · `ruff format` quedó fuera.** Reescribiría 25 de 37 archivos del
backend, unas 1 260 líneas, y habría enterrado el diff del renombrado de `fit-parser` a `api`.
**Resuelto el 17 de septiembre:** se adopta en un commit aislado dentro de **FA**.

**14 de septiembre de 2026 · F0 · El esquema sólo coincide con los modelos si TimescaleDB está
presente.** `TelemetryRecord` declara `telemetry_records_timestamp_idx`, que ninguna migración crea:
lo creaba `create_hypertable`. **Resuelto el 17 de septiembre:** el ADR 0007 elimina TimescaleDB y
**FA** crea el índice explícitamente como BRIN. La propuesta de un job de CI con
`timescale/timescaledb-ha` queda descartada; el CI corre contra `postgres:16`.

**17 de septiembre de 2026 · F0 · La rama se empujó pero no se abrió PR.** `feat/f0-higiene` llevaba
tres días en GitHub sin PR y sin merge a `dev`, y la validación humana de 10 minutos no estaba
registrada. **Pendiente:** abrir el PR, verificar el CI y ejecutar la validación antes de arrancar FA.

**17 de septiembre de 2026 · Plan · TimescaleDB es incompatible con el destino elegido.** Cloud SQL y
AlloyDB no soportan la extensión; Tiger Cloud sólo corre en AWS y Azure; y cualquier Timescale
gestionado que sí corra en Google Cloud entrega la edición Apache 2, sin compresión ni continuous
aggregates. **Resuelto:** ADR 0007 y ADR 0008, fases FA y FB.

## 12. Pendientes heredados y dónde se cierra cada uno

`PENDIENTES_MVP.md` y `PILOT_READINESS.md` describen trabajo abierto de la etapa anterior. Ninguno se
pierde; cada uno tiene fase asignada. Esta tabla es la que hay que revisar antes de declarar el
producto terminado.

| Pendiente | Origen | Se cierra en |
|---|---|---|
| El atleta no ve sus sesiones publicadas (web) | PENDIENTES_MVP, bloqueo principal | **F2** |
| NODO móvil es un placeholder sin autenticación | PENDIENTES_MVP | **F2**, por decisión: se congela en `archive/expo` (ADR 0003) |
| Refresh de sesión sin estrategia única en el cliente | PENDIENTES_MVP | **F2** — el BFF lo saca del cliente (ADR 0004) |
| No se puede abrir y editar un borrador existente | PENDIENTES_MVP | **F4** |
| Faltan objetivos de ritmo, potencia, FC y RPE en el editor | PENDIENTES_MVP | **F4** |
| Faltan pruebas de publicación repetida, 409 y rango de bloques | PENDIENTES_MVP | **F4** |
| Faltan pruebas de UI de invitación, 403, 422 y 409 | PENDIENTES_MVP | **F2** (sesión) y **F4** (planificación) |
| Idempotencia de invitaciones e importación FIT sin definir | PENDIENTES_MVP | **F5** |
| Trabajos asíncronos todavía dentro de la petición HTTP | PENDIENTES_MVP | **F5** (ADR 0006) |
| El token de invitación se muestra en la respuesta; no hay correo | PENDIENTES_MVP | **F12** |
| `ALLOW_COACH_REGISTRATION` como registro de desarrollo | PENDIENTES_MVP | **F1** (capacidades) y **F12** (registro real) |
| `daily_physiology` es un boceto de una fila por día | ARQUITECTURA | **F7** — lo sustituye `observations` |
| Columna `acwr` muerta en `activities` | ESTADO_TECNICO | **FA** |
| Índice `telemetry_records_timestamp_idx` sin migración | Desvío 3 de F0 | **FA** |
| `ruff format` sin adoptar | Desvío 2 de F0 | **FA** |
| Ingesta deshabilitada fuera de `development` | ESTADO_TECNICO | **F5** |
| Sin límite de cuerpo HTTP en el proxy antes de parsear multipart | ESTADO_TECNICO | **F5** |
| Identidad multirol, relaciones y pruebas de acceso cruzado | PILOT_READINESS 1 | **F1** |
| Invitación segura, recuperación, HTTPS, secretos, rate limiting | PILOT_READINESS 2 | **FB** (HTTPS, secretos) y **F12** (el resto) |
| Actividad asociada al atleta, deduplicación, historial auditable | PILOT_READINESS 3 | **F5** y **F12** (`audit_log`) |
| Consentimiento, exportación, borrado y retención | PILOT_READINESS 4 | **F12** |
| Copias automáticas y una restauración comprobada | PILOT_READINESS 5 | **FB** (primera prueba) y **F12** (firmada) |
| Despliegue reproducible de API, worker, base, archivos y monitoreo | PILOT_READINESS 6 | **FB** y **F12** (ADR 0008) |
| Pipeline persistente de sincronización y recomendaciones | PILOT_READINESS 7 | **F5** y **F10** |
| Registro de auditoría de planes, molestias y aprobaciones | PILOT_READINESS 8 | **F12** |
| Prueba de carga y recorrido con equipo de prueba | PILOT_READINESS 9 | **F11** (carga) y **F12** (recorrido) |

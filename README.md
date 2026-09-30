# NODO/ NODO Lab

Plataforma para que entrenadores planifiquen, publiquen y revisen el entrenamiento de sus atletas, con datos de ejecución, descanso y molestias y ayuda de IA bajo aprobación humana. NODO y NODO Lab viven en una sola PWA responsive con módulos separados para atleta y entrenador.

## Documentos para empezar juntos

- [**Plan de ejecución hasta producto completo**](docs/PLAN_EJECUCION.md): las fases técnicas, las reglas que no se negocian y las compuertas humanas. Es lo primero que debe leer cualquier sesión de trabajo nueva.
- [Contrato maestro F0–F16](docs/PLAN_MAESTRO_NODO.md) y [matriz de evidencia](docs/MATRIZ_REQUISITOS.md).
- [Inventario funcional vigente](docs/FUNCIONALIDADES_PRODUCTO.md): qué está operativo, simulado, parcial o pendiente.
- [Guía de carga FIT e Intervals.icu](docs/GUIA_CARGA_FIT_E_INTERVALS.md): recorrido de usuario, resultados y límites actuales.
- [Configuración de Resend](docs/RESEND_CONFIGURACION.md) y [comparación de proveedores](docs/DECISION_PROVEEDORES.md).
- [Decisiones de arquitectura (ADR)](docs/ADR/): identidad multirol, pipeline de ingesta, PWA única, sesión BFF, conector intervals.icu y cola sobre Postgres.
- [Visión, alcance, objetivos y plan de ocho semanas](docs/PLAN_PRODUCTO.md).
- [Arquitectura y contratos propuestos](docs/ARQUITECTURA.md).
- [Contratos de la API base](docs/API_NODO.md).
- [Guía de arranque de la PWA](docs/FRONTEND.md).
- [Relevo histórico de frontend para Antigravity](docs/ANTIGRAVITY_FRONTEND_HANDOFF.md).
- [Estructura del repositorio](docs/ESTRUCTURA_REPOSITORIO.md).
- [Guía de colaboración](CONTRIBUTING.md).
- [Condiciones para abrir un piloto](docs/PILOT_READINESS.md).
- [Estado técnico, decisiones del refactor y pendientes](docs/ESTADO_TECNICO.md).
- [Pendientes del MVP, ruta crítica y criterios de prueba](docs/PENDIENTES_MVP.md).
- [Plataforma GCP](infra/README.md), [operación](docs/OPERACION_GCP.md), [seguridad](docs/SEGURIDAD.md), [costos](docs/COSTOS.md) y [lanzamiento](docs/LANZAMIENTO.md).

**Estado actual: piloto funcional local; producción pendiente de configuración y verificación.** El recorrido local coach → invitación → activación → planificación → publicación → atleta está verificado sobre PostgreSQL 16 real. FIT manual es funcional. IA e Intervals.icu reales no están configurados ni completos: sólo existen sus modos simulados y contratos seguros. La versión candidata y la evidencia de publicación de código están en [GitHub Release](https://github.com/Josuesp34/NODO/releases/tag/v0.4.0-rc.1); un tag no demuestra producción. Falta verificar GCP/billing, plan/apply, URL HTTPS, correo/dominio, integraciones reales y los criterios de `LANZAMIENTO.md`. Consultar `FUNCIONALIDADES_PRODUCTO.md` antes de ofrecer una capacidad.

## Entrega con Josué

El [plan de handover](docs/HANDOVER_JOSUE.md) reúne el arranque, demo, cambios, pendientes y responsables propuestos. El [mensaje de WhatsApp](docs/MENSAJE_WHATSAPP_JOSUE.md) es un borrador para que Brandon lo envíe. La autorización de producción está registrada; la disponibilidad pública y las integraciones reales requieren evidencia separada.

## Desarrollo local

Python 3.11 o 3.12 y Docker Desktop con motor Linux activo. Desde la raíz del repositorio, en PowerShell:

```powershell
cd backend/api
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip==26.2.0
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Editar `.env`: cambiar la contraseña de ejemplo y reflejarla en ambas URLs. `DATABASE_URL` usa `localhost` para Python local; `DOCKER_DATABASE_URL` usa `postgres` para la red de Compose. El archivo `.env` no se versiona.

El puerto local por defecto de la base es `5433`, para no interferir con una instalación de PostgreSQL que use `5432`.

```powershell
docker compose up -d postgres
.venv/Scripts/alembic.exe upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Para ejecutar también la API en contenedor, una vez inicializada la base y sin la API local ocupando el puerto:

```powershell
docker compose up -d --build api
```

El servicio `worker` procesa la cola de carga diaria y correo. Para el recorrido local completo, iniciarlo junto a la API con `docker compose up -d --build api worker`; sin worker, un mensaje queda en cola pero no se envía.

API: [OpenAPI local](http://127.0.0.1:8000/docs). `GET /health` verifica PostgreSQL sin modificar el esquema y devuelve 503 si no está disponible.

Alembic crea el esquema inicial en una base nueva y registra la versión aplicada. Antes de reutilizar una base existente, respaldar y revisar su esquema y ubicación. El Compose actual fija `PGDATA` al volumen declarado: la configuración anterior de la imagen HA podía guardar datos en otra ubicación. Este refactor no movió ni eliminó datos ni volúmenes. No ejecutar `down -v` para resolver incompatibilidades.

## Pruebas y estilo

```powershell
cd backend/api
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
```

`ruff check` debe quedar limpio antes de abrir un PR; sus reglas están en `backend/api/ruff.toml`. Para que los ganchos corran solos en cada commit, una vez por clon y desde la raíz del repositorio:

```powershell
backend/api/.venv/Scripts/pre-commit.exe install
backend/api/.venv/Scripts/pre-commit.exe run --all-files
```

Los ganchos rechazan `.env`, archivos FIT, `node_modules`, `__pycache__` y logs antes de que lleguen a Git.

Las pruebas unitarias sin base verifican métricas, FIT sintético, errores HTTP y límites transaccionales. CI además ejecuta Alembic sobre PostgreSQL 16 real con upgrade, `check`, downgrade y upgrade. Una prueba local o CI no sustituye Cloud SQL ni la URL desplegada.

## Frontend

La interfaz activa está en [`frontend/apps/nodo-web`](frontend/apps/nodo-web): una PWA Next.js con BFF, cookies `httpOnly`, módulo de entrenador y módulo mobile-first para atleta. Los clientes anteriores permanecen como referencia, pero no son el producto de despliegue.

## Contrato de ingesta FIT

`POST /api/v1/athletes/{athlete_id}/activities/fit`, autenticado y multipart:

- `file`: FIT de una sesión, máximo 10 MiB (configurable por `MAX_FIT_BYTES`).
- `rest_hr`, `max_hr`, `is_male`: parámetros opcionales de la convención TRIMP clásica; proporcionar los tres juntos. Son entradas técnicas temporales, no sustituyen un perfil validado del atleta.

Sin perfil o sin resumen FIT con duración de cronómetro y FC media, `trimp_score` es `null` y `trimp_status` indica datos insuficientes. La duración usa `total_timer_time`; en su ausencia usa el intervalo entre registros e indica `record_elapsed`, que puede incluir pausas. No se asume un registro por segundo.

Un archivo multisesión se rechaza explícitamente hasta implementar segmentación. La importación está vinculada al atleta autorizado y es idempotente por hash; fuera de desarrollo exige consentimiento vigente.

## API inicial de NODO

La API incluye sesiones rotables, identidad multirol, organizaciones, invitación y activación de atletas, recuperación de contraseña, planificación estructurada, molestias, revisión, grupos, plantillas, recomendaciones, consentimientos, exportación y desidentificación. Por seguridad, el alta de entrenadores queda cerrada salvo que se defina explícitamente `ALLOW_COACH_REGISTRATION=true` en un entorno local. Resend queda integrado en código para invitaciones y recuperación; sin dominio verificado, secretos y worker desplegado, el correo no está operativo. En desarrollo sin Resend el código de invitación aún puede compartirse manualmente.

## Colaboración

Trabajar en ramas breves, revisar PR entre las dos personas y mantener pruebas verdes. Acordar contratos antes de trabajar interfaz y backend por separado. Datos reales de atletas, archivos FIT, credenciales y configuración personal quedan fuera de Git. El plan comercial es una hipótesis a validar con pilotos, no una promesa de lanzamiento.

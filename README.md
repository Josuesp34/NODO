# NODO/ NODO Lab 

Plataforma en desarrollo para que entrenadores planifiquen, personalicen y revisen el entrenamiento de sus atletas, con datos de ejecución, descanso y molestias y ayuda de IA bajo aprobación humana. NODO es la experiencia del atleta y NODO Lab será la experiencia web del entrenador.

## Documentos para empezar juntos

- [Visión, alcance, objetivos y plan de ocho semanas](docs/PLAN_PRODUCTO.md).
- [Arquitectura y contratos propuestos](docs/ARQUITECTURA.md).
- [Contratos de la API base](docs/API_NODO.md).
- [Estado técnico, decisiones del refactor y pendientes](docs/ESTADO_TECNICO.md).

**Estado actual: base local de backend, no MVP listo para usuarios.** Ya incluye autenticación, relación entrenador-atleta y planificación estructurada. Todavía no hay interfaz, asociación obligatoria actividad-atleta, sincronización, copiloto, notificaciones ni gestión de molestias operativa. Los modelos de métricas diarias siguen siendo bocetos. No desplegar esta base como servicio público.

## Desarrollo local

Python 3.11 o 3.12 y Docker Desktop con motor Linux activo. Desde la raíz del repositorio, en PowerShell:

```powershell
cd backend/fit-parser
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Editar `.env`: cambiar la contraseña de ejemplo y reflejarla en ambas URLs. `DATABASE_URL` usa `localhost` para Python local; `DOCKER_DATABASE_URL` usa `timescaledb` para la red de Compose. El archivo `.env` no se versiona.

```powershell
docker compose up -d timescaledb
.venv/Scripts/alembic.exe upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Para ejecutar también la API en contenedor, una vez inicializada la base y sin la API local ocupando el puerto:

```powershell
docker compose up -d --build fit-parser
```

API: [OpenAPI local](http://127.0.0.1:8000/docs). `GET /health` verifica TimescaleDB sin modificarla y devuelve 503 si no está disponible. No comprueba todo el esquema.

Alembic crea el esquema inicial en una base nueva y registra la versión aplicada. Antes de reutilizar una base existente, respaldar y revisar su esquema y ubicación. El Compose actual fija `PGDATA` al volumen declarado: la configuración anterior de la imagen HA podía guardar datos en otra ubicación. Este refactor no movió ni eliminó datos ni volúmenes. No ejecutar `down -v` para resolver incompatibilidades.

## Pruebas

```powershell
cd backend/fit-parser
.venv/Scripts/python.exe -m pytest -q
```

Las pruebas no requieren una base activa: verifican métricas, SDK FIT real con archivos sintéticos, errores HTTP y límites transaccionales con una sesión simulada. No sustituyen la integración real PostgreSQL/TimescaleDB, pendiente de ejecutar con Docker activo. CI ejecuta estas pruebas en Python 3.11 y 3.12.

## Contrato de ingesta de desarrollo

`POST /api/v1/upload-fit/`, multipart:

- `file`: FIT de una sesión, máximo 10 MiB (configurable por `MAX_FIT_BYTES`).
- `rest_hr`, `max_hr`, `is_male`: parámetros opcionales de la convención TRIMP clásica; proporcionar los tres juntos. Son entradas técnicas temporales, no sustituyen un perfil validado del atleta.

Sin perfil o sin resumen FIT con duración de cronómetro y FC media, `trimp_score` es `null` y `trimp_status` indica datos insuficientes. La duración usa `total_timer_time`; en su ausencia usa el intervalo entre registros e indica `record_elapsed`, que puede incluir pausas. No se asume un registro por segundo.

Un archivo multisesión se rechaza explícitamente hasta implementar segmentación. Reimportar una actividad todavía puede duplicarla: idempotencia y vinculación con atleta son tareas de P0. La API de ingesta se deshabilita cuando `ENVIRONMENT` no es `development`.

## API inicial de NODO

La API ya incluye autenticación con sesiones rotables, invitación de atletas y planificación estructurada. Consultar [API_NODO.md](docs/API_NODO.md) antes de comenzar NODO o NODO Lab. Por seguridad, el alta de entrenadores queda cerrada salvo que se defina explícitamente `ALLOW_COACH_REGISTRATION=true` en un entorno local. La invitación devuelve el token solo como soporte temporal de desarrollo; el envío de correo seguro se implementará antes de abrir un piloto.

## Colaboración

Trabajar en ramas breves, revisar PR entre las dos personas y mantener pruebas verdes. Acordar contratos antes de trabajar interfaz y backend por separado. Datos reales de atletas, archivos FIT, credenciales y configuración personal quedan fuera de Git. El plan comercial es una hipótesis a validar con pilotos, no una promesa de lanzamiento.

# SaaS de entrenamiento con copiloto

Plataforma en desarrollo para que entrenadores planifiquen, personalicen y revisen el entrenamiento de sus atletas, con datos de ejecución, descanso y molestias y ayuda de IA bajo aprobación humana.

## Documentos para empezar juntos

- [Visión, alcance, objetivos y plan de ocho semanas](docs/PLAN_PRODUCTO.md).
- [Arquitectura y contratos propuestos](docs/ARQUITECTURA.md).
- [Estado técnico, decisiones del refactor y pendientes](docs/ESTADO_TECNICO.md).

**Estado actual: base local de backend, no MVP listo para usuarios.** Existe importación FIT de una sesión y cálculos aislados. Todavía no hay interfaz, autenticación, asociación obligatoria atleta–actividad, sincronización, copiloto ni gestión de molestias operativa. Los modelos de planes y métricas diarias son bocetos. No desplegar esta base como servicio público.

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
.venv/Scripts/python.exe -m app.create_tables
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Para ejecutar también la API en contenedor, una vez inicializada la base y sin la API local ocupando el puerto:

```powershell
docker compose up -d --build fit-parser
```

API: [OpenAPI local](http://127.0.0.1:8000/docs). `GET /health` verifica TimescaleDB sin modificarla y devuelve 503 si no está disponible. No comprueba todo el esquema.

El bootstrap crea tablas nuevas; **no migra bases existentes**. Antes de reutilizar una base antigua, respaldar y revisar su esquema y ubicación. El Compose actual fija `PGDATA` al volumen declarado: la configuración anterior de la imagen HA podía guardar datos en otra ubicación. Este refactor no movió ni eliminó datos ni volúmenes. No ejecutar `down -v` para resolver incompatibilidades.

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

## Colaboración

Trabajar en ramas breves, revisar PR entre las dos personas y mantener pruebas verdes. Acordar contratos antes de trabajar interfaz y backend por separado. Datos reales de atletas, archivos FIT, credenciales y configuración personal quedan fuera de Git. El plan comercial es una hipótesis a validar con pilotos, no una promesa de lanzamiento.

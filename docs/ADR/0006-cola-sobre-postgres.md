# ADR 0006: la cola persistente se implementa sobre Postgres, no sobre Redis

**Estado:** aceptada el 14 de septiembre de 2026. Se implementa en la fase F5 de `../PLAN_EJECUCION.md`. Todavía no está construida.

## Contexto

El ADR 0002 exige una cola persistente para ingesta, recálculos y tareas de IA: nada de eso puede correr dentro de la petición HTTP, y los reintentos tienen que sobrevivir a un reinicio. Lo que no fija es con qué.

La opción habitual es Celery o ARQ con Redis. Eso añade una pieza de infraestructura más que instalar, vigilar, respaldar y pagar en el piloto, cuando el volumen esperado es de decenas de atletas y unos pocos eventos por atleta al día.

## Decisión

La cola es una tabla en la base que ya existe.

- Tabla `jobs(kind, payload, run_after, attempts, locked_by, locked_at, status, last_error)`.
- El despachador toma trabajo con `SELECT … FOR UPDATE SKIP LOCKED`, que permite varios workers sin que dos tomen el mismo job.
- `worker.py` corre como proceso aparte, con su propio servicio en Docker Compose.
- Reintentos con backoff, límite de intentos (`JOB_MAX_ATTEMPTS`) y, al agotarse, el job termina en una **bandeja de fallos** visible, no en un log que nadie lee.
- Un job interrumpido a mitad se retoma tras reiniciar el worker: el estado vive en la base, no en memoria.
- Encolar es idempotente respecto de `ingestion_events`: recibir dos veces el mismo webhook no produce dos actividades.

## Consecuencias

- Un job y los datos que produce comparten transacción y respaldo. El backup de la base incluye la cola; no hay dos sistemas que restaurar en orden.
- El polling añade carga a Postgres. A este volumen es despreciable; el intervalo es configurable (`WORKER_POLL_INTERVAL_SECONDS`).
- No hay panel de cola de regalo. Hay que construir la vista de bandeja de fallos y las métricas de la cola, que la fase F12 pide de todas formas.
- Si el volumen lo exige, migrar a ARQ + Redis es un cambio local al despachador, porque el contrato del job (`kind`, `payload`, reintentos, estado) no depende del almacén.
- Compose gana un servicio `worker`. `docker compose down -v` sigue prohibido: destruiría la cola junto con los datos.

## Alternativas descartadas

- **Celery + Redis.** Estándar y bien documentado. Añade broker y, en la práctica, también un backend de resultados; dos piezas más para un piloto que todavía no tiene hosting contratado.
- **`BackgroundTasks` de FastAPI.** Es lo que evita el ADR 0002: vive en el proceso de la API y se pierde en cada reinicio o despliegue.
- **Cron que barre tablas.** Suficiente para recálculos periódicos, insuficiente para webhooks: no da reintento por elemento, ni backoff, ni estado por trabajo.

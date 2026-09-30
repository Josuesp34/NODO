# ADR 0007 — Particionado nativo de PostgreSQL en lugar de TimescaleDB

Fecha: 17 de septiembre de 2026
Estado: **aceptado**, no implementado. Lo implementa la fase **FA** del `PLAN_EJECUCION.md`.
Sustituye la elección de TimescaleDB heredada del esquema inicial y resuelve el desvío 3 del cierre de F0.

## Contexto

El esquema declara `telemetry_records` como hypertable de TimescaleDB. La migración `0001_nodo_core`
ejecuta `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE` al abrir y
`SELECT create_hypertable('telemetry_records', 'timestamp', …)` al cerrar. El plan de ejecución
preveía además `observations` como segunda hypertable en F7.

Al elegir Google Cloud como destino de despliegue aparecieron tres hechos que la decisión original
no contemplaba:

1. **Cloud SQL para PostgreSQL no soporta la extensión `timescaledb`.** No está en su lista de
   extensiones permitidas y no hay forma de instalarla. AlloyDB tampoco.
2. **Tiger Cloud, el Timescale gestionado por su propio fabricante, sólo se hospeda en AWS y Azure.**
   La API en Google Cloud hablando con la base en otra nube significa latencia por consulta y egreso
   facturado en cada lectura.
3. **Las funciones que justifican TimescaleDB no están en la edición Apache 2.** La compresión
   columnar, los continuous aggregates, las políticas de retención y `time_bucket_gapfill` están bajo
   la Timescale License, que prohíbe explícitamente ofrecerlas como servicio gestionado. Por eso
   Aiven —que sí ofrece TimescaleDB y sí corre en regiones de Google Cloud— entrega la edición Apache 2:
   hypertables y `time_bucket`, nada más. Su propia documentación advierte que `time_bucket_gapfill`
   no está disponible.

De ahí se sigue el punto que decide: **cualquier TimescaleDB gestionado que corra en Google Cloud da
hypertables y poco más, y eso PostgreSQL nativo ya lo hace.** Quedarse con la extensión sólo tiene
sentido autoalojando la base, que es precisamente lo que no queremos hacer para un piloto de una a
tres cuentas de entrenador.

### Qué volumen manejamos en realidad

Setenta atletas entrenando seis horas por semana, con registros a un hertz, producen alrededor de
**78 millones de filas al año** en `telemetry_records`: unos 7 a 8 GB sin comprimir. A los precios de
almacenamiento SSD de Cloud SQL eso ronda **1.30 USD al mes** el primer año. Ése es el costo real de
no tener compresión a nuestra escala.

Hay además un rasgo del diseño que lo vuelve menos grave todavía: `daily_load` guarda el resumen
diario precalculado. El calendario, la curva de forma y la comparación plan contra ejecución nunca
leen telemetría cruda. La telemetría se lee al abrir **una** actividad, que es el patrón donde el
particionado por tiempo rinde perfecto y la compresión da igual.

## Decisión

`telemetry_records` y, cuando se cree en F7, `observations` dejan de ser hypertables y pasan a ser
**tablas particionadas por rango sobre su columna de tiempo**, con `pg_partman` administrando la
creación y el retiro de particiones, y **BRIN** como índice sobre la columna de tiempo.

La migración `0001_nodo_core` deja de crear la extensión y deja de llamar a `create_hypertable`.

Detalle que hace el cambio barato: la clave primaria de `telemetry_records` ya es
`(activity_id, timestamp)`. PostgreSQL exige que la clave de partición forme parte de toda clave
única o primaria, y `timestamp` ya está ahí, así que **`PARTITION BY RANGE (timestamp)` es legal sin
tocar la clave primaria ni ninguna consulta existente**.

`pg_partman` y `pg_cron` están soportados en Cloud SQL, así que la administración de particiones y
la retención corren dentro de la base, sin infraestructura adicional.

## Consecuencias

**Lo que ganamos.** Cloud SQL gestionado: copias de seguridad automáticas, recuperación a un punto en
el tiempo, IP privada, réplicas de lectura y parches sin trabajo nuestro. Eso cubre de entrada la
condición de `PILOT_READINESS.md` que pide «backups automáticos y una restauración comprobada», que de
otro modo tendríamos que construir sobre una máquina virtual propia. El CI también se simplifica: las
migraciones se verifican contra un `postgres:16` normal, sin necesidad del contenedor
`timescale/timescaledb-ha` como servicio.

**Lo que perdemos.** La compresión columnar, cuantificada arriba. Y las funciones de relleno de
huecos —`time_bucket_gapfill`, LOCF, interpolación— que habrá que escribir a mano con
`generate_series`, `LEFT JOIN` y funciones de ventana cuando F7 las necesite. Es más trabajo, no un
impedimento.

**Equivalencias que hay que conocer al escribir código.** `time_bucket()` se sustituye por
`date_bin()`, en el núcleo de PostgreSQL desde la versión 14. Los continuous aggregates se sustituyen
por vistas materializadas refrescadas desde la cola `jobs` del ADR 0006, que de todas formas ya vamos
a construir en F5.

**Reversibilidad.** Si el volumen llegara a justificar TimescaleDB, volver es reimportar a una
instancia nueva con la extensión, no rehacer el producto. Las consultas escritas contra tablas
particionadas funcionan igual sobre una hypertable.

## Alternativas descartadas

**Tiger Cloud en AWS con la API en Google Cloud.** Da la versión completa de TimescaleDB, incluida la
compresión, y no requiere cambiar una línea de código. Se descarta porque parte cada consulta entre
dos nubes: latencia añadida en el camino crítico y egreso facturado, a cambio de ahorrar alrededor de
un dólar mensual de almacenamiento.

**Aiven para PostgreSQL en una región de Google Cloud.** Mantiene la extensión y la base junto a la
API. Se descarta porque su edición Apache 2 no incluye compresión ni continuous aggregates, que son
la razón de usar TimescaleDB. Pagaríamos un proveedor adicional por hypertables que Cloud SQL nos da
como particiones.

**TimescaleDB autoalojado en una máquina virtual de Compute Engine.** Es lo más barato y conserva
todo. Se descarta porque las copias de seguridad, la recuperación a un punto en el tiempo, los
parches y la disponibilidad pasan a ser trabajo nuestro, justo en las condiciones que
`PILOT_READINESS.md` exige comprobar antes de admitir atletas reales. Con una a tres cuentas de
entrenador no hay quien atienda esa operación.

**Dejar la hypertable y decidir al desplegar.** Se descarta porque F3, F5 y F7 traen migraciones que
se construirían sobre un supuesto que ya sabemos falso, y porque hoy no hay datos reales: éste es el
momento más barato del proyecto para cambiarlo.

## Fase que lo implementa

**FA · Esquema sin Timescale**, inmediatamente después de F0 y antes de F1.

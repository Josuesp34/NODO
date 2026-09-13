# Base técnica de la nueva etapa

13 de septiembre de 2026.

## Alcance de la base actual

Se incorpora un refactor acotado y la base del MVP; aún no se construye el producto completo.

Cambios realizados:

- Imports de modelos corregidos y registro de planes y métricas diarias en metadata.
- Eliminada la inicialización duplicada/circular de `core`; Alembic es la única vía de cambio de esquema.
- Configuración de base de datos por entorno, ejemplo sin credenciales reales y puertos Compose ligados a localhost.
- Health check de lectura, sin crear extensiones, con respuesta 503 ante indisponibilidad.
- FIT: validación de contenido, tamaño, timestamps y rechazo explícito de multisesión; decodificación fuera del event loop.
- Conservación de sensores faltantes como nulos; orden y deduplicación de timestamps dentro del archivo. Esto NO deduplica importaciones completas.
- Duración desde cronómetro de sesión o fallback identificado de tiempo transcurrido; sin supuesto de un registro por segundo.
- TRIMP con perfil explícito y resumen suficiente; no se inventan parámetros del atleta. Fórmula centralizada en dominio.
- CTL/ATL diarios con `alpha=1/tau`; TSB al inicio del día. Eliminado el cálculo automático mal etiquetado como ACWR. Los campos ORM antiguos se mantienen, sin producir valores nuevos de ACWR.
- Excepciones HTTP conservan 400/413/422; fallos de persistencia realizan rollback sin exponer detalles internos.
- Pruebas y CI; guía de trabajo y plan de producto para dos personas.
- Autenticación con sesiones rotables, invitación y activación de atletas, y aislamiento entrenador-atleta.
- Planeación por bloques y sesiones estructuradas, publicación y control de versiones para evitar sobrescrituras.
- Migración inicial Alembic y contratos de API documentados.
- Workspace inicial con NODO web y móvil; NODO Lab queda definido como módulo de entrenador sobre el cliente HTTP compartido.
- Dependencias de frontend e imagen TimescaleDB fijadas para instalaciones reproducibles; CI valida backend, migraciones y frontend.

## Convenciones de cálculo

TRIMP utiliza `duración_min × reserva_FC × A × exp(B × reserva_FC)`, con `(A,B)=(0.64,1.92)` o `(0.86,1.67)`. Los coeficientes A faltaban en el código y en la fórmula mostrada en el PDF original. La selección clásica se conserva como entrada técnica explícita; el modelo de perfil y su revisión con el entrenador quedan pendientes. Fuente: [Journal of Applied Physiology](https://journals.physiology.org/doi/10.1152/japplphysiol.00482.2003).

No calcular TRIMP si faltan el perfil, FC media de sesión o `total_timer_time`. La FC media calculada sobre registros se puede mostrar como resumen descriptivo, pero no se usa automáticamente para TRIMP, pues el muestreo puede ser irregular.

CTL/ATL son funciones aisladas, no un historial operativo. El código que las consuma debe procesar un día local completo, incluir descansos, recalcular cargas históricas y persistir valores sin redondeo intermedio. La nueva convención TSB usa el cierre del día anterior. No mezclar los valores antiguos y nuevos en una serie sin recalcularla.

## Todavía pendiente

Calendario y editor de sesiones; identidad multirol y relaciones entrenador-atleta múltiples; asociación obligatoria actividad-atleta, idempotencia, cola de ingestión, conectores, datos diarios normalizados, reportes de molestias, notificaciones y copiloto. El servicio actual no recibe ni interpreta recuperación diaria ni reportes físicos; esos flujos quedan especificados en los documentos de producto y arquitectura.

La base conserva actividad sin atleta para desarrollo; por ello la ingesta no está habilitada fuera de `development`. Esa restricción no sustituye autenticación y no convierte un despliegue público de desarrollo en seguro. El límite de lectura FIT tampoco reemplaza un límite de cuerpo HTTP en el proxy antes de parsear multipart.

La preparación para piloto tiene condiciones explícitas en `docs/PILOT_READINESS.md`; no abrir acceso externo hasta cumplirlas.

## Validación

Las pruebas cubren cálculos, datos faltantes, muestreo irregular, FIT sintético con SDK real, rechazos HTTP, registro ORM, rollback, autenticación y planeación. En la validación actual, las 36 pruebas pasaron y se levantó TimescaleDB local, se aplicaron las migraciones y `GET /health` respondió 200 contra PostgreSQL real. También se comprobó CORS para NODO en `http://localhost:3000`.

Docker Desktop en Windows requiere preparar el volumen de la imagen HA con UID 1000; `timescaledb-init` lo hace automáticamente. La base local usa el puerto `5433`, porque `5432` estaba ocupado. API y base se validaron en contenedores locales; esta configuración sigue siendo sólo de desarrollo.

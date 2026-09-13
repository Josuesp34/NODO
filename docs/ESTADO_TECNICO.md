# Base técnica de la nueva etapa

13 de septiembre de 2026.

## Alcance de este commit

Se incorpora el trabajo local pendiente y un refactor acotado; no se construye el MVP completo en este commit. El repositorio ya tenía un commit `aaed0e0` titulado `first commit`. Esta entrega continúa ese historial.

Cambios realizados:

- Imports de modelos corregidos y registro de planes y métricas diarias en metadata.
- Eliminada la inicialización duplicada/circular de `core`; bootstrap explícito único.
- Configuración de base de datos por entorno, ejemplo sin credenciales reales y puertos Compose ligados a localhost.
- Health check de lectura, sin crear extensiones, con respuesta 503 ante indisponibilidad.
- FIT: validación de contenido, tamaño, timestamps y rechazo explícito de multisesión; decodificación fuera del event loop.
- Conservación de sensores faltantes como nulos; orden y deduplicación de timestamps dentro del archivo. Esto NO deduplica importaciones completas.
- Duración desde cronómetro de sesión o fallback identificado de tiempo transcurrido; sin supuesto de un registro por segundo.
- TRIMP con perfil explícito y resumen suficiente; no se inventan parámetros del atleta. Fórmula centralizada en dominio.
- CTL/ATL diarios con `alpha=1/tau`; TSB al inicio del día. Eliminado el cálculo automático mal etiquetado como ACWR. Los campos ORM antiguos se mantienen, sin producir valores nuevos de ACWR.
- Excepciones HTTP conservan 400/413/422; fallos de persistencia realizan rollback sin exponer detalles internos.
- Pruebas y CI; guía de trabajo y plan de producto para dos personas.

## Convenciones de cálculo

TRIMP utiliza `duración_min × reserva_FC × A × exp(B × reserva_FC)`, con `(A,B)=(0.64,1.92)` o `(0.86,1.67)`. Los coeficientes A faltaban en el código y en la fórmula mostrada en el PDF original. La selección clásica se conserva como entrada técnica explícita; el modelo de perfil y su revisión con el entrenador quedan pendientes. Fuente: [Journal of Applied Physiology](https://journals.physiology.org/doi/10.1152/japplphysiol.00482.2003).

No calcular TRIMP si faltan el perfil, FC media de sesión o `total_timer_time`. La FC media calculada sobre registros se puede mostrar como resumen descriptivo, pero no se usa automáticamente para TRIMP, pues el muestreo puede ser irregular.

CTL/ATL son funciones aisladas, no un historial operativo. El código que las consuma debe procesar un día local completo, incluir descansos, recalcular cargas históricas y persistir valores sin redondeo intermedio. La nueva convención TSB usa el cierre del día anterior. No mezclar los valores antiguos y nuevos en una serie sin recalcularla.

## Todavía pendiente

Autenticación, aislamiento de equipos, CRUD de atletas y planes, intervalos estructurados, laps persistidos, asociación obligatoria actividad-atleta, idempotencia, migraciones, cola de ingestión, frontend, conectores, datos diarios normalizados, reportes de molestias y copiloto. El servicio actual no recibe ni interpreta recuperación diaria ni reportes físicos; esos flujos quedan especificados en los documentos de producto y arquitectura.

La base conserva actividad sin atleta para desarrollo; por ello la ingesta no está habilitada fuera de `development`. Esa restricción no sustituye autenticación y no convierte un despliegue público de desarrollo en seguro. El límite de lectura FIT tampoco reemplaza un límite de cuerpo HTTP en el proxy antes de parsear multipart.

Las dependencias principales existentes se conservaron para limitar el refactor. Se deben revisar y actualizar antes del piloto externo. La imagen TimescaleDB sigue una etiqueta mutable del proyecto original; fijar una versión/digest tras validar Docker.

## Validación

Las pruebas cubren cálculos, datos faltantes, muestreo irregular, FIT sintético con SDK real, rechazos HTTP, registro ORM, rollback y health check. Las pruebas de API usan persistencia simulada y no demuestran escritura real en PostgreSQL ni creación de hypertables.

En esta sesión Docker Desktop no tenía motor Linux activo. No se ejecutó bootstrap real, build de contenedores ni prueba contra TimescaleDB. Antes de usar datos de pilotos, levantar Docker, verificar ubicación del volumen preexistente, hacer backup si aplica, inicializar una base de prueba nueva y comprobar una importación y consulta reales. Ningún dato o volumen existente se movió ni eliminó.

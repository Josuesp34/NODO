# Producto manual: cierre B2/B3

Paquete sobre `b3eea4b`, preparado para integración y despliegue por Josué. No crea recursos cloud.

## Contratos

- Actividades: `/athletes/{id}/activities` conserva lista compatible, paginación por limit/offset y headers X-Total-Count/X-Next-Offset; `/page` devuelve items/total/next_offset para la PWA. `/{activity_id}` entrega laps y cantidad de puntos recibidos.
- Vínculo: `PUT /athletes/{id}/activities/{activity_id}/link`, sesión publicada del mismo atleta/disciplina, expected_version y auditoría.
- Comparación: `GET /athletes/{id}/activities/comparison?start=&end=` (1–93 días locales). Herramientas internas pueden reutilizar `comparison_for_athlete(db,user,athlete_id,start,end)`.
- Historial: `/athletes/{id}/profile/history`, `/athletes/{id}/checkins?start=&end=`, `/complaints/{id}` (actualizaciones, revisión y decisiones).
- Competencias: PUT/DELETE con CAS en `/athletes/{id}/competitions/{competition_id}`.
- Molestias: evolución con versión/bloqueo, reapertura tras empeoramiento o actualización posterior al cierre; revisión CAS y prioridad explícita.
- Grupos: miembros autorizados y PUT/DELETE con CAS en `/groups/{id}/members/{athlete_id}`, disponibilidad individual.
- Plantillas: PUT con CAS en `/templates/{id}`; GET `/assignments`; POST `/apply` admite atletas/grupo y excepciones. `workout_refs` enlaza claves estables con id/version. Reaplicar datos idénticos no crea ni actualiza sesiones. Una nueva versión modifica los borradores originales y conserva publicados/ediciones individuales. Días no disponibles se señalan para revisión. Eliminar claves asignadas o reaplicar asignaciones antiguas sin trazabilidad devuelve 409 para conciliación manual.
- Propuestas: snapshot como evidencia, approve/modify/reject, validación completa de la sesión, CAS, una única decisión y lectura del resultado.

## Tiempo y faltantes

La prescripción se normaliza a UTC antes de persistir. Calendario, bloques y editor usan la zona IANA del atleta, sin depender de la zona del navegador.

Se compara duración sólo si todos los pasos usan duración y distancia sólo si todos usan distancia. Los laps se alinean cuando coincide su cantidad, explicitando la necesidad de revisar segmentación. Carrera usa s/km; natación s/100 m. No se infieren segmentos de triatlón ni cumplimiento por falta de sincronización. Carga sin observación se muestra null/not_observed, aunque el modelo conserve decaimiento calculado.

FIT guarda distancia de SESSION o delta de contador monotónico de RECORD; ausencia=NULL. Velocidad sólo si existe en SESSION. La migración convierte ceros históricos del valor predeterminado anterior en NULL.

El helper `daily_load_horizon(from_date,recorded_dates,now,timezone)` incluye descansos hasta hoy; root integra su uso en jobs.

## Pantallas e integración

Nuevas: `/athlete/activities`, `/athlete/activities/[activityId]`, `/coach/athletes/[athleteId]/activities`. Competencias se integran a perfil/calendario; grupos, plantillas, molestias y propuestas conservan sus rutas.

Root integra navegación/worker y prueba E2E del conjunto con el corpus sintético. No se afirma publicación, uso con atletas reales ni revisión humana de Josué.

## Validación reproducible

- Backend: pytest completo; PostgreSQL opcional con `TEST_PRODUCT_DATABASE_URL` apuntando a una base terminada en `_test`. El fixture reinicia únicamente el schema de esa base de prueba.
- Caso PostgreSQL: dos decisiones concurrentes responden 200/409 y dejan una Decision y una única actualización de versión.
- Alembic: base vacía 0001→0006, downgrade0006→0005 y upgrade0006. 0006 contempla tablas creadas desde metadata vigente por 0004.
- Frontend: typecheck, build:web, build:lab, test:web. Evidencia final y conteos en la entrega del commit.

# ADR 0001: identidad única y capacidades múltiples

**Estado:** aceptada para la siguiente migración de producto.

## Decisión

Una persona tiene una sola cuenta NODO y puede acumular capacidades de atleta, entrenador y staff. `is_superuser` se conserva como capacidad administrativa de plataforma, independiente de las capacidades deportivas.

El modelo actual `users.role` y `users.coach_id` es transitorio. Antes de abrir pilotos se sustituirá por:

- `user_roles(user_id, role)` para capacidades de producto.
- `coach_athlete_assignments(coach_id, athlete_id, status, timestamps)` para relaciones explícitas y múltiples.
- `organizations` y `organization_memberships` cuando el piloto requiera varios coaches o equipos.

## Consecuencias

- `/auth/me` devolverá una lista de capacidades y la interfaz NODO mostrará los módulos disponibles.
- NODO Lab se habilitará por capacidad de entrenador; NODO personal por capacidad de atleta.
- Las rutas de planeación autorizarán mediante una asignación activa, nunca mediante un `athlete_id` enviado por el cliente sin verificación.
- La migración deberá copiar los roles y relaciones actuales, mantener compatibilidad temporal del contrato y añadir pruebas de una persona atleta-entrenador.

No iniciar una integración de equipo, pagos o acceso de staff sobre el modelo actual de rol único.

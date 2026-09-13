# Cómo colaborar en NODO

## Flujo de trabajo

`dev` es la rama de integración. Crear una rama corta desde `dev`, abrir un PR y fusionar sólo con los checks verdes. `main` queda reservada para versiones aprobadas para despliegue.

Cada cambio debe incluir:

1. Un objetivo acotado y una explicación de la decisión.
2. Pruebas de la capa afectada o una justificación si no aplican.
3. Actualización del contrato API, migración o documentación cuando el cambio lo requiera.
4. Sin secretos, tokens, datos de atletas, archivos FIT ni artefactos generados.

## Definición de terminado

- Backend: `python -m pytest -q` y migraciones Alembic válidas.
- Frontend: `npm run typecheck` y `npm run build:lab`.
- Cambios de esquema: migración nueva, reversible cuando sea razonable y comprobada sobre una base limpia.
- Rutas protegidas: casos de permiso propio, permiso denegado y conflicto concurrente cuando corresponda.

## Convenciones de producto

NODO es la plataforma. NODO Lab es el módulo de entrenador. No asumir que una persona sólo puede ser atleta o entrenador: el modelo de capacidades múltiples definido en `docs/ADR/0001-multi-role-identity.md` es obligatorio antes de pilotos externos.

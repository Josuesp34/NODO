# Cómo colaborar en NODO

## Flujo de trabajo

`dev` es la rama de integración. Crear una rama corta desde `dev`, abrir un PR y fusionar sólo con los checks verdes. `main` queda reservada para versiones aprobadas para despliegue.

El trabajo va por fases: [`docs/PLAN_EJECUCION.md`](docs/PLAN_EJECUCION.md) define F0 a F13 y cada una usa una rama `feat/fN-slug`. Una fase no empieza antes de que la anterior esté validada a mano. Si aparece trabajo que el plan no contempla, se anota en la sección "Desvíos" del plan y se decide en equipo antes de ampliar el alcance.

Cada cambio debe incluir:

1. Un objetivo acotado y una explicación de la decisión.
2. Pruebas de la capa afectada o una justificación si no aplican.
3. Actualización del contrato API, migración o documentación cuando el cambio lo requiera.
4. Sin secretos, tokens, datos de atletas, archivos FIT ni artefactos generados.

## Preparar el entorno una vez por clon

```bash
python -m pip install -r backend/api/requirements-dev.txt
pre-commit install
```

Los ganchos corren `ruff`, higiene básica de archivos y un bloqueo explícito de `.env`, archivos FIT, `node_modules`, `__pycache__` y logs. `pre-commit run --all-files` revisa el repositorio completo sin commitear, y el CI ejecuta lo mismo.

## Definición de terminado

- Backend: `python -m ruff check .`, `python -m pytest -q` y migraciones Alembic válidas, todo desde `backend/api`.
- Frontend: `npm run typecheck` y `npm run build:lab`.
- Repositorio: `pre-commit run --all-files` limpio.
- Cambios de esquema: migración nueva, reversible cuando sea razonable y comprobada sobre una base limpia.
- Rutas protegidas: casos de permiso propio, permiso denegado y conflicto concurrente cuando corresponda.

## Convenciones de producto

NODO es la plataforma. NODO Lab es el módulo de entrenador. No asumir que una persona sólo puede ser atleta o entrenador: el modelo de capacidades múltiples definido en `docs/ADR/0001-multi-role-identity.md` es obligatorio antes de pilotos externos.

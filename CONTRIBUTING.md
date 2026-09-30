# Cómo colaborar en NODO

## Flujo de trabajo

`dev` es la rama de integración. Crear una rama corta desde `dev`, abrir un PR y fusionar sólo con los checks verdes. `main` queda reservada para versiones aprobadas para despliegue.

El alcance completo está en [`docs/PLAN_MAESTRO_NODO.md`](docs/PLAN_MAESTRO_NODO.md); [`docs/PLAN_EJECUCION.md`](docs/PLAN_EJECUCION.md) organiza la ejecución técnica y los ADR posteriores fijan decisiones específicas. El trabajo puede avanzar en carriles independientes, pero ningún requisito se marca terminado sin integración, prueba y evidencia en la matriz. Si aparece trabajo no contemplado, se registra como desvío y se decide antes de ampliar alcance.

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

- Backend: `python -m ruff check .`, `python -m ruff format --check .`, `python -m pytest -q` y migraciones Alembic válidas sobre PostgreSQL 16, todo desde `backend/api`.
- Frontend: `npm run typecheck`, `npm run test:web`, `npm run build:web` y `npm run build:lab`.
- Plataforma: `terraform fmt -check -recursive infra`, `terraform validate` en ambos entornos y `bash -n ops/*.sh`.
- Repositorio: `pre-commit run --all-files` limpio.
- Cambios de esquema: migración nueva, reversible cuando sea razonable y comprobada sobre una base limpia.
- Rutas protegidas: casos de permiso propio, permiso denegado y conflicto concurrente cuando corresponda.
- Release: SHA exacto → CI → digest escaneado → staging → promoción del mismo digest → migración → HTTPS/smoke. Tener un PR o Terraform válido no equivale a despliegue.

## Convenciones de producto

NODO es la plataforma. NODO Lab es el módulo de entrenador. No asumir que una persona sólo puede ser atleta o entrenador: el modelo de capacidades múltiples definido en `docs/ADR/0001-multi-role-identity.md` es obligatorio antes de pilotos externos.

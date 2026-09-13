# Guía para agentes de desarrollo

Antes de modificar el frontend, leer [el relevo de frontend para Antigravity](docs/ANTIGRAVITY_FRONTEND_HANDOFF.md), [el contrato de API](docs/API_NODO.md) y [la arquitectura](docs/ARQUITECTURA.md).

El producto tiene dos aplicaciones: **NODO Lab** (web para entrenadores) y **NODO** (móvil para atletas). Comparten la API FastAPI y tipos HTTP, pero no componentes visuales. No inventar endpoints ni representar como implementadas la recuperación, las molestias, los conectores de relojes o el copiloto: siguen pendientes en el backend.

No incluir archivos `.env`, tokens, datos de atletas, `node_modules`, capturas ni logs en Git. Mantener el contrato REST, manejar `401`, `403`, `404`, `409` y `422` de forma explícita y ejecutar las validaciones indicadas en el relevo.

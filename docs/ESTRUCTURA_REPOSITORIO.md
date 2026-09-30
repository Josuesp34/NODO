# Estructura del repositorio

Esta es la estructura estable para el MVP. Cada cambio debe entrar en la capa que le corresponde; evitar archivos de producto o pruebas en la raíz.

```text
NODO/
├── backend/
│   └── api/                      # FastAPI. Se llamó `fit-parser` hasta la fase F0.
│       ├── app/
│       │   ├── api/              # HTTP, contratos y autorización
│       │   ├── application/      # (todavía no existe) Casos de uso que componen dominio e infraestructura
│       │   ├── core/             # Configuración, seguridad y conexión de base
│       │   ├── domain/           # Reglas y cálculos deterministas
│       │   ├── infrastructure/   # Modelos ORM y proveedores externos
│       │   └── services/         # Procesamiento especializado, como FIT
│       ├── migrations/           # Cambios versionados de PostgreSQL
│       ├── tests/
│       │   ├── api/
│       │   ├── domain/
│       │   └── services/
│       ├── docker-compose.yml    # Servicios `api`, `worker` y `postgres`, sólo para local
│       ├── ruff.toml             # Reglas de estilo del backend
│       └── requirements*.txt
├── frontend/
│   ├── apps/
│   │   ├── nodo-web/             # PWA activa: coach, atleta y BFF
│   │   ├── nodo-lab/             # Referencia web anterior, compilada en CI
│   │   └── nodo-mobile/          # Experiencia móvil NODO (congelada, ver ADR 0003)
│   └── packages/
│       └── api-client/           # Contrato REST y tipos compartidos
├── docs/
│   ├── ADR/                      # Decisiones tomadas, numeradas y con estado
│   ├── PLAN_EJECUCION.md         # Secuencia FA/FB y fases; PLAN_MAESTRO_NODO conserva F0–F16
│   └── …                         # Producto, arquitectura y relevo técnico
├── infra/                       # Terraform staging/prod para GCP
├── ops/                         # Preflight, backup, restore, rollback y smoke
├── .github/workflows/            # Backend, frontend, higiene, plataforma, seguridad y deploy
├── .pre-commit-config.yaml       # Ganchos de commit para todo el repositorio
├── AGENTS.md                     # Contexto para agentes de desarrollo
└── README.md                     # Entrada para personas
```

`NODO Lab` no es un producto independiente: es un módulo para entrenadores dentro de NODO. Ambas experiencias viven en la PWA `frontend/apps/nodo-web`; las aplicaciones anteriores se conservan como referencias.

## Reglas de ubicación

- Una ruta FastAPI o esquema Pydantic pertenece a `app/api`.
- Una regla de negocio sin I/O pertenece a `app/domain`.
- Un caso de uso que compone reglas, repositorios o conectores pertenece a `app/application` o `app/services` según su responsabilidad.
- Persistencia, SDKs de dispositivos y proveedores externos pertenecen a `app/infrastructure`.
- Cada prueba va bajo la carpeta que refleje la capa validada.
- Documentación de decisiones queda en `docs`, no mezclada con el código. Una decisión con consecuencias de arquitectura se escribe como ADR numerado en `docs/ADR`.

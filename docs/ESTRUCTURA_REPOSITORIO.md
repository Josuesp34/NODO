# Estructura del repositorio

Esta es la estructura estable para el MVP. Cada cambio debe entrar en la capa que le corresponde; evitar archivos de producto o pruebas en la raíz.

```text
Saas-entrenamiento/
├── backend/
│   └── fit-parser/
│       ├── app/
│       │   ├── api/              # HTTP, contratos y autorización
│       │   ├── application/      # Casos de uso que coordinan dominio e infraestructura
│       │   ├── core/             # Configuración, seguridad y conexión de base
│       │   ├── domain/           # Reglas y cálculos deterministas
│       │   ├── infrastructure/   # Modelos ORM y proveedores externos
│       │   └── services/         # Procesamiento especializado, como FIT
│       ├── migrations/           # Cambios versionados de PostgreSQL
│       ├── tests/
│       │   ├── api/
│       │   ├── domain/
│       │   └── services/
│       ├── docker-compose.yml
│       └── requirements*.txt
├── frontend/
│   ├── apps/
│   │   ├── nodo-lab/             # Módulo web de entrenador dentro de NODO
│   │   └── nodo-mobile/          # Experiencia móvil NODO
│   └── packages/
│       └── api-client/           # Contrato REST y tipos compartidos
├── docs/                         # Producto, arquitectura y relevo técnico
├── .github/                      # Automatización de repositorio
├── AGENTS.md                     # Contexto para agentes de desarrollo
└── README.md                     # Entrada para personas
```

`NODO Lab` no es un producto independiente: es un módulo para entrenadores dentro de NODO. La experiencia de atleta existe en web y móvil; la de entrenador empieza en web y comparte la misma identidad.

## Reglas de ubicación

- Una ruta FastAPI o esquema Pydantic pertenece a `app/api`.
- Una regla de negocio sin I/O pertenece a `app/domain`.
- Un caso de uso que compone reglas, repositorios o conectores pertenece a `app/application` o `app/services` según su responsabilidad.
- Persistencia, SDKs de dispositivos y proveedores externos pertenecen a `app/infrastructure`.
- Cada prueba va bajo la carpeta que refleje la capa validada.
- Documentación de decisiones queda en `docs`, no mezclada con el código.

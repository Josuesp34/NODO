import os

# Debe ocurrir antes de importar app; nunca se usa una base real en estas pruebas.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test"
os.environ["ENVIRONMENT"] = "development"

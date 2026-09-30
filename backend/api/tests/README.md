# Pruebas del backend

Las pruebas se organizan por la capa que validan:

- `api/`: contratos HTTP, autenticación, autorización y flujos de planeación.
- `domain/`: fórmulas y reglas puras, sin base de datos ni red.
- `services/`: interpretación y procesamiento de archivos FIT.

`conftest.py` contiene sólo fixtures compartidos. Las pruebas unitarias usan SQLite en memoria cuando necesitan persistencia; la comprobación de PostgreSQL 16 se realiza mediante Docker y Alembic en local y CI. SQLite no verifica particiones ni comportamiento de PostgreSQL.

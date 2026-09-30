# Corpus sintético: 70 atletas × 12 semanas

`ops/qa_corpus.py` prepara fixtures exclusivamente de desarrollo y mide consultas HTTP autenticadas contra API/PostgreSQL. No crea recursos cloud, envía mensajes ni utiliza datos reales. Las cuentas son `qa-*@example.com`; su contraseña predeterminada pública es únicamente para estas cuentas locales.

## Preparación

Ejecutar Alembic desde `backend/api` contra PostgreSQL 16 de desarrollo. Debe existir la partición predeterminada de telemetría de 0004 o particiones suficientes para las fechas del corpus. El generador no crea ni elimina particiones ni otros recursos de infraestructura.

Desde la raíz del repositorio, con el Python del backend:

```bash
export ENVIRONMENT=development
export NODO_SYNTHETIC_QA=1
# DATABASE_URL debe apuntar a PostgreSQL local o al servicio postgres de Docker.
# Exportarla desde la configuración local; no copiar credenciales a Git.
python ops/qa_corpus.py seed --output .local/qa-corpus.seed.json
```

Ambas guardas son obligatorias. La siembra rechaza servidores remotos y cuentas QA preexistentes sin un marcador compatible. Una segunda ejecución del mismo config devuelve `already_seeded` sin modificar registros. No elimina ni reemplaza datos existentes. No usar este fixture en producción. `NODO_QA_PASSWORD` permite una contraseña local alternativa sin escribirla en el manifiesto o reporte.

`ops/fixtures/qa-corpus-v1.json` fija fecha inicial, disciplinas, zonas, descansos y frecuencia de casos. Cada perfil tiene 84 días de carga y check-in; faltantes permanecen explícitos. Se incluye origen/fuente, parámetros fisiológicos, competencias, grupos, tres puntos de telemetría por actividad, laps de carrera/natación/ciclismo, triatlón sin inventar segmentación comparable, importaciones tardías y días que cruzan medianoche. Los duplicados se intentan dentro de savepoints y deben rechazarse por las restricciones reales de PostgreSQL. Las molestias conservan historia de cierre/reapertura y revisión prioritaria.

## Medición real

Arrancar la API con la misma base y ejecutar:

```bash
python ops/qa_corpus.py benchmark \
  --url http://127.0.0.1:8000/api/v1 \
  --concurrency 8 --rounds 2 \
  --output .local/qa-corpus.benchmark.json
```

Se autentica el coach sintético, consulta los 70 atletas y distribuye 280 peticiones de calendario/actividades entre ocho hilos. Incluye transporte HTTP, autorización, consulta PostgreSQL y lectura JSON; un calentamiento precede a los tiempos. Revisa paginación, denegación de coach revocado, visibilidad de molestias, comparación en las cuatro disciplinas y que siete atletas multirol no obtengan acceso a borradores por una capacidad coach sin asignación.

Objetivos: p95 calendario <1.5 s y actividades <1 s. Si falla un objetivo, el proceso termina con código 1. El reporte contiene SHA/config/script, estado de cambios locales, CPU/arquitectura/OS, concurrencia, rondas, p50/p95/máximo y casos verificados. No contiene tokens, contraseña, headers ni payloads de atletas.

Los tiempos de una máquina local no certifican el rendimiento de producción. Repetir en el entorno de Josué con iguales datos, recursos y concurrencia; conservar el JSON fuera de Git. Sólo afirmar una medición asociada a su SHA y estado de trabajo indicados.

## Pruebas

```bash
python -m pytest -q ops/tests/test_qa_corpus.py
# Desde backend/api:
python -m pytest -q
```

El corpus permite probar backfill/recalcular carga con el worker integrado por root. La siembra calcula sus 84 días con la función de dominio determinista; no afirma que el worker procesó esos datos. La aplicación/API incluye una prueba específica de permisos multirol para el calendario.

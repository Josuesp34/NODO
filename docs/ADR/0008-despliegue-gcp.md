# ADR 0008 — Despliegue en Google Cloud sobre Cloud Run y Cloud SQL

Fecha: 17 de septiembre de 2026
Estado: **aceptado**, no implementado. Lo implementan las fases **FB** (entorno de validación) y
**F12** (producción) del `PLAN_EJECUCION.md`.
Depende del ADR 0007 (la base es PostgreSQL gestionado, sin TimescaleDB).

## Contexto

Hasta ahora NODO sólo ha corrido en Docker Compose local. `docs/ARQUITECTURA.md` ya fijó que
«Kubernetes no es necesario para este piloto», pero no decía qué sí. El plan original dejaba todo el
despliegue para F12, al final, lo que significa descubrir los problemas de infraestructura en el
momento más caro.

Las piezas que hay que hospedar, según lo que el plan construye:

- **API** — FastAPI, HTTP, sin estado. Existe hoy.
- **Worker** — proceso persistente que consume la tabla `jobs` con `SELECT … FOR UPDATE SKIP LOCKED`.
  No atiende HTTP, corre siempre. Llega en F5 (ADR 0006).
- **PWA** — Next.js 16. No puede ser un sitio estático: el ADR 0004 pone la sesión en una cookie
  `httpOnly` emitida por route handlers del propio Next, así que necesita servidor. Llega en F2.
- **Base de datos** — PostgreSQL 16 particionado (ADR 0007).
- **Archivos FIT** — almacenamiento de objetos. Llega en F5.
- **Migraciones** — `alembic upgrade head`, que debe correr **antes** de que la revisión nueva reciba
  tráfico, y nunca al arrancar el contenedor.

## Decisión

**Dos proyectos de Google Cloud separados**, `nodo-staging` y `nodo-prod`, con la misma definición de
Terraform y distintas variables. Proyectos separados y no dos entornos en uno, porque la frontera de
facturación, de permisos y de borrado accidental es el proyecto, y en producción algún día habrá
datos reales de atletas.

| Pieza | Servicio | Por qué |
|---|---|---|
| API | **Cloud Run (service)** | Sin estado, tráfico irregular, escala a cero en staging |
| PWA | **Cloud Run (service)** | Next.js con servidor, requisito del ADR 0004 |
| Worker | **Cloud Run (worker pool)** | Sin endpoint HTTP, CPU siempre asignada, número de instancias fijo. Es el primitivo exacto para un consumidor de cola |
| Migraciones | **Cloud Run (job)** | Se ejecuta y termina. Se dispara desde el despliegue, antes de enrutar tráfico |
| Base | **Cloud SQL para PostgreSQL 16** | Copias automáticas, recuperación a un punto en el tiempo, IP privada, parches gestionados |
| Archivos FIT | **Cloud Storage** | Un bucket por entorno, sin acceso público, URLs firmadas |
| Imágenes | **Artifact Registry** | Una sola región, con limpieza por antigüedad |
| Secretos | **Secret Manager** | Montados como variables de entorno en el despliegue. Nunca en Git, nunca en la imagen |
| Despliegue | **GitHub Actions + Workload Identity Federation** | Sin llaves JSON de cuenta de servicio guardadas en GitHub |
| Infraestructura | **Terraform** en `infra/`, con `envs/staging` y `envs/prod` | Auditable y reproducible; no clics que nadie recuerda |

**Red.** Cloud SQL sin IP pública. Cloud Run llega por egreso directo a la VPC. La API y el worker
tienen su propia cuenta de servicio con `roles/cloudsql.client` y acceso sólo a los secretos que cada
uno necesita.

**Postura de disponibilidad, acordada para esta etapa.** Instancia zonal, sin alta disponibilidad
regional ni réplica de lectura. Copias automáticas diarias con recuperación a un punto en el tiempo
activada. Worker siempre encendido. Alertas básicas sobre errores 5xx, profundidad de la cola y
conexiones caídas. Con una a tres cuentas de entrenador, la alta disponibilidad multiplica el costo
sin comprar un riesgo que exista. Se revisa cuando haya entrenadores pagando.

**Staging escala a cero; producción no.** En staging la API y la PWA aceptan arranques en frío. En
producción la API lleva una instancia mínima para que un entrenador no pague el arranque en frío al
abrir el calendario.

## Consecuencias

**Cambios que esto exige en el código.** El `Dockerfile` del backend fija el puerto 8000 en el
`CMD`; Cloud Run inyecta `$PORT` y hay que respetarlo. La API debe confiar en `X-Forwarded-Proto`
para generar URLs correctas detrás del proxy de Cloud Run. Los logs tienen que salir en JSON a
`stdout` para que Cloud Logging los indexe, y sin datos personales, como ya exige F12.

**Lo que no cambia.** La aplicación sigue siendo la misma que corre en `docker compose` local. Compose
se conserva como entorno de desarrollo y como respaldo de portabilidad: si algún día hubiera que
salir de Google Cloud, lo que hay que rehacer es Terraform, no el producto.

**Costo.** Con la postura de arriba, el orden de magnitud esperado es de decenas de dólares mensuales
por entorno, dominado por Cloud SQL y por el worker siempre encendido. Hay que confirmarlo en la
calculadora de Google Cloud con la región elegida antes de crear nada, y poner un presupuesto con
alerta en cada proyecto el mismo día que se crea.

**Región.** Se elige una sola y se usa para todo. `us-central1` o `us-south1` por cercanía a
Guadalajara y por catálogo completo de servicios; decidir con la calculadora y dejarlo escrito aquí
al ejecutar FB.

## Alternativas descartadas

**Google Kubernetes Engine.** `docs/ARQUITECTURA.md` ya lo había descartado y se confirma: tres
contenedores y una base no justifican un plano de control ni el trabajo de operarlo.

**Una máquina virtual de Compute Engine con Docker Compose.** Es lo más barato y lo más parecido al
entorno local. Se descarta por la misma razón que en el ADR 0007: copias de seguridad, parches,
certificados y disponibilidad pasarían a ser trabajo manual nuestro, justo lo que
`PILOT_READINESS.md` exige demostrar.

**App Engine.** Cloud Run es su sucesor natural para cargas en contenedor y no tiene las restricciones
de entorno de App Engine.

**La PWA en Vercel y la API en Google Cloud.** Vercel hospeda Next.js mejor que nadie, pero parte el
despliegue en dos proveedores, dos facturas y dos modelos de secretos, y mete un salto de red entre
el BFF y la API. Se descarta por ahora; se reconsidera si el rendimiento de la PWA en Cloud Run
resulta insuficiente.

**Desplegar sólo en F12, como decía el plan original.** Se descarta: es la razón de que exista la
fase FB. Un entorno de validación temprano prueba la decisión del ADR 0007 contra Cloud SQL real
antes de que ocho fases se construyan encima, y le da a Brandon y a Josué algo que abrir en el
teléfono para validar cada fase.

## Fases que lo implementan

- **FB · Staging en Google Cloud**, después de FA: Terraform, Cloud SQL, API en Cloud Run, despliegue
  continuo. Sin worker ni PWA, que todavía no existen.
- **F2, F5** amplían el mismo Terraform cuando aparecen la PWA, el worker y el bucket de archivos.
- **F12 · Producción**: el segundo proyecto, con las nueve condiciones de `PILOT_READINESS.md`.

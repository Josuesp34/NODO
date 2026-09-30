# Base técnica de la nueva etapa

Actualizado el 14 de septiembre de 2026, al cerrar la fase F0 de [`PLAN_EJECUCION.md`](PLAN_EJECUCION.md).

## Fase F0 · Higiene, contratos y ADR

Lo que cambió, y nada más que eso: no se tocó comportamiento, esquema ni contrato de API.

- `backend/fit-parser` pasó a llamarse `backend/api`. La carpeta dejó de ser un extractor de archivos FIT hace varias entregas. Se actualizaron Compose (el servicio ahora es `api`), CI y toda la documentación.
- `ruff` entra como linter del backend, con reglas en `backend/api/ruff.toml` y versión fijada en `requirements-dev.txt`. `ruff check` está limpio. Las correcciones fueron de estilo: orden de imports, `Optional[X]` a `X | None`, `List` a `list`, `timezone.utc` a `UTC` e imports muertos.
- Tres arreglos de linter con algo de sustancia: `models/__init__.py` declara `__all__` (sus imports registran cada modelo en el metadata de SQLAlchemy y no son "imports muertos"); `sensor_value()` salió del bucle de telemetría en `app/api/routes.py`, donde se redefinía en cada registro; y el validador de zona horaria encadena `raise ... from None`.
- `pre-commit` entra con higiene básica, `ruff` y un gancho que rechaza `.env`, archivos FIT, `node_modules`, `__pycache__`, `.next` y logs. El CI corre lo mismo en un workflow nuevo.
- `.env.example` documenta las variables que el código ya lee y, en una sección aparte y comentada, las que cada fase futura necesitará. Están marcadas explícitamente como **no leídas todavía**.
- ADR 0003 (PWA única), 0004 (sesión como BFF), 0005 (conector intervals.icu) y 0006 (cola sobre Postgres) quedan escritos, con estado, alternativas descartadas y la fase que los implementa. Ninguno está implementado.
- `docs/PLAN_EJECUCION.md` vive en el repositorio y el README enlaza a él.

Verificación de esta fase: 39 pruebas verdes, `ruff check` limpio, `pre-commit run --all-files` limpio, `npm run typecheck` y `npm run build:lab` verdes, y la cadena de migraciones 0001 → 0003 aplicada sobre una base PostgreSQL nueva. La comprobación contra TimescaleDB real queda en el guion de validación humana; el desvío está registrado en el plan.

## Alcance de la base anterior

13 de septiembre de 2026.

Se incorpora un refactor acotado y la base del MVP; aún no se construye el producto completo.

Cambios realizados:

- Imports de modelos corregidos y registro de planes y métricas diarias en metadata.
- Eliminada la inicialización duplicada/circular de `core`; Alembic es la única vía de cambio de esquema.
- Configuración de base de datos por entorno, ejemplo sin credenciales reales y puertos Compose ligados a localhost.
- Health check de lectura, sin crear extensiones, con respuesta 503 ante indisponibilidad.
- FIT: validación de contenido, tamaño, timestamps y rechazo explícito de multisesión; decodificación fuera del event loop.
- Conservación de sensores faltantes como nulos; orden y deduplicación de timestamps dentro del archivo. Esto NO deduplica importaciones completas.
- Duración desde cronómetro de sesión o fallback identificado de tiempo transcurrido; sin supuesto de un registro por segundo.
- TRIMP con perfil explícito y resumen suficiente; no se inventan parámetros del atleta. Fórmula centralizada en dominio.
- CTL/ATL diarios con `alpha=1/tau`; TSB al inicio del día. Eliminado el cálculo automático mal etiquetado como ACWR. Los campos ORM antiguos se mantienen, sin producir valores nuevos de ACWR.
- Excepciones HTTP conservan 400/413/422; fallos de persistencia realizan rollback sin exponer detalles internos.
- Pruebas y CI; guía de trabajo y plan de producto para dos personas.
- Autenticación con sesiones rotables, invitación y activación de atletas, y aislamiento entrenador-atleta.
- Planeación por bloques y sesiones estructuradas, publicación y control de versiones para evitar sobrescrituras.
- Migración inicial Alembic y contratos de API documentados.
- Workspace inicial con NODO web y móvil; NODO Lab queda definido como módulo de entrenador sobre el cliente HTTP compartido.
- Dependencias de frontend e imagen TimescaleDB fijadas para instalaciones reproducibles; CI valida backend, migraciones y frontend.

## Convenciones de cálculo

TRIMP utiliza `duración_min × reserva_FC × A × exp(B × reserva_FC)`, con `(A,B)=(0.64,1.92)` o `(0.86,1.67)`. Los coeficientes A faltaban en el código y en la fórmula mostrada en el PDF original. La selección clásica se conserva como entrada técnica explícita; el modelo de perfil y su revisión con el entrenador quedan pendientes. Fuente: [Journal of Applied Physiology](https://journals.physiology.org/doi/10.1152/japplphysiol.00482.2003).

No calcular TRIMP si faltan el perfil, FC media de sesión o `total_timer_time`. La FC media calculada sobre registros se puede mostrar como resumen descriptivo, pero no se usa automáticamente para TRIMP, pues el muestreo puede ser irregular.

CTL/ATL son funciones aisladas, no un historial operativo. El código que las consuma debe procesar un día local completo, incluir descansos, recalcular cargas históricas y persistir valores sin redondeo intermedio. La nueva convención TSB usa el cierre del día anterior. No mezclar los valores antiguos y nuevos en una serie sin recalcularla.

## Todavía pendiente

El detalle operativo está en [PENDIENTES_MVP.md](PENDIENTES_MVP.md). Lo más urgente es presentar las sesiones publicadas en NODO web y móvil, consolidar refresh de sesión en el cliente y completar la edición de borradores. La identidad multirol avanzada, asociación obligatoria de actividad-atleta, idempotencia de ingesta, cola de trabajos, conectores, datos diarios normalizados, reportes de molestias, notificaciones y copiloto siguen fuera del MVP de prueba. El servicio actual no recibe ni interpreta recuperación diaria ni reportes físicos; esos flujos quedan especificados en los documentos de producto y arquitectura.

La base conserva actividad sin atleta para desarrollo; por ello la ingesta no está habilitada fuera de `development`. Esa restricción no sustituye autenticación y no convierte un despliegue público de desarrollo en seguro. El límite de lectura FIT tampoco reemplaza un límite de cuerpo HTTP en el proxy antes de parsear multipart.

La preparación para piloto tiene condiciones explícitas en `docs/PILOT_READINESS.md`; no abrir acceso externo hasta cumplirlas.

## Validación

Las pruebas cubren cálculos, datos faltantes, muestreo irregular, FIT sintético con SDK real, rechazos HTTP, registro ORM, rollback, autenticación y planeación. En la validación actual, las 39 pruebas pasaron, `alembic check` no detectó deriva de esquema, se levantó TimescaleDB local, se aplicaron las migraciones y `GET /health` respondió 200 contra PostgreSQL real. También se comprobó CORS para NODO en `http://localhost:3000`.

Docker Desktop en Windows requiere preparar el volumen de la imagen HA con UID 1000; `timescaledb-init` lo hace automáticamente. La base local usa el puerto `5433`, porque `5432` estaba ocupado. API y base se validaron en contenedores locales; esta configuración sigue siendo sólo de desarrollo.

## Actualización de construcción integral · 20 de septiembre de 2026

La precedencia vigente es `PLAN_MAESTRO_NODO.md` + `PLAN_EJECUCION.md` v2 + ADR 0007/0008. Por tanto, las referencias históricas de este documento a TimescaleDB o dos aplicaciones ya no describen el objetivo: producción usa PostgreSQL 16 particionado en Cloud SQL y una PWA única.

### Plataforma cerrada en código

- módulo Terraform reusable y raíces separadas de `staging`/`prod` para red, Cloud SQL privado, Storage, Artifact Registry, Secret Manager, IAM/WIF, API, PWA, migration job y worker pool opcional;
- budgets y alertas parametrizados pero desactivados hasta confirmar importes/canales;
- workflows con acciones fijadas por SHA para backend, migraciones PostgreSQL, frontend, contenedores, Terraform, CodeQL, OSV, Trivy, dependency review, staging y promoción a producción por digest;
- scripts y runbooks para preflight, backup, restore PITR a una instancia nueva, rollback de revisión y smoke;
- contratos de seguridad, costos, diseño, LLM, recuperación y lanzamiento, más matriz de trazabilidad.

Verificación local: `terraform fmt` y `terraform validate` pasaron para ambos entornos con Terraform 1.13.3 y providers Google 7.46.1; Bash y YAML pasaron parseo. No se ejecutó `terraform plan` ni `apply`, no se usaron credenciales y no existe evidencia de recursos o URL pública.

### Bloqueos reales para despliegue

1. Los Dockerfiles y assets de migración requeridos ya están presentes y el preflight de release pasa; falta completar los builds/scans de ambos contenedores en CI. Un build local de API se inició pero fue cancelado por límite de tiempo, no por un error del código.
2. Faltan selección/verificación humana de proyectos, región, billing/créditos, costo, dominio, correo, OAuth, proveedor IA y permisos.
3. Faltan branch protection, GitHub Environments con reviewers/variables y primera conexión WIF.
4. No se han ejecutado plan/apply, restore drill, dispositivos físicos, integraciones reales, E2E público, pentest ni GO comercial/legal.

Estado global honesto de esa pasada: **PARCIAL — construcción activa; no publicado ni vendible todavía**. La plataforma estaba preparada para revisión y plan, no equivalía a producción.

## Cierre funcional local · 20 de septiembre de 2026

La construcción posterior cerró el piloto acompañando el producto con una sola PWA y API multirol. El recorrido local completo quedó comprobado sobre PostgreSQL 16 real: alta de coach, invitación, activación de atleta, creación de sesión, publicación idempotente y lectura de la sesión publicada en “Hoy”. Durante este E2E se corrigieron dos defectos que la suite aislada no había detectado: normalización de capacidades granulares en la PWA y columnas de ciclo de vida con zona horaria en PostgreSQL.

Evidencia local actual:

- backend: `47 passed`, `ruff check` y pre-commit verdes;
- PostgreSQL 16: migraciones `upgrade → downgrade base → upgrade head`, tabla de telemetría particionada y recorrido E2E real;
- frontend: typecheck de todos los workspaces, `9/9` pruebas PWA y build Next de 34 rutas;
- imágenes API/PWA construidas; PWA standalone comprobada en `PORT=8080` con usuario no root;
- Terraform staging/prod validado, workflows YAML y runbooks Bash verificados;
- QA visual de landing, acceso, panel coach y sesión del atleta con la dirección dark/lima/coral de `DESIGN_SYSTEM.md`.

Estado global actual: **piloto funcional y vendible de forma acompañada en código; NO publicado y NO-GO de producción**. La carga FIT es funcional y cuenta con guía pública; la IA y la conexión de Intervals.icu siguen siendo simuladas, no integraciones reales. Persisten compuertas externas: credenciales y billing GCP, WIF/entornos GitHub, dominio/correo, OAuth real de Intervals.icu, proveedor IA real, preferencias push, CI remoto, plan/apply, restore drill, dispositivos, pentest y aprobación legal/comercial.

## Correo y decisiones de proveedor · 23 de septiembre de 2026

Se añadió el adaptador Resend con cola persistente e idempotencia, cuerpo/destinatario cifrados en reposo, borrado del payload tras éxito, invitaciones sin código visible en producción y recuperación de contraseña de un solo uso con revocación de sesiones. La PWA ofrece el formulario de recuperación. Pruebas locales cubren aceptación, cifrado, despacho simulado, respuesta genérica y revocación; **ningún email real fue enviado**. Sin dominio y cuenta verificada, estos flujos no son operativos en producción. Migraciones 0001→0005, `alembic check`, downgrade base y upgrade head quedaron verdes en un PostgreSQL 16 local y aislado; Cloud SQL continúa pendiente.

Las comparaciones actuales de datos deportivos e IA están en [DECISION_PROVEEDORES.md](DECISION_PROVEEDORES.md). La decisión deportiva aceptada es **Intervals.icu principal y FIT como respaldo permanente**; la elección final de IA sigue pendiente. Intervals.icu y los asistentes continúan en simulación; no se ha abierto acceso a un proveedor real.

## Preparación de entrega con Josué · 29 de septiembre de 2026

La entrega incorpora todo el piloto local a una rama revisable y corrige autorización tras revocar atletas, protección de escrituras BFF, dependencias Python, renovación de sesión, URL/IAM de la API Cloud Run, ejecución del worker y promoción segura del registro. El primer administrador se crea por un job acotado, sin habilitar endpoints development en producción. Validación integrada: 58 pruebas backend, 34 PWA, typecheck de los workspaces y build PWA de 37 rutas aprobados; Terraform staging/prod válido. La evidencia del SHA definitivo y el estado de CI se publica junto a la versión.

El plan vigente de relevo y producción está en [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md), con [mensaje para WhatsApp](MENSAJE_WHATSAPP_JOSUE.md) y [evidencia de validación](VALIDACION_HANDOVER.md). Brandon autorizó integrar el PR completo y desplegar. Siguen pendientes el proyecto/identidad/billing de NODO, dominio y configuraciones externas, adaptadores reales de Intervals/IA, pantallas y push, restore/monitoreo y pruebas físicas. No se verificó una URL de producción ni aceptación de Josué; el NO-GO de apertura a atletas reales sigue vigente.

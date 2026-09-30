# Handover de NODO con Josué

Fecha: 29 de septiembre de 2026. Responsable de entrega: Brandon.
Actualización de reparto: 30 de septiembre de 2026.

**Objetivo:** entregar una versión compartida y reproducible del código, revisar con Josué lo que funciona y cerrar el recorrido hasta producción con evidencia. Brandon autorizó el PR completo, integración y despliegue; esa autorización ya está dada. La apertura a atletas reales conserva los criterios de `LANZAMIENTO.md`.

**Estado:** código integrado y versión candidata publicada; proveedores reales y producción pendientes. Brandon no dispone de las respuestas sobre GCP, dominio, correo, OAuth e IA. Josué coordina la resolución de esos datos, accesos y decisiones con sus propietarios. Nuestro equipo asume el desarrollo, pruebas, configuración y despliegue que puedan ejecutarse con los permisos correspondientes para reducir el trabajo técnico que recibe Josué. La recepción y aceptación de Josué aún deben registrarse.

El reparto y la secuencia detallados están en [PLAN_CIERRE_PRE_HANDOVER.md](PLAN_CIERRE_PRE_HANDOVER.md). Es un plan de ejecución; no marca sus tareas nuevas como terminadas.

## 1. Qué se entrega

| Entrega | Qué existe | Límite actual |
|---|---|---|
| PWA única | Landing, acceso, activación, módulos coach/atleta, BFF, calendario, hoy/semana y detalle | Validación física y HTTPS desplegado pendientes |
| Identidad y planificación | Multirol, organizaciones, invitaciones, sesiones estructuradas, publicación y versiones | Job bootstrap seguro implementado; falta ejecutarlo en el entorno real |
| Datos deportivos | FIT autenticado, dueño obligatorio, deduplicación, laps/telemetría y cola persistente | Una sesión y hasta 10 MiB; Intervals no sincroniza realmente |
| Seguimiento | Perfil, check-in, molestias, bandeja, grupos, plantillas y propuestas aprobables | Hay contratos API sin toda su interfaz final |
| Privacidad/comercial | Consentimientos, exportación/desidentificación, cupos y cobros administrados | Legal, retención efectiva, soporte y precio por confirmar; no procesa tarjetas |
| Correo | Resend, cola cifrada, invitación y recuperación de un solo uso | Ningún envío real verificado; falta dominio/cuenta/secretos |
| Asistentes | Simuladores con contexto, citas, preview y confirmaciones | Falta proveedor real y conexión completa de las pantallas; chat atleta pendiente |
| Plataforma | Terraform staging/prod, Cloud Run/SQL, secretos, WIF, workflows y runbooks | Recursos, costo real, restauración y monitoreo no verificados |

Inventario preciso: [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md). Trazabilidad: [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md). Alcance completo: [PLAN_MAESTRO_NODO.md](PLAN_MAESTRO_NODO.md).

## 2. Versión y revisión

La entrega incluye todos los avances locales de NODO y las correcciones de publicación/seguridad. La base anterior es `98f2a9b` en `feat/f0-higiene`; el código activo es la PWA `frontend/apps/nodo-web`. Lab y Expo se conservan como referencias.

- Rama de trabajo: `codex/handover-josue`.
- Integración: PR completo a `dev`, después PR de release a `main`, sujeto a los checks y protecciones existentes.
- Versión de entrega: [`v0.4.0-rc.1`](https://github.com/Josuesp34/NODO/releases/tag/v0.4.0-rc.1); identifica un candidato y no una aplicación operativa en producción.
- PR completo: [#7](https://github.com/Josuesp34/NODO/pull/7). El estado de integración y la promoción a `main` se verifican en GitHub Release.
- La evidencia final de SHA, PRs, CI y publicación se registra en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md) y en GitHub Release.
- La versión de código conserva `v0.4.0-rc.1`. La [guía vigente en main](https://github.com/Josuesp34/NODO/blob/main/docs/HANDOVER_JOSUE.md) incorpora las aclaraciones posteriores de responsabilidades; el tag conserva su snapshot original.
- No utilizar un ZIP que omita archivos nuevos, `.env` compartidos ni una carpeta con cambios sin versionar como fuente de despliegue.

## 3. Arranque reproducible para Josué

Requisitos: Git, Python 3.11 o 3.12, Node 22 y Docker Desktop activo. En Windows usar `.venv\Scripts\python.exe`, `.venv\Scripts\alembic.exe` y `.venv\Scripts\uvicorn.exe` en lugar de los ejecutables de `.venv/bin`.

```bash
git clone https://github.com/Josuesp34/NODO.git
cd NODO
git checkout v0.4.0-rc.1
cd backend/api
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip==26.2.0
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Editar el `.env` exclusivamente local: contraseña propia, ambas URLs de base consistentes, `ENVIRONMENT=development` y `ALLOW_COACH_REGISTRATION=true` sólo durante la demo. Mantener superusuario deshabilitado. La IA debe permanecer `simulated` y no configurar Resend para esta demo. Nunca compartir este archivo por WhatsApp ni Git.

Usar una **base nueva y un proyecto Compose dedicado**; el puerto indicado debe estar libre y coincidir con `DATABASE_URL`. Una base heredada se respalda y revisa antes: la migración rechaza actividades sin dueño y no asigna atletas por suposición.

```bash
docker compose -p nodo-handover up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Otra terminal, desde `backend/api`, ejecuta `.venv/bin/python -m app.services.jobs`. Desde `frontend`:

```bash
npm ci
cp .env.example apps/nodo-web/.env.local
npm run dev:web
```

Abrir `http://localhost:3000`; API/OpenAPI en `http://127.0.0.1:8000/docs`. Crear coach sintético desde `POST /api/v1/auth/coaches` en OpenAPI con correo `coach-demo@example.com`, nombre Demo Coach, zona `America/Mexico_City` y contraseña local de al menos 12 caracteres. No existe alta pública productiva; no habilitar development en una URL pública.

## 4. Demo y aceptación técnica conjunta (45–60 min)

- [ ] Josué clona la versión etiquetada y levanta una base nueva sin archivos personales de Brandon.
- [ ] Coach entra, invita a `athlete-demo@example.com` y obtiene el código manual sólo en desarrollo.
- [ ] Atleta activa la cuenta en ventana privada; ambos pueden iniciar/cerrar sesión.
- [ ] Coach crea bloque y sesión estructurada, edita borrador y publica; atleta ve sólo la versión publicada en Hoy/Semana.
- [ ] Publicación repetida y edición con versión antigua no duplican ni sobrescriben silenciosamente.
- [ ] Atleta carga FIT sintético; repetir el archivo no crea otra actividad; el worker procesa el trabajo.
- [ ] Atleta registra check-in/molestia; coach la revisa con motivo y decisión.
- [ ] Verificar accesos cruzados denegados y que revocar la asignación corte también acceso de asistentes/recomendaciones.
- [ ] Mostrar explícitamente qué está simulado: Intervals e IA. Correo y push no se presentan como entregados.
- [ ] Registrar fecha, participantes, versión y resultado. Esta sesión todavía no está ejecutada ni aprobada por Josué.

Para generar un FIT sintético fuera del repo, desde `backend/api`:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import gettempdir
import runpy
fixture = runpy.run_path('tests/services/test_fit_parser.py')
target = Path(gettempdir()) / 'nodo-handover-demo.fit'
target.write_bytes(fixture['make_fit']())
print(target)
PY
```

## 5. Plan hasta producción

| Orden | Trabajo por cerrar | Responsable de seguimiento | Evidencia para cerrar |
|---|---|---|---|
| P0 · cerrado | Código completo integrado a `dev` y `main`; versión candidata publicada | Brandon | PRs #7/#8, tag `v0.4.0-rc.1` y CI del commit exacto aprobados |
| P1 | Identificar o crear proyectos staging/prod; definir identidad, billing, región, estado Terraform y costo bruto/neto | Nosotros preparamos/ejecutamos; Josué coordina los datos y permisos faltantes | Inventario de NODO y presupuesto confirmado; no usar recursos de otros proyectos |
| P2 | Provisionar base de plataforma, usuario PostgreSQL, secretos y bootstrap seguro del primer admin | Nosotros, con acceso autorizado | Plan aplicado, migración y login admin sin habilitar registro development |
| P3 | Construir/escaneo de imágenes, configurar WIF/Environments y permisos GitHub; desplegar staging | Nosotros; propietario GitHub habilita lo que exija admin | Digests, permisos entre registros, jobs/worker activos y URL HTTPS |
| P4 | Definir u obtener dominio, DNS, cuenta Resend y remitente; verificar y configurar secretos | Nosotros configuramos/verificamos; Josué coordina propiedad/cuentas/condiciones faltantes | SPF/DKIM/DMARC y recepción real de invitación/recuperación en cuenta autorizada |
| P5 | Obtener app/cuenta OAuth aprobada de Intervals; implementar state/callback/cifrado, webhooks idempotentes, backfill/reconexión/revocación; conservar FIT | Nosotros implementamos/verificamos; Josué coordina propietario y aprobación externa | Importación real consentida, duplicados y revocación comprobados |
| P6 | Definir propuesta de IA/modelo/región/retención/tope, coordinar aprobaciones aplicables e implementar adaptador real y ambos chats | Nosotros implementamos/evaluamos; responsables humanos deciden condiciones aplicables | Proveedor/configuración documentados, evaluaciones sintéticas, citas autorizadas, confirmación y flujos manuales |
| P7 | Completar comparación prescrita/ejecutada, historial de actividades, chat atleta, pantallas administrativas y Web Push | Nosotros | Recorridos pendientes completos y notificación recibida en dispositivo consentido |
| P8 | Validar 70 perfiles × 12 semanas, carga, privacidad, seguridad, renovación concurrente de sesiones, accesibilidad y teléfonos físicos | Nosotros automatizamos/corregimos; Brandon u otro tester autorizado realiza dispositivos; revisión especializada cuando aplique | Corpus versionado, métricas, hallazgos corregidos y validaciones fechadas |
| P9 | Backups/PITR, restauración aislada, rollback, monitoreo, alertas, costos, guardia y soporte | Nosotros preparamos/verificamos; Josué recibe la operación | Restore medido, objetivos RPO/RTO, alertas de API/cola/correo y acceso operativo |
| P10 | Promover exactamente los digests probados, migrar y verificar producción; autorización general ya recibida | Nosotros ejecutamos/verificamos con recursos identificados y acceso autorizado | URL HTTPS, SHA→CI→digest→revisión, E2E coach/atleta y pruebas reales |
| P11 | Coordinar legal/consentimiento/retención, precio/soporte y selección del piloto con responsables de negocio/legal | Josué coordina; responsables humanos aprueban lo aplicable | Checklist `LANZAMIENTO.md` completo; GO para atletas reales |

Los trabajos P4/P5/P6 pueden avanzar en paralelo al staging cuando existan sus datos externos. Las dependencias no se marcan cerradas sólo por configurar variables. IA e Intervals requieren código adicional además de credenciales.

## 6. Datos y recursos por resolver por Josué

No se asume que estos recursos existan ni que Brandon pueda entregar la configuración. Josué coordina con sus propietarios qué existe, quién concede acceso y las decisiones externas. Nosotros preparamos las propuestas/guiones y creamos o configuramos lo posible cuando existan esos permisos y condiciones. Registrar cada punto como `por definir`, `por crear`, `por configurar` o `verificado`, junto con responsable, siguiente acción y evidencia. La asignación de seguimiento no equivale a aceptación de Josué ni a aprobación de costos o términos de terceros.

- [ ] Proyecto(s) GCP de NODO e identidad confirmada; cuenta de facturación/créditos y región.
- [ ] Dominio de NODO y acceso DNS. Una URL `run.app` no verifica correo ni sustituye un dominio aprobado.
- [ ] Cuenta propietaria y aprobación OAuth de Intervals; callback registrado y cuenta de prueba autorizada.
- [ ] Resend con dominio verificado y remitente.
- [ ] Proveedor/modelo IA, ubicación, tratamiento de datos y techo de gasto.
- [ ] Accesos nominales de Josué y procedimiento de soporte.
- [ ] Propietario GitHub: protecciones/revisores, Environments/WIF y Dependency Graph/permisos del review nativo. Las auditorías directas siguen siendo obligatorias.

Secretos por Secret Manager o canal seguro; WhatsApp y Git reciben únicamente enlaces, identificadores no secretos y estado. Las preguntas anteriores quedan convertidas en este checklist para Josué, sin esperar respuestas inmediatas de Brandon. Mantener la autorización general de producción ya recibida; Josué coordina las decisiones puntuales de costo, términos o negocio que requieran aprobación.

## 7. Cierre del handover

**Entrega técnica:** código publicado, CI comprobado, instrucciones vigentes, demo reproducida por Josué y pendientes con responsables acordados. **Entrega operativa:** producción e integraciones reales verificadas, monitoreo/costos/restauración y accesos entregados. Registrar ambos resultados por separado.

La comunicación lista para copiar está en [MENSAJE_WHATSAPP_JOSUE.md](MENSAJE_WHATSAPP_JOSUE.md). Runbooks: [OPERACION_GCP.md](OPERACION_GCP.md), [RUNBOOK_PRODUCCION.md](RUNBOOK_PRODUCCION.md), [RECUPERACION_DESASTRES.md](RECUPERACION_DESASTRES.md), [RESEND_CONFIGURACION.md](RESEND_CONFIGURACION.md) y [LANZAMIENTO.md](LANZAMIENTO.md).

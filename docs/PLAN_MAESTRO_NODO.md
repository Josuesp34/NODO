---
fecha: 2026-09-14
tags: [proyecto, nodo, body-os, arquitectura, ejecucion]
estado: activo
version: 2.0
---

# NODO — Plan maestro hasta aplicación publicada y funcional

**Estado:** 🟡 Activo — especificación de ejecución, no evidencia de implementación.
**Repositorio:** https://github.com/Josuesp34/NODO
**Responsable:** Brandon. **Agente ejecutor solicitado:** GPT-6 Astra.

**Precedencia técnica vigente (20-09-2026).** Este documento conserva el alcance F0–F16 y el
criterio comercial de cierre. Para datos e infraestructura, los ADR 0007 y 0008, posteriores,
sustituyen cualquier referencia anterior a TimescaleDB o a una VM: PostgreSQL 16 particionado,
Cloud SQL y servicios/worker/jobs de Cloud Run. `PLAN_EJECUCION.md` v2 detalla FA/FB; no recorta
los asistentes duales, F14 comercial, F15 plataforma ni F16 lanzamiento de este contrato maestro.

## 🎯 Objetivo y alcance contractual

Entregar NODO publicado en producción y operable de punta a punta: una PWA para entrenador y atleta/persona, cada uno con un LLM intermediario entre sus datos y sus consultas. La entrega exige código integrado, revisión resuelta, despliegue reproducible y verificación funcional sobre la URL pública HTTPS.

Alcance comercial inicial: incorporación asistida, 2–3 entrenadores y 15–30 atletas adultos; pruebas con 70 atletas sintéticos y 12 semanas. Calendario y sesiones para running, ciclismo, natación y triatlón, con cálculos específicos de cada disciplina y sin sumar unidades incompatibles. Cobro administrado registrado en la aplicación; pasarela automática y alta pública masiva quedan fuera de esta versión. Esta delimitación no permite dejar funciones incluidas incompletas.

Una persona puede consultar sus propios datos aunque aún no tenga coach asignado. La planificación publicada por un coach sigue bajo autoridad del coach. No se añade un entrenador médico o prescriptor autónomo para personas sin coach.

## ✅ Tareas y ejecución continua

- [ ] Verificar estado remoto, documentación, instrucciones y línea base.
- [ ] Implementar y verificar todos los contratos F0–F16.
- [ ] Revisar, corregir e integrar los PRs necesarios.
- [ ] Fusionar release a main y desplegar el artefacto correspondiente.
- [ ] Verificar la URL de producción, proveedores reales y recorrido completo.
- [ ] Entregar evidencia, costos y runbooks.

Las fases organizan el trabajo; no son puntos donde finalizar la tarea. Las ramas y PRs son mecanismos internos. El resultado no puede ser “listo en una rama”, “PR abierto” o “listo para desplegar”.

El mandato actual sustituye las antiguas reglas de una fase por sesión, detenerse entre fases y no integrar main: ejecutar todo en una tarea persistente, actualizar esas decisiones en AGENTS.md y ADR, conservando seguridad, permisos y calidad. No reinterpretar firmas humanas como si las hubiera realizado un agente.

Se autorizan subagentes Astra para tareas acotadas e independientes, hasta cuatro agentes activos o el límite disponible. Cada implementador usa un worktree aislado; el raíz coordina contratos, revisa cambios e integra. No crear tareas de usuario separadas. La compactación no reinicia el proyecto: mantener un registro persistente y continuar.

### Inspección y fuentes

Clonar o usar un worktree fuera del vault Second Brain; nunca mezclar sus cambios. Leer completamente AGENTS.md, CONTRIBUTING.md, README, PLAN_PRODUCTO, PLAN_EJECUCION, ARQUITECTURA, API_NODO, ESTADO_TECNICO, PENDIENTES_MVP, PILOT_READINESS, ADR, migraciones, workflows y relevo frontend aplicable. Revisar lo ya implementado antes de reconstruirlo.

Estado histórico, no supuesto vigente: F0 existía en feat/f0-higiene, SHA 98f2a9b5; dev estaba en 08f38131. Verificar ramas, PRs y CI actuales. Reproducir cualquier afirmación contradictoria sobre TimescaleDB.

Este documento es la referencia principal para alcance y aceptación. Incorporarlo al checkout como docs/PLAN_MAESTRO_NODO.md después de leer cualquier archivo existente con ese nombre. Mantener la arquitectura y contratos históricos compatibles salvo las modificaciones explícitas aquí. Documentar decisiones nuevas con ADR y una matriz requisito → implementación → prueba → evidencia.

## 📝 Arquitectura y especificaciones

### 1. Consumo y experiencia

Una PWA responsive en frontend/apps/nodo-web, basada en Next.js y componentes coherentes con el proyecto. NODO Lab es el módulo coach. Usar cuentas multirol, navegación por capacidades, español claro, estados de carga/vacío/error, reintentos y formularios accesibles. Conservar pantallas y flujos manuales aunque falle la IA.

Sesión BFF con cookie httpOnly, Secure y SameSite; protección CSRF y validación de origen en escrituras. Nada de tokens de sesión en localStorage, sessionStorage o HTML. API FastAPI modular: HTTP, dominio, servicios e infraestructura. Autorización servidor en cada petición y herramienta.

PWA instalable; hoy/semana disponibles offline de forma limitada. No cachear respuestas sensibles entre usuarios; limpiar cachés al cerrar sesión o cambiar cuenta. Explicar antigüedad del contenido offline. Safari iOS, Chrome Android y navegadores de escritorio; emulación no equivale a validación en teléfono físico. No requiere tiendas ni HealthKit nativo en esta versión.

### 2. Google Cloud y cuenta autorizada

Usar la identidad **brandonmuro.work@gmail.com** y los créditos elegibles de su cuenta de facturación. Verificar gcloud auth, proyectos, billing, saldo, vencimiento, elegibilidad y permisos antes de crear recursos. Los créditos pertenecen a una cuenta de facturación, no se transfieren simplemente por usar un correo.

Reutilizar un proyecto exclusivamente NODO si está inequívocamente identificado; en otro caso crear uno dedicado si existen permisos y una cuenta de facturación inequívoca. Si hay ambigüedad, pedir la selección concreta sin utilizar proyectos ajenos. No asumir que el proyecto activo de gcloud es el correcto. Nunca afirmar cobertura de créditos no comprobada.

Política: servicio gestionado de GCP adecuado → contenedor portable en Cloud Run → externo sólo cuando sea necesario. Sin VPS externo ni Kubernetes. GitHub e Intervals.icu siguen como dependencias. Preferir Terraform/gcloud/APIs y dejar todo inventariado en Cloud Console; no exigir clics manuales donde exista automatización.

Presupuestos de trabajo propuestos en el encargo: USD 100/mes de infraestructura y USD 30/mes de IA interna; recurso individual de hasta USD 50/mes, sin compromisos anuales. Al ejecutar el prompt que adopta este plan, estos son los límites autorizados de aprovisionamiento. Estimar consumo bruto antes de créditos y consumo neto; no asumir que créditos cubren terceros. Si el diseño no cabe, optimizar y presentar la diferencia antes de aprovisionar fuera de esos límites.

Etiquetas project=nodo, environment y managed-by. Alertas al 25/50/75/90/100 %, retención de logs e imágenes, límites de solicitudes/tokens y cuotas. Los presupuestos no son un corte garantizado: no prometer cero sobrecostos. No apagar producción, deshabilitar billing ni borrar datos automáticamente por una alerta.

### 3. Topología de producción

Inicio: Next.js/BFF y FastAPI como servicios de Cloud Run, worker como Cloud Run worker pool,
migraciones como Cloud Run job, y PostgreSQL 16 gestionado en Cloud SQL sin IP pública. Docker
Compose se conserva para desarrollo y portabilidad, no como topología de producción. Dimensionar
mediante pruebas, con límites de recursos, reinicios supervisados y cuentas de servicio separadas.

Región preferida northamerica-south1, sujeta a disponibilidad, cuotas, costos y requisitos de ubicación. Evaluar us-south1 como alternativa; no afirmar residencia mexicana de todos los datos si Vertex AI, backups o servicios externos operan fuera. Documentar ubicaciones efectivas.

Servicios: Cloud Storage privado para FIT/exportaciones/backups; Secret Manager; Artifact Registry; Logging/Monitoring con uptime checks; snapshots; Cloud DNS si se dispone del dominio; Cloud Build o GitHub Actions con federación de identidad, sin claves JSON persistentes cuando exista alternativa. Cloud Scheduler sólo donde haga falta. Cola de producto en PostgreSQL; no duplicarla con Pub/Sub o Redis sin necesidad comprobada.

TLS gestionado en el borde de Google Cloud y dominio autorizado. Separar staging y producción en
proyectos distintos, con secretos, bases, buckets, identidades y accesos propios; staging escala a
cero y no recibe datos reales. Nunca exponer un modo development como producción.

Series temporales: PostgreSQL 16 particionado por rango, BRIN y `pg_partman`, conforme al ADR 0007.
No introducir TimescaleDB de nuevo sin una ADR nueva y evidencia de costo/rendimiento. Las migraciones
se prueban contra PostgreSQL real con upgrade, `alembic check` y recorrido de downgrade seguro.

Terraform con estado remoto privado, control de concurrencia, permisos acotados y sin secretos en el repositorio. No guardar claves en outputs públicos. IAM de mínimo privilegio y recursos sólo de NODO; no autoelevarse ni eludir MFA o políticas de organización.

Backups automáticos de Cloud SQL con recuperación a un punto en el tiempo, retención coherente con
privacidad y restauración probada en destino aislado. Objetivos iniciales propuestos: RPO ≤24 h y
RTO ≤4 h; medirlos y documentar resultados, no confundir configuración con restauración verificada.
Alertas de fallos de backup, cola atascada, almacenamiento, API y proveedor.

### 4. Identidad y modelo de datos

Entidades mínimas o equivalentes existentes:

- users, user_roles, organizations, organization_memberships, coach_athlete_assignments, auth_sessions, athlete_invitations.
- athlete_profiles con deportes, zona horaria, objetivos, disponibilidad, parámetros, fuente y vigencia.
- training_blocks, prescribed_workouts con pasos/versiones, competitions, groups, group_memberships, plan_templates, plan_assignments y excepciones.
- activities con dueño obligatorio, proveedor, ID externo y hash; activity_sessions, activity_laps, telemetry_records.
- observations con atleta, métrica, valor, unidad, método, proveedor, dispositivo, periodo observado, zona horaria, recepción, ID externo y calidad.
- checkins, complaints, complaint_updates, review_items.
- daily_load con unidad, fórmula, parámetros y versión; no sumar TRIMP y TSS como si fueran equivalentes.
- recommendations, decisions, athlete_connections, ingestion_events, jobs, consents, audit_log.
- assistant_threads/messages/runs/tool_calls/citations/feedback; planes comerciales, suscripciones administradas, cupos y pagos registrados.

IDs de terceros: comprobar su ámbito real y definir unicidad con proveedor/conexión/atleta cuando corresponda; no asumir IDs globales. Transacciones, restricciones y pruebas deben impedir acceso cruzado y duplicación. Todas las migraciones mediante Alembic; preservar datos existentes.

### 5. Intervals.icu y FIT

Intervals.icu es la fuente automática principal, FIT manual es respaldo permanente. Verificar API y documentación oficial actual antes de codificar scopes, eventos, campos y ciclo de tokens. No inventar refresh tokens o expiración: implementar renovación sólo si el proveedor la soporta; en otro caso reconexión y revocación según contrato real, actualizando el ADR previo.

OAuth con state seguro ligado a sesión, scopes mínimos, callback validado, tokens cifrados por entorno, revocación y borrado según consentimiento. Webhooks autenticados conforme al mecanismo real del proveedor; acuse rápido, evento persistido y trabajo en cola. Backfill configurable de 90 días, límites de tasa, reintentos con backoff y manejo de 401/403/429/5xx.

Importar actividades, laps y wellness disponibles: HRV con método, sueño y pulso cuando existan. No prometer cobertura de todas las marcas o métricas. Un FIT de entrenamiento no demuestra datos diarios. Conectar relojes directamente a Intervals cuando sea posible; mantener procedencia y excluir usos no permitidos de datos originados en Strava. device_name no sustituye la trazabilidad del origen ni una autorización de uso.

UI atleta: conectar, estado, última sincronización, errores y desconectar. UI coach: estado de atletas autorizados. Escritura al calendario externo detrás de bandera apagada por defecto y acción explícita; NODO es fuente de verdad del plan.

FIT autenticado, validación de tamaño/contenido/tiempos, dueño y permisos. Límite en proxy antes del parser, procesamiento acotado y rechazo claro de formatos no soportados. Tres importaciones iguales producen una actividad. Worker con lease/reclamación tras caída y SKIP LOCKED; atomicidad, idempotencia y bandeja de fallos. Actividades tardías recalculan desde el día afectado con fórmula/versiones.

### 6. LLM para entrenador y persona

Dos experiencias sobre herramientas de servidor, sin SQL libre ni acceso directo del LLM a la base. Motor común con política por rol; consultas siempre autorizadas en servidor, incluso al recuperar historial y citas.

**Coach Copilot:** consultar atletas asignados y grupos, planes, cumplimiento, carga, wellness, molestias y revisión. Resumir semana, identificar ausencia de sincronización y crear borradores de sesiones/bloques/ajustes. Mostrar evidencia, fechas, fuente, calidad, datos faltantes, versión y diff. Coach revisa y publica mediante acción explícita. No publicar, ajustar, cerrar molestias ni enviar mensajes automáticamente.

**Asistente personal/atleta — Habla con tus datos:** consultar sólo datos propios, con o sin coach asignado. Explicar hoy/semana, sesiones publicadas, actividades y tendencias calculadas; comparar plan/ejecución; señalar datos faltantes. Guiar check-ins, preparar reporte de molestia o pregunta al coach. No modificar planes, autorizar entrenamiento, diagnosticar ni mostrar notas privadas del coach. Sin coach puede explicar datos y registrar sensaciones, sin inventar prescripción profesional.

Ejemplos obligatorios: “¿Quién requiere revisión hoy y por qué?”, “Prepara seis semanas para 10K sin martes”, “¿Qué tengo hoy?”, “¿Cumplí mis intervalos?”, “¿Cómo cambió mi carga?”, “Tengo una molestia y quiero reportarla”.

Escrituras conversacionales: borrador estructurado → previsualización → confirmación del usuario autorizado → operación transaccional → lectura posterior del resultado → auditoría. Vincular confirmación a usuario, contenido, versión y caducidad; doble envío no duplica. El límite de autonomía del agente que programa no elimina confirmaciones dentro del producto.

Visibilidad: datos compartidos del entrenamiento separados de notas privadas y chats. Los chats personales no se comparten íntegros por defecto; sólo compartir reportes/preguntas confirmados. Revocar asignación corta herramientas, acceso futuro a conversaciones derivadas y citas; no se puede borrar de la memoria humana lo ya visto. Cachear y recuperar contexto con permisos revalidados.

Herramientas tipadas de lectura: perfil, calendario, actividad, comparación, observaciones, resumen semanal, sincronización, check-ins, molestias, bandeja, grupos y calidad. Herramientas de borrador y confirmación separadas. Identidad y ámbito nunca determinados sólo por un athlete_id propuesto por el LLM.

Conversaciones: propietario, rol, ámbito, timestamps, mensajes, herramientas, evidencias, proveedor/modelo, versión del prompt, costo, estado y retención. Contexto mínimo por consulta; cifras desde funciones deterministas. Citas abren datos autorizados con fecha, fuente, método y calidad. Datos insuficientes deben reconocerse; no inventar una respuesta fisiológica.

Puerto de IA: simulador para tests y Vertex AI como primera implementación real GCP-first. Elegir modelo disponible mediante evaluaciones de calidad/costo/latencia; verificar condiciones y cobertura de créditos. OpenAI sólo como alternativa justificada y con credencial/presupuesto apropiados; Astra constructor no obliga a usar Astra en producto. Streaming, cancelación, salida estructurada, límites por usuario/organización, timeout, reintentos acotados, circuit breaker y costo agregado de ambos asistentes.

Textos de usuarios, FIT, notas y proveedores son datos no confiables. No pueden alterar permisos o política. No entrenar modelos con datos de atletas por defecto. Revisar retención del proveedor y minimizar información enviada. El calendario, formularios y revisión manual funcionan cuando la IA cae o alcanza cuota.

### 7. Reglas de dominio y producto

No diagnóstico, prevención garantizada de lesiones, retorno deportivo autorizado por IA ni rendimiento exacto. Nunca “100 % descansado”. Estados de revisión: datos insuficientes; sin señales destacadas en los datos disponibles; requiere revisión. Reglas versionadas y explicables, sin inventar umbrales médicos universales.

Una molestia nueva o creciente prevalece en revisión aunque el reloj parezca favorable. Flujo reportada → revisada → decisión → seguimiento → cierre, con reapertura e historial. Ausencia de check-in no es cero. Cambiar perfil o dispositivo no reescribe silenciosamente históricos o referencias.

Calendario con bloques libres, competencias, pasos de calentamiento/trabajo/recuperación/vuelta a calma, repeticiones, tiempo/distancia y objetivos tipados. Conflictos expected_version responden 409 sin sobrescribir. Propuestas obsoletas no se aplican. Grupos conservan excepciones y previsualizan afectados.

### 8. Fases y aceptación verificable

| Fase | Implementación obligatoria | Aceptación mínima |
|---|---|---|
| F0 Fundación | Revisar rama existente; higiene, contratos, ADR, Docker y CI | Base limpia migra; alembic check; /health; backend/frontend/lint verdes |
| F1 Identidad | Multirol, organizaciones, asignaciones, invitaciones, capacidades y migración | Cuenta dual; acceso cruzado denegado; revocación; relaciones anteriores preservadas |
| F2 PWA/BFF | App única, sesión segura, rutas por capacidades, manifest/offline | Login/refresh/logout/expiración E2E; tokens no accesibles; caché aislada; responsive |
| F3 Perfil | Disciplinas, parámetros, objetivos, disponibilidad, fuente y vigencia | Cálculos con perfil a fecha de actividad; insuficiencia explícita; históricos preservados |
| F4 Calendario | Bloques, competencias, editor, pasos, publicación y versiones | Coach publica; atleta ve; dos ediciones producen conflicto claro sin pérdida |
| F5 Ingesta | FIT autenticado, observabilidad de eventos, cola y worker persistente | Archivo triplicado genera una actividad; caída/reinicio recupera; recálculo histórico |
| F6 Intervals | Contrato OAuth real, webhooks, backfill, revocación, UI de conexión | Tests contractuales más conexión/importación real consentida; duplicados y errores probados |
| F7 Comparación | Observaciones, días locales, cobertura y vinculación ajustable | Laps/intervalos comparables; no sincronizada ≠ incumplida; sueño y datos tardíos correctos |
| F8 Molestias | Check-ins, reportes, evolución, revisión, decisiones y bandeja | Persona sin reloj reporta; empeoramiento reabre; ninguna señal favorable lo oculta |
| F9 LLM dual | Ambos chats, herramientas, contexto, citas, confirmaciones, proveedor y evaluaciones | Coach y persona completan consultas con datos persistidos; proveedor real; aislamiento y escrituras seguras |
| F10 Ajustes | Evidencia, diff, aprobación/modificación/rechazo y versiones | 409 en propuesta obsoleta; diff aprobado aplicado exactamente una vez y auditado |
| F11 Escala | Grupos, plantillas, excepciones, paginación y consultas eficientes | 70 atletas/12 semanas; excepciones intactas; medir p95 calendario <1.5 s y listado <1 s bajo carga definida |
| F12 Operación | Consentimiento, exportación/borrado, retención, recuperación, seguridad, auditoría | PILOT_READINESS con evidencias; privacidad funcional; acceso y errores seguros |
| F13 Notificaciones | Web Push, preferencias y escenarios precompetencia | Push real a dispositivo consentido; revocación respetada; escenarios con supuestos visibles |
| F14 Comercial | Planes/cupos, suscripción y cobro administrados, admin, suspensión y soporte | Administrador activa y registra pago; cupos se aplican; costos IA/atleta/coach visibles; sin pago ficticio |
| F15 GCP | Terraform, IAM, Cloud Run/Cloud SQL, almacenamiento, secretos, CI/CD, backups y monitoreo | Staging/producción aislados; restauración ejecutada; rollback y costo medidos; artefacto trazable |
| F16 Lanzamiento | Onboarding, ayuda, accesibilidad, analítica, documentos legales, dominio/correo y release | URL HTTPS funcional, pruebas E2E desplegadas, integraciones reales y entrega de operación |

F15 se inicia con el preflight y la infraestructura mínima, no se aplaza hasta después de integrar proveedores. F12 usa las pruebas de backups/deploy de F15; evitar una dependencia circular. F2/F3 pueden avanzar tras F1; F4 necesita ambos; F5 necesita F1/F3; F6 después de F5; F7 con F5 y contrato F6; F8 con F4/F7; base conversacional F9 desde F1/F4, completar herramientas según F7/F8/F11; F10 con F7/F9; F11 con F4. F13/F14 pueden avanzar cuando existan sus contratos; F16 reúne todas las evidencias.

### 9. Evaluaciones y QA

Pruebas unitarias/contrato/integración y E2E relevantes; no repetir suites sin cambios. Migraciones sobre base nueva y upgrade desde estado anterior, downgrade donde sea seguro. Ruff, pre-commit, typecheck y builds con comandos reales del proyecto. No exigir número fijo de tests heredado.

Evaluaciones de ambos LLM: consultas normales, sin coach, permisos cruzados, revocación, notas privadas, prompt injection, evidencia inexistente, métodos incompatibles, datos viejos/incompletos, molestia creciente, diagnóstico/retorno deportivo, publicación automática, salida inválida, proveedor caído, cuota agotada y doble confirmación. Cero accesos cruzados y cero escrituras no autorizadas en la suite. Evaluar proveedor real acotadamente con datos sintéticos antes de datos consentidos.

Pruebas de producción: DNS/TLS, cookies, API y worker, migraciones, uploads privados, 401/403/409, no exposición de secretos/puertos, protección de administración, solicitudes de invitación/recuperación sin tokens en respuesta, correo a destinatario de prueba autorizado y eliminación/exportación verificables. Analítica sin conversaciones o salud crudas. Accesibilidad de teclado, foco, etiquetas y contraste; inspección visual móvil/escritorio.

Correo: reutilizar infraestructura existente autorizada; externo por API/SMTP si hace falta. No crear un servidor SMTP improvisado sólo para afirmar cobertura GCP. SPF/DKIM/DMARC y remitente del dominio cuando se disponga de él. Dominio/condiciones/precio no se inventan. Privacidad y términos preparados para revisión y publicados sólo tras aprobación de datos/condiciones reales.

### 10. Revisión, aprobación, integración y publicación

Usar ramas temporales y PRs de alcance revisable (por fase o corte coherente), no dividir la entrega en tareas que terminan con cada rama. Preservar ramas existentes; actualizar desde dev antes de integrar. Para paralelismo, resolver dependencias y migraciones antes de fusionar.

Autorización del encargo: crear ramas, commits, push, PRs, corregir CI/comentarios, integrar a dev, crear release PR a main, fusionarlo y publicar producción dentro de cuentas/recursos/límites autorizados. Sin push directo a main cuando el proyecto usa PRs.

Revisión por subagente distinto del autor cuando esté disponible; registrar hallazgos, corregir y ejecutar verificaciones. Esto no equivale a una aprobación humana de GitHub. Usar aprobaciones válidas disponibles; no suplantar revisores, cambiar de identidad para autoaprobar, quitar protecciones ni eludir una revisión obligatoria. Si la plataforma exige aprobación externa, preparar el PR y solicitar sólo esa acción.

Cada PR: comportamiento final, migraciones, validación, evidencia, riesgos y rollback. Esperar CI del SHA actual; cambios posteriores invalidan la evidencia afectada. El release debe identificar main SHA → CI → digest de imagen → despliegue → URL HTTPS → smoke/E2E. No desplegar una carpeta modificada manualmente como sustituto del artefacto revisado.

Promover artefactos probados desde staging a producción. Migraciones compatibles expand/contract cuando haga falta; backup verificado antes de cambios con riesgo. Rollback de aplicación no implica que todo downgrade de base sea seguro. Publicar primero con acceso restringido y cuentas sintéticas; abrir a atletas reales sólo tras readiness y consentimiento. No reclutar, cobrar tarjetas, invitar o contactar personas reales automáticamente.

### 11. Bloqueos y autorizaciones externas

Preflight temprano de OAuth aprobado, billing/créditos, permisos, dominio/DNS, correo, Vertex AI y región, revisores y validación de dispositivos. No esperar al final para descubrirlos. Pedir en conjunto los datos externos realmente faltantes mientras continúa trabajo independiente. Intentar un checkpoint consolidado; una nueva restricción material puede requerir otro, no se garantiza una sola pausa ni un tiempo fijo de ejecución.

Completar adaptadores, simuladores, IaC y staging donde sea posible sin credenciales. Mantener los estados de pruebas reales pendientes, no marcarlos completados. Secretos por Secret Manager o canal seguro, nunca por chat/Git/logs. Identidad no autenticada, billing ambiguo, aprobación del proveedor, MFA, dominio o revisiones protegidas no se sortean por autorización genérica.

No borrar recursos existentes, discos ni backups por tener etiqueta NODO. Limpieza limitada a temporales creados en esta ejecución y confirmados prescindibles; retención acordada para datos persistentes. No usar credenciales/datos de otros proyectos o la cuenta Google equivocada.

### 12. Evidencia, continuidad y criterio de cierre

Mantener docs/ESTADO_TECNICO.md con fase, requisito, dueño, rama, PR, SHA, pruebas, CI, entorno, evidencia, costo y siguiente acción. Añadir OPERACION_GCP, RUNBOOK_PRODUCCION, RECUPERACION_DESASTRES, COSTOS, SEGURIDAD, LLM_COACH, LLM_ATLETA, EVALUACIONES_LLM y LANZAMIENTO o consolidaciones equivalentes. Evidencia sensible fuera de Git en almacenamiento privado.

**COMPLETO** exige todos los requisitos implementados y verificados; PRs revisados e integrados; release en main; aplicación publicada HTTPS; ambos LLM funcionando con proveedor real y datos autorizados; Intervals importando realmente; FIT, calendario, molestias y grupos operativos; correo y notificaciones comprobados; backups restaurados; monitoreo/costos y acceso operativo entregados. Pruebas físicas y aprobación legal pendientes no se sustituyen por emulación o documentos borrador.

Si una dependencia externa esencial falta, declarar **PARCIAL — BLOQUEO EXTERNO**, precisar lo probado y seguir con todo trabajo independiente. Ni un PR listo para aprobar, ni integración simulada, ni “lista para publicar” satisfacen el cierre final. Un producto publicado sin Intervals o sin IA reales tampoco satisface este contrato.

Entrega final: URL, recorrido coach y persona, SHA release, PRs y aprobaciones válidas, CI/digest/deploy, inventario GCP y ubicación, saldo/vencimiento de créditos verificables, costo bruto/neto estimado, pruebas funcionales, integraciones reales, restauración/RPO/RTO, alertas, rollback, alcance comercial y cualquier riesgo residual. Acceso administrativo por mecanismo seguro, nunca contraseñas en el informe.

## 📎 Recursos y referencias

- Repositorio: https://github.com/Josuesp34/NODO
- Antecedente de fases: [[Claude outputs/PLAN_EJECUCION]]; sustituir sus pausas por sesión y ampliar F9 conforme a este plan.
- API Intervals: https://www.intervals.icu/features/open-api/
- OAuth Intervals: https://forum.intervals.icu/t/intervals-icu-oauth-support/2759
- GCP regiones: https://docs.cloud.google.com/compute/docs/regions-zones
- GCP extensiones: https://docs.cloud.google.com/sql/docs/postgres/extensions
- GCP presupuestos: https://docs.cloud.google.com/billing/docs/how-to/budgets
- GCP backups: https://docs.cloud.google.com/compute/docs/disks/data-protection

Consultar documentación oficial vigente al implementar; las URLs son referencias de verificación, no prueba de cobertura, disponibilidad, costo o acceso actual.

## 🔗 Notas relacionadas

- [[🧬 Body OS — Índice]]
- [[🏋️ B2B Entrenadores — Índice]]
- [[B05 Capa LLM Coach y Alumno]]

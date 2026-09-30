# Plan de cierre antes del handover con Josué

Fecha: 30 de septiembre de 2026.
Estado: plan de trabajo; las tareas nuevas no se presentan como implementadas.

## Objetivo y reparto

Entregar a Josué NODO con el desarrollo, las pruebas, la instalación y la operación técnica resueltos. Nuestro equipo —Brandon con el asistente de desarrollo— asume la construcción y automatización. Josué coordina únicamente los accesos, cuentas o decisiones humanas que falten y recibe la operación mediante una demo.

La autorización de integración y producción ya existe. No se vuelve a pedir. Los datos que Brandon desconoce siguen registrados como pendientes externos por resolver; no se espera que Brandon tenga sus respuestas. Si una cuenta o recurso no existe, se prepara su creación y se ejecuta por nuestra parte cuando estén identificados propietario, permisos y condiciones aplicables.

Este plan actualiza el reparto de [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md). Conserva el alcance F0–F16 de [PLAN_MAESTRO_NODO.md](PLAN_MAESTRO_NODO.md), la PWA única, GCP, Intervals.icu principal y FIT permanente. La recepción de Josué aún no está registrada.

## Base comprobada y huecos encontrados

Base remota revisada: `main` en `2a5c1fcd4c278a540a55f5065130b5c7113677b4`. Código candidato `v0.4.0-rc.1`, integrado por #7/#8; documentación posterior por #9/#10. Los cambios desde el tag son de documentación. La evidencia de la versión mantiene 59 pruebas backend, 34 PWA, migraciones, builds y auditorías CI. No hay URL de producción ni proveedores reales comprobados.

La lectura del repositorio identifica trabajo que podemos asumir:

| Hallazgo | Evidencia actual | Trabajo necesario |
|---|---|---|
| Historial disponible sólo en API | `activity_routes.py`: listado de hasta 250 actividades con vínculo a sesión | Pantalla, navegación, detalle autorizado y paginación según volumen |
| Comparación todavía incompleta | Existe `prescribed_workout_id` y carga diaria, sin recorrido completo de vinculación/comparación | Contrato, cálculos deterministas, corrección de vínculo y UI |
| Copiloto coach usa una simulación de pantalla | `CopilotWorkspace` construye ejemplos localmente | Consumir conversaciones persistidas, evidencias y confirmaciones del servidor |
| Chat atleta ausente | API de asistentes con rol atleta; no hay pantalla de chat | Pantalla propia, datos autorizados y flujos para persona sin coach |
| IA real no implementada | `send_message` rechaza modo real con 501; contexto limitado a calendario/bandeja | Adaptador, herramientas del alcance, evaluaciones, límites y medición |
| Intervals no sincroniza | `SimulatedIntervalsAdapter` no intercambia tokens y devuelve backfill vacío | OAuth, ingesta, webhooks, backfill, reconexión y revocación remota |
| Push sólo tiene un aviso de pendiente | `NotificationSettings` describe contratos futuros | Preferencias, suscripciones, worker, revocación y recepción real |
| Validación de navegador incompleta | Pruebas PWA actuales verifican contratos; CI no ejecuta un recorrido con navegador/API/worker juntos | E2E con PostgreSQL y datos sintéticos |
| Operación preparada, sin activar | Terraform, workflows y runbooks existentes; worker deshabilitado por defecto | Configuración comprobada, worker activo, alertas y despliegue con evidencia |
| Smoke limitado | `smoke-production.sh` comprueba `/` y `/health` | Añadir recorrido autenticado, cola, migración e integraciones |
| Documentos con estados históricos | Matriz conserva cifras/estados previos a la entrega | Actualizar trazabilidad sin borrar la historia ni rehacer funciones existentes |

Estos hallazgos son una revisión de alcance y código. No equivalen a un pentest ni a una certificación de rendimiento. Privacidad, cálculos, permisos y concurrencia existentes requieren pruebas de integración antes de cerrar su operación real.

## Paquetes que asumimos

Todos empiezan pendientes de ejecución, salvo la publicación de la base ya realizada. Cada paquete termina con su PR integrado, documentación y evidencia correspondiente; las comprobaciones externas conservan su estado pendiente hasta ejecutarse.

| Paquete | Trabajo de nuestro lado | Puede avanzar sin cuentas externas | Evidencia de cierre |
|---|---|---|---|
| B0 · Baseline y dependencias | Conciliar matriz/estado/API; preparar ficha única de accesos, costos y proveedores | Sí | Inventario vigente y cada faltante con dueño/siguiente acción |
| B1 · Demo reproducible | Arranque aislado, cuentas sintéticas, base nueva, migraciones, worker y FIT de prueba | Sí | Clon limpio levanta y reproduce coach → atleta sin archivos personales |
| B2 · Datos y comparación | Historial/detalle, vínculo ajustable, comparación por disciplina, días locales y calidad | Sí | Contratos, UI y pruebas con datos tardíos, ausentes y unidades incompatibles |
| B3 · Flujos manuales | Completar perfiles/competencias, edición, molestias, grupos/plantillas, propuestas y administración | Sí | Recorridos persistidos, auditados y sin ingresar IDs técnicos a mano |
| B4 · Chats del producto | Coach/atleta contra API; historial, herramientas, citas y confirmaciones | Sí, con simulador explícito | E2E de ambos roles, sin coach, revocación y doble envío |
| B5 · Proveedores reales | Conector Intervals y adaptador IA GCP-first configurables; pruebas de contrato | Código y pruebas de contrato sí; validación real no | Integración real consentida y evaluaciones del proveedor aprobado |
| B6 · Notificaciones | Backend, migración, preferencias, suscripción, envíos en cola y UI | Código y transporte de prueba sí | Recepción HTTPS en dispositivo consentido y revocación efectiva |
| B7 · Privacidad y comercial | Retención, borrado/exportación, consentimiento, cupos/suspensión y administración | Código y pruebas sí | Ciclo completo en PostgreSQL; documentos/decisiones humanos aparte |
| B8 · Calidad a escala | Corpus de 70 perfiles × 12 semanas, E2E, carga, accesibilidad y revisión de seguridad | Sí | Artefactos sintéticos, métricas, hallazgos corregidos y CI |
| B9 · Plataforma y automatización | Preflight, bootstrap GCP/IAM/WIF, secretos, CI/CD, costos, alertas y recuperación | Preparación sí; ejecución requiere acceso | Staging aislado, imágenes por digest, worker/cola y restore medido |
| B10 · Activación y producción | DNS/correo/proveedores, staging, promoción, smoke/E2E, backup/rollback | Requiere recursos y cuentas | SHA→CI→digest→revisión→HTTPS, proveedores y monitoreo reales |
| B11 · Entrega operativa | Guía breve, demo, inventario, evidencia, soporte y procedimiento de actualización | Documentación sí | Josué recibe accesos seguros, reproduce el recorrido y registra recepción |

### B0–B1: quitar la preparación manual del relevo

- [ ] Corregir estados antiguos en la matriz y señalar qué requisito ya tiene código/pruebas, qué falta construir y qué espera validación externa.
- [ ] Crear un arranque de demo con un comando o una secuencia corta comprobada para API/PWA/PostgreSQL/worker. Usar puertos locales, proyecto Compose dedicado y base sintética; no tocar volúmenes heredados.
- [ ] Preparar cuentas coach, atleta, persona sin coach y cuenta multirol con datos ficticios, más un FIT reproducible. Secretos de demo fuera de Git y sin reutilización productiva.
- [ ] Automatizar comprobación de migraciones, salud, publicación, FIT y recuperación del worker; dejar instrucciones Mac/Windows y parada segura.
- [ ] Preparar una ficha consolidada de accesos. Iniciar en paralelo la coordinación de OAuth/dominio/permisos, porque sus tiempos dependen de terceros.

### B2–B3: completar el producto manual antes de depender de IA

- [ ] Historial y detalle de actividades para atleta y coach autorizado; vacíos, errores, origen/calidad y paginación, evitando truncamientos silenciosos.
- [ ] Vincular/desvincular actividad y sesión con autorización, auditoría y resolución de ambigüedad. Comparar tiempos/distancias/laps únicamente cuando existan datos compatibles.
- [ ] Revisar carga diaria, descansos, días locales, backfill, datos tardíos y parámetros fisiológicos con fuente/vigencia. Mostrar datos insuficientes; no convertir falta de sincronización en incumplimiento.
- [ ] Completar capturas de perfil/disciplina/disponibilidad/competencias, excepciones de grupos y edición de plantillas. Conservar `expected_version`, publicación y versiones.
- [ ] Mostrar evolución de molestias, decisión, seguimiento y reapertura; conservar su visibilidad aunque existan otros indicadores favorables.
- [ ] Revisar propuestas con evidencia y diff: aprobación/modificación/rechazo, conflicto obsoleto, aplicación exactamente una vez y lectura posterior.
- [ ] Administración con selección de organizaciones, planes y suscripciones mediante lecturas autorizadas. Mantener cobro administrado sin añadir pasarela, precio ficticio ni pagos reales automáticos.

### B4–B5: terminar la integración, no entregar únicamente variables vacías

- [ ] Sustituir ejemplos locales del coach por conversaciones persistidas y crear el chat atleta. Mantener sesiones BFF y citas que abran fuentes autorizadas.
- [ ] Implementar herramientas de lectura tipadas para perfil, calendario, actividades, comparación, observaciones, resumen, molestias, revisión, grupos y calidad. Revalidar permisos en cada uso.
- [ ] Mantener borrador → preview → confirmación → transacción → lectura → auditoría. El LLM no publica planes ni calcula métricas por su cuenta.
- [ ] Preparar el adaptador real GCP-first previsto en el plan maestro, con autenticación adecuada, modelo/región configurables, salida validada, streaming/cancelación, timeout, reintentos acotados y alternativa manual.
- [ ] Implementar medición y límites agregados de uso/costo de ambos chats por usuario/organización. Selección efectiva de modelo, ubicación, retención y gasto requiere evaluación y decisión documentada.
- [ ] Implementar Intervals: inicio OAuth, `state` de un uso vinculado a sesión, callback, scopes mínimos de lectura, tokens cifrados, ingesta idempotente, webhook validado, backfill de 90 días y estado de sincronización.
- [ ] Respetar revocación remota, eliminación y reconexión tras token inválido; FIT permanece disponible. No inventar refresh tokens ni activar escritura al calendario externo.
- [ ] Usar proveedores de prueba HTTP controlados para errores, payloads duplicados/inválidos, denegación, caídas y cuotas. Registrar por separado la verificación del proveedor real.

El contrato oficial de [Intervals OAuth](https://forum.intervals.icu/t/intervals-icu-oauth-support/2759) requiere una app de un propietario identificado y aprobada antes de ejecutar OAuth. Podemos preparar el conector mientras se tramita esa aprobación. Para la implementación GCP, la [guía oficial de autenticación](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start) recomienda ADC y exige proyecto, facturación y permisos; sustituir el requisito actual de una API key genérica cuando no corresponda al proveedor elegido.

### B6–B8: notificaciones, privacidad y evidencia integrada

- [ ] Preferencias persistidas, alta/baja de suscripciones Push, claves guardadas de forma segura, worker, deduplicación y baja de endpoints expirados.
- [ ] Avisos del alcance con datos mínimos, horarios/zona del usuario y estados claros cuando no hay permiso o compatibilidad. No mostrar información sensible del atleta en la pantalla bloqueada por defecto.
- [ ] Revisar consentimiento por finalidad, restricción tras revocación, exportación, desidentificación, dependencias/FK y limpieza de archivos, chats, outbox, cachés e integraciones en PostgreSQL real.
- [ ] Implementar y medir retención efectiva; el número configurado en `.env` no acredita que se eliminen datos. Preparar hechos de tratamiento para revisión legal, sin certificar el aviso definitivo.
- [ ] Probar caché offline por cuenta, cambio de usuario, logout, sesión expirada y renovación concurrente. Revisar que respuestas sensibles no lleguen a caches compartidos.
- [ ] Generar 70 perfiles sintéticos de las disciplinas del alcance y 12 semanas, con descansos, faltantes, datos tardíos, duplicados, multirol, revocación y molestias. Fixtures versionados sin datos reales.
- [ ] Ejecutar navegador real automatizado con API/PWA/PostgreSQL/worker juntos: invitación/activación, publicación, carga, comparación, molestias, propuestas, chats, cuenta y administración. Emulación no sustituye teléfonos físicos.
- [ ] Medir consultas/paginación/carga con hardware y concurrencia documentados; contrastar objetivos del plan (p95 calendario <1.5 s y listado <1 s). Revisar migraciones, reinicios/reintentos y acceso entre organizaciones.
- [ ] Evaluar ambos asistentes: instrucciones maliciosas, citas inexistentes, notas privadas, datos incompatibles, proveedor caído, cuota y confirmación duplicada. Cero accesos cruzados/escrituras sin autorización en la suite.
- [ ] Revisar teclado/foco/etiquetas/contraste y preparar guion iOS/Android. Coordinar revisión especializada cuando corresponda; no atribuirle un pentest humano al agente.

### B9–B10: realizar nosotros el trabajo de plataforma cuando haya acceso

- [ ] Preparar configuración validada por entorno, mapa de secretos, permisos mínimos, regiones/cuotas y formulario de inventario/costos. No asumir que ya existen proyectos, dominio o créditos elegibles.
- [ ] Automatizar creación/configuración GCP permitida, Terraform con estado remoto, WIF y Environments. Los ajustes GitHub que requieren propietario/admin se dejan en un cambio o guion concreto para esa persona.
- [ ] Validar costo bruto/neto y servicios activos antes de aplicar. Los importes del plan maestro son límites de trabajo, no saldo ni cobertura comprobados; budgets no garantizan un corte de gasto.
- [ ] Habilitar realmente worker, migration job y secretos. Comprobar que los mensajes avanzan y los reintentos/leases funcionan, no sólo que `/health` responde.
- [ ] Completar alertas de API, base, backup, jobs atascados/dead, correo/proveedor y costo; destinos y guardia operativa confirmados.
- [ ] Preparar registros DNS y configurar dominio/Resend mediante permisos delegados. Verificar SPF/DKIM/DMARC, invitación y recuperación a cuenta de prueba consentida, errores/bounces y retención del outbox.
- [ ] Ejecutar backup/PITR, restauración a destino aislado y rollback de aplicación; medir RPO/RTO frente a los objetivos del plan. No borrar originales ni confundir rollback de código con downgrade seguro.
- [ ] Desplegar staging restringido con cuentas sintéticas, integrar proveedores reales y repetir los recorridos afectados. Promover los mismos digests escaneados a producción y registrar revisión/URLs.
- [ ] Verificar cookies HTTPS, API privada, permisos, cola, correo, datos privados y recorrido completo. Abrir atletas reales sólo con `LANZAMIENTO.md` y consentimiento completos.

La [API oficial de Resend](https://resend.com/docs/api-reference/introduction) exige credencial y transporte HTTPS. La adaptación en código puede probarse sin enviar mensajes; la entrega real requiere cuenta/dominio y destinatario de prueba autorizado. Nuestro trabajo es configurar y comprobar esa operación cuando existan esos accesos.

### B11: entregar una operación que Josué pueda usar

- [ ] Una página de arranque/operación con enlaces a runbooks, incidencias habituales, respaldo/restauración, límites y escalamiento.
- [ ] Inventario de proyectos/servicios/cuentas nominales y mapa de Secret Manager; ninguna contraseña o token en WhatsApp/Git.
- [ ] Versión, SHA, PRs, checks, digests, revisión desplegada y evidencias fechadas; distinguir sintético, proveedor real, staging, producción y dispositivo físico.
- [ ] Guion de demo breve y guía/capturas del recorrido, generadas con cuentas sintéticas; reproducir antes de la sesión.
- [ ] Josué recibe acceso y valida el recorrido y la operación. Registrar recepción, dudas y pendientes con fecha; no inventar su aceptación.

## Orden de ejecución y dependencias

1. **Preparación:** B0 y B1. Tramitar la ficha externa en paralelo; no esperar sus respuestas para construir.
2. **Producto base:** B2 y B3. Integrar cortes por contrato; B8 empieza aquí con el arnés E2E y datos sintéticos.
3. **Asistentes y servicios:** B4, B5, B6 y B7 según sus dependencias. B5 necesita las herramientas de B2/B3 para completar ambos asistentes. B8 sigue verificando cada corte.
4. **Plataforma temprana:** preparar B9 desde B0; ejecutar staging tan pronto haya permisos, configuración y artefactos revisados. No aplazar el descubrimiento de costos/cuotas/worker al final.
5. **Cierre real:** B10 tras producto e integraciones probados en staging; B11 consolida la entrega. Proveedor no autorizado o validación física/legal pendiente mantiene parcial el cierre afectado.

Primer corte recomendado: B0/B1 y arnés E2E; segundo: historial/comparación; tercero: chats contra API. Son avances concretos que reducen el trabajo técnico de Josué mientras se gestionan accesos. No se fija fecha total sin cerrar el inventario y el alcance de cada corte.

## Intervenciones humanas mínimas y cómo las reducimos

Josué coordina estas intervenciones cuando falten; la persona propietaria o competente realiza la acción que corresponda. Algunas pueden ejecutarlas Brandon u otro integrante autorizado. El objetivo es consolidar datos y una sesión de recepción, sin prometer que terceros aprueben todo en una sola interacción.

| Intervención | Nosotros dejamos preparado / ejecutamos | Acción humana que puede quedar |
|---|---|---|
| Propiedad y accesos | Inventario, IAM mínimo, WIF, parámetros y comandos acotados | Identificar/crear cuentas propietarias, delegar acceso, resolver MFA/admin/billing ambiguo |
| Dominio, correo e Intervals | Propuesta/configuración, registros DNS, callback/scopes y ficha de registro | Obtener dominio/cuenta, registrar app bajo su propietario y tramitar aprobación/términos |
| IA, costos y negocio/legal | Opciones/evaluaciones, medición, límites, hechos de tratamiento y borradores | Decidir condiciones/gasto/modelo efectivo, precio/soporte y aprobar documentos aplicables |
| Verificación real | Guiones, cuentas sintéticas, enlaces, captura de evidencia y corrección de fallos | Consentir cuenta de proveedor/destinatario, ejecutar teléfonos físicos; revisión especializada cuando proceda |
| Recepción | Demo, accesos nominales, documentación y procedimiento de operación | Probar el recorrido y confirmar recepción/responsabilidad operativa |

La ficha externa reúne: cuenta/propietario y permisos GCP; proyectos staging/prod o autorización de creación identificada; billing/créditos/región; propietario GitHub/admin; dominio/DNS; cuenta/remitente Resend; propietario/app aprobada/callback/cuenta consentida Intervals; condiciones/modelo/región/retención/gasto IA; canal de alertas/soporte; quién realiza dispositivos y revisiones humanas. Los secretos se entregan por Secret Manager o canal seguro, nunca en la ficha pública.

Cada faltante se registra como `por definir`, `por crear`, `por configurar` o `verificado`, con dueño, siguiente acción y evidencia. No generar nuevas preguntas individuales a Brandon sobre datos que ya dijo desconocer; Josué los gestiona con los propietarios correspondientes.

## Criterios para no devolverle desarrollo pendiente a Josué

- [ ] Funciones F0–F16 del contrato implementadas e integradas; ningún ejemplo de UI se ofrece como integración real.
- [ ] Clon/instalación comprobados, instrucciones y contratos consistentes; demo reproducible o URL desplegada con acceso seguro.
- [ ] E2E PostgreSQL, navegadores y corpus/carga con resultados registrados; hallazgos resueltos.
- [ ] Intervals y ambos asistentes funcionan con proveedores reales autorizados; FIT y flujos manuales se conservan.
- [ ] Correo y Push recibidos realmente; restauración, alertas, costos y soporte comprobados.
- [ ] Producción HTTPS trazable a la versión aprobada; dispositivos y gates humanos documentados.
- [ ] A Josué le queda recibir y operar. Si algo externo impide cerrar, recibe su estado exacto, configuración preparada y la acción mínima necesaria.

No llamar «completo» a un paquete cuyo contrato sólo pasó con un transporte simulado. La planificación de este documento no cambia el estado actual: código candidato publicado, producción e integraciones reales pendientes.

## Referencias

[Inventario funcional](FUNCIONALIDADES_PRODUCTO.md) · [Matriz](MATRIZ_REQUISITOS.md) · [Plan maestro](PLAN_MAESTRO_NODO.md) · [Plan de ejecución](PLAN_EJECUCION.md) · [Evaluaciones LLM](EVALUACIONES_LLM.md) · [Operación GCP](OPERACION_GCP.md) · [Producción](RUNBOOK_PRODUCCION.md) · [Recuperación](RECUPERACION_DESASTRES.md) · [Lanzamiento](LANZAMIENTO.md).

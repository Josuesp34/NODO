# Plan de cierre antes del handover con Josué

Actualizado: 30 de septiembre de 2026. Estado: **candidato `v0.5.0-rc.1` en ejecución**.

## Objetivo y alcance vigente

Entregar el producto en código, probado e integrado, una demo reproducible, la versión GitHub y la preparación de activación que Josué pueda ejecutar. Brandon/equipo de desarrollo cierra los cambios y su evidencia; Josué coordina propietarios/accesos/decisiones y recibe la operación mediante una sesión registrada.

**Restricción posterior de Brandon:** no crear, modificar ni desplegar recursos en Google Cloud. No ejecutar Terraform apply ni workflows de despliegue; Vibe Conversa queda fuera. Código, pruebas sintéticas, PRs, integración dev/main y versiones GitHub siguen autorizados. Esta instrucción sustituye las autorizaciones cloud anteriores. Los recursos, proveedores y dispositivos reales siguen pendientes para la activación de Josué.

El plan conserva F0–F16 de [PLAN_MAESTRO_NODO.md](PLAN_MAESTRO_NODO.md), PWA única, PostgreSQL 16, Intervals principal y FIT permanente. La base publicada histórica es `v0.4.0-rc.1`; el candidato nuevo aún no se presenta como publicado. El SHA, CI, PRs y tag finales se añaden a [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md).

## Avances y cierre por paquete

| Paquete | Avance de implementación | Cierre local restante | Pendiente externo |
| --- | --- | --- | --- |
| B0 · Contratos/estado | Inventario, matriz y handover reconciliados con producto/proveedores/privacidad | Conciliar docs/API y referencias de la mezcla final | Propietarios/cuentas/condiciones nominales |
| B1 · Demo | `ops/demo.py`, Compose aislado, migración/worker y semilla idempotente de cuentas sintéticas | Verificar clon limpio, restart y guía con snapshot final | Josué reproduce y confirma recepción |
| B2 · Datos/comparación | Historial paginado/detalle, vínculo CAS, comparación determinista, calidad/días locales | Suite/E2E/benchmark del código integrado | Datos consentidos y medición cloud |
| B3 · Producto manual | Perfil/competencias, molestias/seguimiento, grupos/plantillas, propuestas y admin por selectores | Recorridos integrados y estados vacíos/error/conflicto | Aceptación del equipo piloto |
| B4 · Chats | Ambos chats contra servidor, historial, herramientas/citas, confirmación y streaming/cancelación | Evaluaciones sintéticas, permisos, replay y revocación del conjunto | Evaluación de proveedor real y recepción |
| B5 · Proveedores | Vertex ADC y OAuth/Intervals, webhook/backfill/sync/revoke durable preparados | Pruebas contractuales/reintentos/límites y estados UI de la mezcla | App/cuenta aprobadas, modelo/región/gasto e importación real consentida |
| B6 · Notificaciones | Preferencias, suscripciones cifradas, eventos/recordatorios en cola, pywebpush/worker, dedupe, revocación/plazo y escenarios precompetencia explícitos | Consolidar pruebas controladas y regresiones integradas del snapshot final | VAPID/HTTPS y recepción/baja en dispositivo consentido |
| B7 · Privacidad/comercial | Consentimiento real, export/borrado FK, retención/archivos/outbox/chats, cupos/suspensión/admin y panel de estimaciones/reservas IA | Verificar ciclo combinado, aislamiento y cifras conservadoras del snapshot final | Aviso/retención/backup, precio, soporte y cobro real administrado |
| B8 · Calidad | Corpus guardado 70 × 12 semanas, benchmark autenticado, E2E y pruebas PostgreSQL | Ejecutar arnés integrado, registrar métricas y resolver hallazgos | Teléfonos, rendimiento/seguridad de despliegue y revisión especializada |
| B9 · Plataforma preparada | Terraform, CI/builds, WIF/config, jobs/worker, almacenamiento y runbooks | Validación estática final, scripts, auditorías y CI del SHA | Josué identifica/activa recursos; sin creación/modificación Cloud en esta ejecución |
| B10 · Activación | Preflight/configuración/promoción por digest, backup/rollback y guiones preparados | Entregar pasos verificables y requisitos exactos | Josué ejecuta staging/producción, DNS/correo/proveedores, restore/alertas/costos |
| B11 · Recepción | Handover, mensaje breve, demo y pendientes con orden/responsable | Publicar snapshot/docs y completar evidencia de release | Demo de Josué y aceptación fechadas |

“Implementado” no cierra la evidencia externa de una fila. El candidato incorpora eventos/recordatorios, escenarios precompetencia y panel de costos con pruebas controladas. Escenarios: 1–42 días, 2–4 alternativas, cargas explícitas en una sola unidad y estado inicial compatible o explicado; no predicen rendimiento ni publican planes. Costos: estimaciones y reservas, sin sumar presupuestos superpuestos ni fingir tarifas/miembros históricos. La evidencia final de la mezcla y CI sigue en VALIDACION_HANDOVER.

## Trabajo técnico antes de entregar la versión

1. **Integrar y revisar.** Encadenar migraciones producto/proveedores/privacidad; montar routers vigentes y retirar handlers legacy duplicados. Revisar permisos y dependencias resueltas. Una revisión independiente verifica los cambios y los defectos concretos se corrigen antes del release.
2. **Ejecutar PostgreSQL.** Upgrade/check/downgrade/upgrade en base sintética aislada; suite de identidad/planificación/producto/proveedores/privacidad. Probar FK de atleta y coach, consentimiento revocado, cupos concurrentes, lease/heartbeat/CAS, cancelación y payload mínimo. No borrar volúmenes existentes.
3. **Comprobar navegador.** API/PWA/PostgreSQL/worker juntos: acceso/multirol, publicación/CAS, FIT/dedupe, historial/comparación, molestias/reapertura, propuestas, chats/confirmación/replay, export/borrado, administración y offline entre cuentas/pestañas/expiración. Typecheck, tests y builds Web/Lab del mismo snapshot.
4. **Medir escala.** Ejecutar el corpus 70 × 12 semanas y benchmark autenticado; registrar SHA, hardware, concurrencia, p50/p95 y casos. Contrastar objetivos de calendario/actividades sin llamar al resultado local capacidad productiva.
5. **Verificar notificaciones/escenarios/costos incorporados.** Ejecutar las regresiones integradas de eventos durables, rollback/dedupe, relación/consentimiento/fuente vigente al entregar y revocación entre trabajos. Recordatorios opt-in en la hora previa respetan silencio/zona y vencen al inicio. Escenarios y costos conservan supuestos, insuficiencia y reservas; ninguna prueba controlada acredita Push recibido o factura real.
6. **Publicar código.** Revisar diff, auditorías y CI del SHA; PR a dev, release PR a main, tag/release confirmado. Si falla un check, resolver o documentar el bloqueo real; no presentar un review nativo inaccesible como aprobado. No activar workflows cloud.
7. **Actualizar evidencia y entregar.** Conciliar estados/links/versiones, demo reproducible y este handover. Registrar exactamente qué pasó localmente y qué necesita activación. Mensaje WhatsApp sólo como borrador listo para copiar; no se envía por herramientas.

## Activación que recibe Josué

| Orden | Preparación entregada | Acción pendiente de Josué/propietario | Evidencia que debe registrar |
| --- | --- | --- | --- |
| 1 | Inventario/checklists/IaC y mapa de configuración | Confirmar cuentas propias NODO, proyectos staging/prod, billing/créditos, región/dominio, accesos GitHub/WIF y nominales | Recursos y costos brutos/netos identificados; ningún uso de Vibe Conversa |
| 2 | Terraform validado, imágenes/CI/digests y jobs | Revisar plan y activar plataforma, secretos, base privada, almacenamiento, migration/worker/bootstrap y PWA | Ejecución de migración, health autenticado, cola activa, HTTPS y revisión por digest |
| 3 | Contratos Resend/Intervals/Vertex/Push y UI | Obtener dominio/remitente, app OAuth aprobada/callback, modelo/condiciones/gasto y claves VAPID | Correo recibido, OAuth/importación/revoke, IA evaluada y Push recibido en cuenta/dispositivo consentidos |
| 4 | Runbooks backup/PITR/restore/rollback y monitoreo | Ejecutar restore aislado/rollback, probar alertas/canales y revisar costos | RPO/RTO medidos, respuestas de alertas y soporte/guardia nominales |
| 5 | Guiones de QA/accesibilidad y lista legal/comercial | Probar iOS/Android, revisar documentos/retención/precio/soporte y coordinar piloto | Evidencia fechada y checklist LANZAMIENTO aprobado |
| 6 | Snapshot publicado, demo, guías y pendientes | Reproducir y registrar recepción; acordar responsables/seguimiento | Versión, participantes, resultado y pendientes aceptados |

Los secretos se transfieren por Secret Manager o canal seguro, nunca Git/WhatsApp. Cada faltante se registra como `por definir`, `por crear`, `por configurar` o `verificado`, con propietario, siguiente acción y evidencia. No inventar accesos, créditos, aceptación de términos o recepción de Josué.

## Criterios de cierre

- [ ] Snapshot integrado dev/main, CI verificable y `v0.5.0-rc.1` realmente publicado, con enlaces exactos.
- [ ] Pruebas integradas, migraciones, builds, corpus/benchmark y E2E del mismo código documentados.
- [ ] Demo de clon limpio reproducida y documentación/API consistentes.
- [ ] Hallazgos de seguridad/correctitud cerrados o limitaciones precisas registradas.
- [ ] Todas las comprobaciones reales pendientes separadas, con pasos/responsable y sin afirmar despliegue.
- [ ] Josué reproduce el recorrido y registra recepción técnica.
- [ ] Activación/operación, proveedores/dispositivos, restore/monitoreo/legal y GO para atletas reales registrados después.

La entrega de código puede cerrarse sin modificar Google Cloud; la apertura productiva a atletas reales conserva **NO-GO** hasta las evidencias de [LANZAMIENTO.md](LANZAMIENTO.md). Referencias operativas: [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md), [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md), [EJECUCION_ENTREGA.md](EJECUCION_ENTREGA.md), [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md).

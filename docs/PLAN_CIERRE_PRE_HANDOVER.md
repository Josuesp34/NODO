# Plan de cierre antes del handover con Josué

Actualizado: 30 de septiembre de 2026. Estado: **preparación técnica cerrada para `v0.5.0-rc.1`; recepción/activación externa pendiente**.

## Objetivo y alcance vigente

Entregar el producto en código, probado e integrado, una demo reproducible, la versión GitHub y la preparación de activación que Josué pueda ejecutar. Brandon/equipo de desarrollo cierra los cambios y su evidencia; Josué coordina propietarios/accesos/decisiones y recibe la operación mediante una sesión registrada.

**Restricción posterior de Brandon:** no crear, modificar ni desplegar recursos en Google Cloud. No ejecutar Terraform apply ni workflows de despliegue; Vibe Conversa queda fuera. Código, pruebas sintéticas, PRs, integración dev/main y versiones GitHub siguen autorizados. Esta instrucción sustituye las autorizaciones cloud anteriores. Los recursos, proveedores y dispositivos reales siguen pendientes para la activación de Josué.

El plan conserva F0–F16 de [PLAN_MAESTRO_NODO.md](PLAN_MAESTRO_NODO.md), PWA única, PostgreSQL 16, Intervals principal y FIT permanente. La base publicada histórica es `v0.4.0-rc.1`; la entrega nueva se identifica por el tag `v0.5.0-rc.1` y su comprobante. SHA, CI y PRs se registran a [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md).

## Avances y cierre por paquete

| Paquete | Avance de implementación | Cierre técnico realizado | Pendiente externo |
| --- | --- | --- | --- |
| B0 · Contratos/estado | Inventario, matriz y handover reconciliados con producto/proveedores/privacidad | Documentos/API y referencias conciliados | Propietarios/cuentas/condiciones nominales |
| B1 · Demo | `ops/demo.py`, Compose aislado, migración/worker y semilla idempotente de cuentas sintéticas | Checkout limpio Docker en CI y guía reproducible | Josué reproduce y confirma recepción |
| B2 · Datos/comparación | Historial paginado/detalle, vínculo CAS, comparación determinista, calidad/días locales | Suite/E2E/benchmark integrados aprobados | Datos consentidos y medición cloud |
| B3 · Producto manual | Perfil/competencias, molestias/seguimiento, grupos/plantillas, propuestas y admin por selectores | Recorridos y estados vacíos/error/conflicto verificados | Aceptación del equipo piloto |
| B4 · Chats | Ambos chats contra servidor, historial, herramientas/citas, confirmación y streaming/cancelación | Evaluaciones sintéticas/permisos/replay/revocación aprobados | Evaluación de proveedor real y recepción |
| B5 · Proveedores | Vertex ADC y OAuth/Intervals, webhook/backfill/sync/revoke durable preparados | Contratos/reintentos/límites y UI verificados | App/cuenta aprobadas, modelo/región/gasto e importación real consentida |
| B6 · Notificaciones | Preferencias, suscripciones cifradas, eventos/recordatorios en cola, pywebpush/worker, dedupe, revocación/plazo y escenarios precompetencia explícitos | Regresiones controladas, concurrencia, fuente vigente y deadline aprobados | VAPID/HTTPS y recepción/baja en dispositivo consentido |
| B7 · Privacidad/comercial | Consentimiento real, export/borrado FK, retención/archivos/outbox/chats, cupos/suspensión/admin y panel de estimaciones/reservas IA | Ciclo, aislamiento, borrado FK y reservas verificadas | Aviso/retención/backup, precio, soporte y cobro real administrado |
| B8 · Calidad | Corpus guardado 70 × 12 semanas, benchmark autenticado, E2E y pruebas PostgreSQL | 39 E2E, corpus/benchmark y hallazgos corregidos | Teléfonos, rendimiento/seguridad de despliegue y revisión especializada |
| B9 · Plataforma preparada | Terraform, CI/builds, WIF/config, jobs/worker, almacenamiento y runbooks | Terraform estático/mock, scripts, auditorías y CI aprobados | Josué identifica/activa recursos; sin creación/modificación Cloud en esta ejecución |
| B10 · Activación | Preflight/configuración/promoción por digest, backup/rollback y guiones preparados | Pasos/requisitos entregados; imágenes comprobadas en CI, sin publicar en Artifact Registry | Josué ejecuta staging/producción, DNS/correo/proveedores, restore/alertas/costos |
| B11 · Recepción | Handover, mensaje breve, demo y pendientes con orden/responsable | Snapshot/docs, mensaje y comprobante de release | Demo de Josué y aceptación fechadas |

“Implementado” no cierra la evidencia externa de una fila. El candidato incorpora eventos/recordatorios, escenarios precompetencia y panel de costos con pruebas controladas. Escenarios: 1–42 días, 2–4 alternativas, cargas explícitas en una sola unidad y estado inicial compatible o explicado; no predicen rendimiento ni publican planes. Costos: estimaciones y reservas, sin sumar presupuestos superpuestos ni fingir tarifas/miembros históricos. La evidencia de la mezcla y CI está en VALIDACION_HANDOVER y el comprobante de release.

## Trabajo técnico ejecutado para la entrega

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
| 2 | Terraform validado, builds CI y jobs; publicación de imágenes/digests al activar | Revisar plan y activar plataforma, secretos, base privada, almacenamiento, migration/worker/bootstrap y PWA | Ejecución de migración, health autenticado, cola activa, HTTPS y revisión por digest |
| 3 | Contratos Resend/Intervals/Vertex/Push y UI | Obtener dominio/remitente, app OAuth aprobada/callback, modelo/condiciones/gasto y claves VAPID | Correo recibido, OAuth/importación/revoke, IA evaluada y Push recibido en cuenta/dispositivo consentidos |
| 4 | Runbooks backup/PITR/restore/rollback y monitoreo | Ejecutar restore aislado/rollback, probar alertas/canales y revisar costos | RPO/RTO medidos, respuestas de alertas y soporte/guardia nominales |
| 5 | Guiones de QA/accesibilidad y lista legal/comercial | Probar iOS/Android, revisar documentos/retención/precio/soporte y coordinar piloto | Evidencia fechada y checklist LANZAMIENTO aprobado |
| 6 | Snapshot publicado, demo, guías y pendientes | Reproducir y registrar recepción; acordar responsables/seguimiento | Versión, participantes, resultado y pendientes aceptados |

Los secretos se transfieren por Secret Manager o canal seguro, nunca Git/WhatsApp. Cada faltante se registra como `por definir`, `por crear`, `por configurar` o `verificado`, con propietario, siguiente acción y evidencia. No inventar accesos, créditos, aceptación de términos o recepción de Josué.

## Criterios de cierre

- Fuente de la entrega: tag `v0.5.0-rc.1` y comprobante con integración dev/main y CI del SHA exacto; verificar en [la release](https://github.com/Josuesp34/NODO/releases/tag/v0.5.0-rc.1).
- [x] Pruebas integradas, migraciones, builds, corpus/benchmark y E2E del mismo código documentados.
- [x] Demo de clon limpio reproducida y documentación/API consistentes.
- [x] Hallazgos de seguridad/correctitud cerrados o limitaciones precisas registradas.
- [x] Todas las comprobaciones reales pendientes separadas, con pasos/responsable y sin afirmar despliegue.
- [ ] Josué reproduce el recorrido y registra recepción técnica.
- [ ] Activación/operación, proveedores/dispositivos, restore/monitoreo/legal y GO para atletas reales registrados después.

La entrega de código puede cerrarse sin modificar Google Cloud; la apertura productiva a atletas reales conserva **NO-GO** hasta las evidencias de [LANZAMIENTO.md](LANZAMIENTO.md). Referencias operativas: [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md), [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md), [EJECUCION_ENTREGA.md](EJECUCION_ENTREGA.md), [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md).

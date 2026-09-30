# Funcionalidades actuales de NODO

Actualizado: 30 de septiembre de 2026. **Entrega de código `v0.5.0-rc.1`**, con demo/CI verificados. Este inventario describe implementación y límites; no acredita producción activa. SHA, CI, E2E y release se registran en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md).

“Implementado” describe código consumible por API/PWA; “probado localmente” exige evidencia sintética; “operativo externo” exige proveedor, despliegue o dispositivo reales. Una prueba con transporte HTTP interceptado no acredita recepción ni importación real.

**Restricción vigente:** no crear, modificar ni desplegar recursos Google Cloud. Código/GitHub siguen autorizados. Josué recibe IaC y runbooks para activar posteriormente; Vibe Conversa queda fuera.

## Inventario

| Área | Implementación actual | Prueba local / límite | Validación externa pendiente |
| --- | --- | --- | --- |
| Pública y sesión | Landing, acceso/activación/recuperación, soporte, privacidad/términos borrador, BFF con cookies httpOnly, refresh/logout | Tests de transporte/origen/cuerpo, contratos PWA; offline y navegador integrado aprobados en CI | HTTPS, dominio, dispositivos y aprobación de textos legales |
| Identidad | Roles múltiples, capacidades, organizaciones/membresías/asignaciones, invitación/revocación | Pruebas de aislamiento, rol actual y acceso tras revocar | Accesos nominales y recepción de Josué |
| Bootstrap | Primer administrador por job explícito, idempotente, auditado, sin habilitar registro HTTP productivo | Pruebas de creación, repetición y errores sin secretos | Ejecutar con secretos del entorno activado por Josué |
| Planificación | Bloques, sesiones/pasos/repeticiones/objetivos, CAS y publicación idempotente, Hoy/Semana/detalle atleta | Conflictos, versión publicada y permisos probados; publicación/CAS aprobados en E2E | Recorrido HTTPS y dispositivos |
| Perfil y contexto | Perfil deportivo versionado, disciplinas/parámetros/disponibilidad, competencias/prioridad, observaciones y check-in | API/PWA y pruebas de producto; fuente/vigencia y datos insuficientes | Validación de uso con participantes consentidos |
| Molestias/revisión | Alta/evolución, historial, bandeja, decisión/seguimiento y reapertura | Prioridad visible y separación de cierre/decisión; no diagnóstico | Recepción del flujo por equipo piloto |
| FIT | Carga autenticada, hash por atleta, laps/telemetría, auditoría y recálculo en cola | Una sola sesión, máximo 10 MiB; pruebas duplicados/acceso/fechas | Archivos consentidos de dispositivos soportados |
| Actividades/comparación | Historial paginado, detalle, vínculo editable con versión, comparación determinista por disciplina y día local | Laps sólo si alineación compatible; triatlón sin segmentación comparable; falta de datos no es incumplimiento | Rendimiento cloud y datos reales consentidos |
| Grupos/plantillas/propuestas | Miembros/excepciones, plantillas editables y aplicación idempotente, evidencia/diff y decisión de propuestas | Permisos, asignación vigente, base obsoleta y doble aplicación protegidos | Recepción con equipo piloto |
| Ambos asistentes | Chats persistidos coach/atleta, listado/historial, herramientas/citas autorizadas, previews/confirmaciones, streaming/cancelación y replay | Simulador explícito para demo; HTTP Vertex controlado; no guardan/devuelven respuesta tras revocación durante consulta | Modelo/región/condiciones y evaluación real aprobados |
| Uso IA | Reservas/límites por usuario y organización; panel de uso/costos por mes UTC para cuenta propia o administrador | Runs contados una vez, completados separados de reservas en curso/inciertas; presupuestos usuario/organización no se suman; tarifas/miembros/denominadores actuales | Tarifa/consumo real contrastados, presupuesto y operación |
| Intervals.icu | OAuth/state de un uso vinculado a sesión, cifrado, callback, estado UI, webhook/cola, backfill, sync/reconexión/desconexión | HTTP interceptado, scopes mínimos de lectura, dedupe y revocación durable; no refresh token inventado | App aprobada, callback, fuente permitida y cuenta consentida; importación real |
| Correo | Resend en outbox cifrado, invitación/recuperación de un uso, revocación de sesiones, revalidación de entrega | Transporte simulado y pruebas de token/sesión; aceptación en cola no es recepción | Dominio/remitente, cuenta/secretos, entrega/bounce reales |
| Push | Preferencias por categoría, zona/silencio, suscripciones cifradas, cola/dedupe, payload mínimo, baja y endpoints vencidos | Eventos durables de publicación/molestias/propuestas/problemas de sync; recordatorios opt-in en la hora previa, silencio/zona/dedupe/plazo; pywebpush con HTTP interceptado | VAPID/HTTPS y recepción/baja en teléfono consentido |
| Precompetencia | API/PWA para 2–4 alternativas de 1–42 días hasta competencia, cargas diarias explícitas en TRIMP o TSS | CTL/ATL del día anterior compatible o supuesto explicado; ausencia devuelve insuficiencia, sin convertir unidades, predicción de marca ni publicación | Revisión de uso del equipo y datos consentidos |
| Privacidad | Consentimiento por finalidad, revocación, exportación propia y borrado/desidentificación con relaciones FK | PostgreSQL/SQLite: protege chats/resultados de atleta revocado, conserva datos ajenos y limpieza durable; no exporta secretos | Aviso definitivo, base/plazo financieros y política de backups |
| Retención/archivos | Job periódico deduplicado, borrado temporal de fuentes/derivados/chats/outbox y archivos; adaptadores local/REST GCS | Limpieza local probada; trabajos externos conservan reintentos; backups no se reescriben | Borrado remoto/restauración y retención real tras activación de Josué |
| Comercial | Catálogos autorizados, planes/suscripciones/pagos manuales, cupos y suspensión | Carrera real PostgreSQL y aislamiento; sin pasarela, facturación ni precio inventado | Precio/soporte/condiciones y responsables de negocio |
| Worker/calidad | PostgreSQL persistente, claims/lease/heartbeat, reintentos/CAS; corpus 70 × 12 semanas y benchmark HTTP autenticado | Suite, migraciones, reinicio y carga locales; resultados exactos en validación final | Cloud bajo carga definida, alertas y dispositivos |
| Plataforma | Terraform staging/prod, Cloud Run/SQL, Storage/secretos, WIF, CI, backup/rollback y operación | Validación estática, pruebas/builds y preflight; no aplica ni despliega Cloud | Josué identifica recursos/cuentas y activa, prueba restore/monitoreo/costos |

## IA: configuración y alcance

La demo conserva `AI_PROVIDER=simulated`: respuesta determinista sin red externa. El adaptador `vertex` existe con ADC, proyecto/región/modelo configurables y salida validada. No se activa por tener variables vacías; requiere consentimiento, configuración, presupuesto positivo y evaluación real. `AI_API_KEY` genérica no sustituye autenticación ADC.

Las herramientas leen perfil, calendario, actividades, comparación, observaciones, resumen, sincronización, check-ins, molestias, revisión, grupos y calidad con autorización del servidor. Las métricas provienen de cálculos deterministas. Una propuesta requiere preview y confirmación vigente; el asistente no publica planes ni autoriza entrenamiento.

La procedencia interna registra todos los atletas usados en contexto e historial, aunque el modelo omita citarlos. Se revalida tras el proveedor, en historial, replay, exportación y borrado. Un dato enviado cuando existía consentimiento no puede retirarse del proveedor por este control. No se guarda ni devuelve una respuesta tras revocación. El chat personal no se comparte íntegro con el coach.

## Intervals: contrato preparado y verificación pendiente

El conector real es de lectura y exige una app aprobada. Importa sólo fuentes y campos admitidos, conserva calidad/procedencia, respeta límites y reconecta ante un token inválido. La API oficial no documenta refresh token: no se inventa una renovación. Un token emitido que pierde autorización antes de persistirse queda cifrado en limpieza durable; el estado OAuth consumido no puede reutilizarse.

FIT manual sigue disponible. Los handlers legacy de alta/baja simulada están cerrados para no borrar un token real mediante el recorrido anterior. La pantalla confirma el estado del servidor; una simulación o configuración incompleta no se presenta como conexión real.

## Avisos, escenarios y costos

Los eventos se guardan junto a la mutación del producto y pasan por un worker con revalidación del destinatario, consentimiento, relación y fuente/versiones antes de Push. Los recordatorios respetan preferencias/silencio/zona y vencen al inicio de la sesión. No se incluye contenido de salud en el aviso. Las pruebas controladas cubren dedupe, rollback, revocación/borrado y concurrencia PostgreSQL; no acreditan entrega física.

Los escenarios son hipótesis manuales del coach autorizado en una sola unidad y requieren cargas explícitas por día. El estado inicial proviene del día anterior compatible o de un supuesto explicado. CTL/ATL/TSB son cálculos matemáticos; el calendario no se modifica y las molestias permanecen visibles.

El panel IA muestra estimaciones guardadas y reservas conservadoras, con acceso propio o administrativo. Los fallos/cancelaciones conservan consumo incierto; el presupuesto de organización y el de usuario representan ámbitos superpuestos y no se suman. Modelo/tarifa/roles/denominadores mostrados son actuales, no una reconstrucción histórica. No consulta facturación externa ni incluye costos de infraestructura.

## Evidencia y cierre

Las pruebas de cada paquete están en el repositorio; [VALIDACION_PRIVACIDAD_PUSH.md](VALIDACION_PRIVACIDAD_PUSH.md) documenta el ciclo SQLite/PostgreSQL y correcciones de procedencia/OAuth. [QA_CORPUS_70_ATLETAS.md](QA_CORPUS_70_ATLETAS.md) describe corpus y medición reproducibles. El cierre de integración consolida suite, builds, Alembic, E2E, benchmark, auditorías y CI del SHA exacto en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md); no se reutilizan cifras del candidato anterior como resultado de éste.

Recepción Push, correo, OAuth/IA reales, HTTPS, restore, costos cloud, teléfonos físicos, aceptación de Josué y aprobaciones legales/comerciales conservan su estado pendiente. [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md) permite cerrar cada requisito con su evidencia correspondiente.

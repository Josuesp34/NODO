# Handover de NODO con Josué

Actualizado: 30 de septiembre de 2026. Responsable de entrega: Brandon.
Estado: **candidato `v0.5.0-rc.1` en ejecución; cierre de integración y publicación pendiente**.

El objetivo es entregar el código, la demo reproducible y una lista concreta de activación para Josué. El candidato incorpora producto, proveedores, privacidad y operación; la revisión final, las pruebas de la mezcla y el CI del SHA final se registran en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md). No equivale a producción activa ni a recepción aceptada por Josué.

**Instrucción vigente de Brandon:** no crear, modificar ni desplegar recursos en Google Cloud. La autorización de código, commits, PRs, integración y versiones GitHub sigue vigente. Josué recibe Terraform, configuración y runbooks para activar la plataforma posteriormente. **Vibe Conversa queda fuera de NODO**. Las autorizaciones de despliegue de documentos históricos quedan sustituidas por esta restricción.

## Qué se entrega y qué falta

| Área | Código preparado y pruebas locales | Activación o comprobación pendiente |
| --- | --- | --- |
| PWA e identidad | App única coach/atleta, multirol, organizaciones, sesión BFF, invitación/recuperación, bootstrap admin por job | HTTPS, dominio, identidad operativa y recepción real de correo |
| Producto manual | Calendario, sesiones estructuradas, CAS/publicación, perfiles/competencias, check-ins, molestias/revisión, grupos/plantillas y propuestas | Demo de recepción de Josué y QA de dispositivos físicos |
| Datos deportivos | FIT, historial/detalle paginado, vínculo editable a sesión, comparación determinista, fuente/calidad y días locales | Probar con datos consentidos; no asumir equivalencia de unidades ni cumplimiento cuando faltan datos |
| Intervals.icu | Inicio/callback OAuth, state de un uso, scopes de lectura, tokens cifrados, webhook, backfill/sync, reconexión y revocación durable | App aprobada, callback/dominio, cuenta consentida e importación real |
| Asistentes | Chats persistidos coach/atleta, herramientas autorizadas, citas, preview/confirmación, streaming/cancelación, límites/uso y adaptador Vertex | Modelo/región/condiciones/costo aprobados y evaluación con proveedor real; demo usa simulador explícito |
| Notificaciones | Preferencias, zona/silencio, suscripciones cifradas, avisos de producto en cola, recordatorios opt-in en la hora anterior a una sesión, dedupe, baja/expiración y payload mínimo | Claves VAPID, HTTPS y recepción/baja en dispositivo consentido |
| Privacidad y comercial | Consentimiento por finalidad, exportación/borrado FK, limpieza durable de archivos/tokens/chats, retención periódica, cupos/suspensión y administración por entidades autorizadas | Aviso/retención legal, política de backups, soporte y precio; cobros administrados, sin pasarela |
| Calidad/plataforma | Corpus sintético 70 × 12 semanas, benchmark autenticado, E2E, PostgreSQL, worker con lease, IaC/CI y runbooks | Cierre de pruebas/CI final, dispositivos, rendimiento cloud, restauración y operación reales |

El inventario detallado está en [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md); la matriz separa implementación, prueba local y validación externa en [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md). El candidato incorpora escenarios precompetencia de cargas explícitas y panel de costos IA: están probados con datos sintéticos y conservan sus límites. Los escenarios no predicen rendimiento ni publican planes; los costos son estimaciones/reservas, no facturas.

## Versión y fuente de entrega

- Base histórica publicada: [`v0.4.0-rc.1`](https://github.com/Josuesp34/NODO/releases/tag/v0.4.0-rc.1).
- Objetivo actual: **`v0.5.0-rc.1`, candidato en ejecución; todavía no se presenta como publicado**.
- La rama de integración y los PRs del candidato se registran en [EJECUCION_ENTREGA.md](EJECUCION_ENTREGA.md). El cierre registra SHA, PRs, checks y tag exactos en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md).
- Usar el tag publicado y confirmado en esa evidencia para entregar un snapshot. No utilizar una carpeta con cambios sin versionar, compartir `.env` ni copiar secretos por WhatsApp.
- `frontend/apps/nodo-web` es la PWA activa. Lab y Expo conservan sus referencias; Expo no forma parte del workspace activo.

## Demo local para Josué

Requisitos: Git, Python 3 y Docker Desktop con Compose. La demo utiliza únicamente cuentas sintéticas y puertos de loopback. Desde el snapshot confirmado:

```bash
git clone https://github.com/Josuesp34/NODO.git
cd NODO
# Cambiar al tag confirmado en VALIDACION_HANDOVER.md cuando se publique.
python3 ops/demo.py up
python3 ops/demo.py status
```

En Windows, usar `py` en lugar de `python3`. El script compila API/PWA, inicia PostgreSQL, ejecuta Alembic, comprueba salud, inicia worker y siembra cuentas idempotentes. La URL predeterminada es `http://127.0.0.1:3300`. Las credenciales sintéticas se generan en `.local/nodo-demo/credentials.json`, con permisos locales; nunca enviarlas como configuración productiva. API/OpenAPI local: `http://127.0.0.1:8800/docs`.

La demo conserva una base aislada en `.local/nodo-demo/postgres`. Los puertos predeterminados 55432/8800/3300 deben estar libres; `NODO_DEMO_DB_PORT`, `NODO_DEMO_API_PORT` y `NODO_DEMO_WEB_PORT` permiten cambiarlos antes del primer arranque. Detener sin borrar datos:

```bash
python3 ops/demo.py stop
```

No exponer esta demo a internet ni reutilizar sus claves en producción. El estado de la prueba de clon limpio y los comandos de recuperación se registran en la guía de arranque y validación mantenida por integración. La existencia del script no sustituye su comprobación final.

## Sesión de recepción (45–60 minutos)

- [ ] Josué clona el snapshot confirmado y levanta la demo sin archivos personales de Brandon.
- [ ] Entra como coach, atleta, persona sin coach y cuenta multirol; comprueba login/logout y permisos.
- [ ] Crea/edita/publica sesión; atleta ve sólo la versión publicada. Una edición obsoleta responde conflicto.
- [ ] Importa FIT sintético repetido, revisa historial/detalle y comparación; un duplicado no crea otra actividad.
- [ ] Registra check-in/molestia, revisa evolución y decide con motivo; prueba una propuesta obsoleta.
- [ ] Usa ambos chats en modo simulado explícito, abre citas y confirma un borrador. Revoca asignación/consentimiento y comprueba historial, replay y exportación protegidos.
- [ ] Revisa preferencias Push, exportación/borrado y administración sintética. No confundir transporte HTTP de prueba con recepción física.
- [ ] Compara dos alternativas de carga hasta una competencia, revisa supuestos/estado inicial y el panel de estimaciones/reservas IA. Muestra recordatorios con transporte controlado; la recepción física permanece pendiente.
- [ ] Registra fecha, participantes, versión, resultado, pendientes y responsable. La recepción de Josué no está realizada aún.

## Secuencia pendiente de activación con Josué

| Orden | Trabajo | Responsable | Evidencia de cierre |
| --- | --- | --- | --- |
| 1 | Terminar mezcla, demo, suite, E2E y CI; integrar dev/main y publicar candidato | Brandon/equipo de desarrollo | SHA, PRs, CI y tag exactos en VALIDACION_HANDOVER |
| 2 | Confirmar cuenta/proyectos propios NODO, billing/créditos, región, dominio y permisos | Josué coordina propietarios | Inventario nominal y costos confirmados; Vibe fuera |
| 3 | Configurar Terraform/WIF/Secret Manager, API/PWA privadas donde corresponde, worker/jobs y migraciones | Josué activa después de la entrega | Plan revisado, digests, ejecución de migración y HTTPS; esta ejecución no modifica Cloud |
| 4 | Activar Resend, Intervals y modelo Vertex aprobado | Josué con propietarios de proveedores | Dominio verificado, correo recibido, importación/revocación consentidas y evaluación IA real |
| 5 | Configurar VAPID y ejecutar Push/dispositivos, rendimiento y accesibilidad | Josué coordina cuenta/dispositivos consentidos | Recepción/baja, iOS/Android y resultados fechados |
| 6 | Ejecutar backup/PITR, restore aislado, rollback, alertas y revisión de costos | Josué recibe/activa operación | RPO/RTO medidos, canales de alerta y accesos nominales |
| 7 | Resolver aviso de privacidad/retención, precio, soporte y piloto | Responsables humanos coordinados por Josué | Checklist LANZAMIENTO completo y GO documentado |

La infraestructura se entrega preparada. **No ejecutar `terraform apply`, jobs remotos ni workflows de despliegue como parte de este cierre**. Configurar variables no prueba una integración real. Las condiciones y secretos de proveedores se transfieren por un canal seguro; el handover y WhatsApp contienen sólo estado y enlaces públicos.

## Cierre del handover

La entrega técnica queda cerrada cuando el snapshot está publicado, sus checks son verificables, Josué reproduce la demo y los pendientes tienen responsable. La entrega operativa requiere además producción/proveedores, dispositivos, restauración, monitoreo, condiciones legales/comerciales y recepción registrados por separado.

Plan: [PLAN_CIERRE_PRE_HANDOVER.md](PLAN_CIERRE_PRE_HANDOVER.md). Mensaje listo para copiar: [MENSAJE_WHATSAPP_JOSUE.md](MENSAJE_WHATSAPP_JOSUE.md). Runbooks: [OPERACION_GCP.md](OPERACION_GCP.md), [RUNBOOK_PRODUCCION.md](RUNBOOK_PRODUCCION.md), [RECUPERACION_DESASTRES.md](RECUPERACION_DESASTRES.md), [RESEND_CONFIGURACION.md](RESEND_CONFIGURACION.md) y [LANZAMIENTO.md](LANZAMIENTO.md).

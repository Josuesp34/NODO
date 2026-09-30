# Evidencia de entrega de NODO

Actualizado: 30-09-2026. Candidato **v0.5.0-rc.1** en cierre de integración/CI. El resultado final de publicación se incorpora aquí y en el comprobante adjunto a la release; no reutilizar las cifras históricas de v0.4.0-rc.1.

## Pruebas del corte integrado

| Comprobación | Resultado comprobado | Entorno y límite |
| --- | --- | --- |
| Backend completo | 197 aprobadas, 1 omitida opcional | Python 3.12.7, SQLite y PostgreSQL 16 local; corte 81aeac5. Los avisos se incorporan después y actualizan este resultado |
| Migraciones | upgrade/check/downgrade/upgrade y ciclo desde base aprobados | PostgreSQL 16 aislado; cabeza 0009_operations; no Cloud SQL |
| PWA | 40 pruebas aprobadas, typecheck y builds Web/Lab aprobados | Next 16.3.8; API/BFF, permisos y guard del service worker |
| Navegador | 27 casos del corte previo; corrección y regresión de cambio de cuenta en integración | Chromium escritorio/móvil y WebKit emulados; resultado del conjunto final se registra al cerrar |
| Infraestructura | 7 pruebas Terraform con providers simulados; validate staging/prod | Terraform 1.13.3, sin plan remoto/apply ni credenciales cloud |
| Scripts | 14 pruebas de smoke/backup/restore con HTTP/CLI simulados; 3 guardas del corpus | Comprueban contratos/fallos, sin restauración ni recursos reales |
| Dependencias | npm runtime/total y pip runtime/desarrollo sin advisories conocidos al consultar | CI repite npm/pip-audit, OSV, Trivy y CodeQL; registrar su SHA final |
| Higiene | Ruff check/format, pre-commit y diff-check aprobados | Sin secretos, FIT reales ni artefactos en Git |

Las regresiones incluyen permisos después de revocar, procedencia de todos los atletas usados por IA, bloqueo de replay/historial/export, limpieza OAuth durable, FIT original privado, todas las generaciones GCS, retención FIT/export independiente, claims/lease/fencing del worker y expiración/limpieza de la copia offline. El transporte de proveedores está interceptado con datos sintéticos: no acredita importación, correo, Vertex ni Push reales.

## CI y publicación

El [PR completo #13](https://github.com/Josuesp34/NODO/pull/13) concentra los paquetes y sus correcciones. Los checks del primer corte confirmaron backend/PG/migraciones/builds/demo desde cero; se corrigió el lock de Terraform para incluir checksums oficiales Linux y Mac. El cierre exige CI del último SHA, integración en dev/main, tag y readback del comprobante. Mientras ese registro no esté completo, el candidato sigue en ejecución.

Dependency Review nativo es opcional y no se cuenta como aprobado si la API/permisos del propietario lo omiten. Las auditorías directas obligatorias no tienen excepciones para dependencias vulnerables.

## Alcance del navegador y la demo

La demo ejecutada localmente conserva API/PostgreSQL/worker en Docker y la PWA standalone en el host. Docker Desktop alcanzó su límite de disco al exportar la imagen PWA; sólo se limpiaron cachés propios. La prueba CI de checkout limpio construye/inicia todos los servicios Docker, sin archivos personales. Su resultado final se registra en el comprobante; la prueba local no se presenta como esa evidencia.

Chromium escritorio/móvil comprueba navegación completa offline. WebKit comprueba la página abierta sin red, borrado y vencimiento; la navegación completa sin red está limitada por [Playwright #42775](https://github.com/microsoft/playwright/issues/42775). Las pruebas de denegación y respuestas viejas deshabilitan el SW para interceptar exactamente el transporte. El guard del SW comprueba que nunca cachea /api. Safari/iOS/Android físicos y HTTPS siguen pendientes.

## Pendientes externos de Josué

- Proyecto/cuenta/billing/dominio NODO, WIF/Environments y activación Google Cloud.
- Resend, OAuth Intervals, Vertex/modelo/gasto y VAPID con recepción/importación/evaluación reales.
- Dispositivos físicos, rendimiento del despliegue, alertas/costos, backup/PITR/restore/rollback reales.
- Aviso/retención legal, precio/soporte y aceptación fechada de Josué.

**Instrucción vigente:** no crear, modificar ni desplegar Google Cloud en esta ejecución. Vibe Conversa queda fuera. No se enviaron mensajes reales ni se registró aceptación humana. La release publica código; no acredita producción ni GO para atletas reales.

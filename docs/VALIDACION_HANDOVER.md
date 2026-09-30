# Evidencia de entrega de NODO

Actualizado: 30-09-2026. Entrega **v0.5.0-rc.1**. El [tag y la release](https://github.com/Josuesp34/NODO/releases/tag/v0.5.0-rc.1) identifican el snapshot; el adjunto `nodo-v0.5.0-rc.1-evidence.json` registra SHAs, PRs, checks y mediciones definitivos. Su checksum acompaña al archivo. No reutilizar las cifras de v0.4.0-rc.1.

## Pruebas del código integrado

El corte `c29a5844fb2a55b5c9a10d669ed201df1b0d33f2`, integrado mediante [PR #13](https://github.com/Josuesp34/NODO/pull/13), aprobó los seis workflows y CodeQL. Los cambios posteriores de documentación conservan el código probado; CI vuelve a verificar la integración y el SHA de main antes del tag. El comprobante adjunto contiene esos resultados finales.

| Comprobación | Resultado comprobado | Entorno y límite |
| --- | --- | --- |
| Backend completo | 262 aprobadas, 7 omitidas | Python 3.12, PostgreSQL 16 real en CI; omisiones exclusivas de SQLite/selección de motor |
| Backend sin PostgreSQL | 181 aprobadas, 88 omitidas en cada Python 3.11/3.12 | Los casos PG se ejecutan en el job separado; no sumar motores como pruebas distintas |
| Migraciones | upgrade/check/downgrade/upgrade y ciclo desde base aprobados | PostgreSQL 16 aislado; cabeza 0009_operations; no Cloud SQL |
| PWA | 41 pruebas aprobadas; typecheck y builds Web/Lab aprobados | Next 16.3.8; BFF, refresh concurrente, permisos y guard del service worker |
| Navegador | 39 casos aprobados | Chromium escritorio/móvil y WebKit emulados, contra API/PostgreSQL/worker reales de la demo Docker |
| Infraestructura | 7 pruebas Terraform con providers simulados; validate staging/prod | Terraform 1.13.3; sin plan remoto/apply ni credenciales cloud |
| Scripts | 14 pruebas smoke/backup/restore HTTP/CLI simulados; 3 guardas del corpus | Contratos/fallos; sin restauración productiva ni recursos reales |
| Dependencias y seguridad | Auditorías obligatorias, OSV, Trivy y CodeQL aprobados | npm/pip sin advisories conocidos en ese corte; no equivale a pentest/review humano |
| Higiene | Ruff, pre-commit y diff-check aprobados | Sin secretos, FIT reales ni artefactos privados en Git |

Logs: [backend/PG](https://github.com/Josuesp34/NODO/actions/runs/36754867760), [navegador/corpus](https://github.com/Josuesp34/NODO/actions/runs/36754867773), [frontend](https://github.com/Josuesp34/NODO/actions/runs/36754867892), [plataforma](https://github.com/Josuesp34/NODO/actions/runs/36754867745), [seguridad](https://github.com/Josuesp34/NODO/actions/runs/36754867766) e [higiene](https://github.com/Josuesp34/NODO/actions/runs/36754867754).

Las regresiones cubren revocación durante IA/replay/historial/export, OAuth durable, FIT privado, generaciones GCS, retención independiente, claims/lease/fencing, fuentes Push revalidadas tras locks y justo antes del transporte, vencimiento de recordatorios, fallo terminal de sync y límites de autenticación atómicos. Offline se invalida al cambiar cuenta/cerrar sesión/revocar/vencer; una respuesta antigua no restaura datos ni elimina cookies de un login nuevo.

El hallazgo CodeQL de ruta local se corrigió con resolución real y comprobación del directorio permitido, incluida una regresión de enlaces que escapan. CodeQL aprobó y el ref del PR quedó sin alertas abiertas, sin suprimir ni descartar el hallazgo.

Dependency Review nativo queda **omitido por permisos/configuración del propietario**; no se cuenta como aprobado. Las auditorías directas son obligatorias y no exceptúan dependencias vulnerables.

## Corpus y medición

CI crea 70 atletas sintéticos × 84 días: 5.880 check-ins/cargas diarias, 3.360 entrenamientos, 3.085 actividades, 10.004 laps y 9.255 puntos de telemetría. Rechaza 70 duplicados y comprueba datos incompletos/tardíos, medianoche, multirol, molestias y revocación.

El benchmark de referencia hizo 280 lecturas HTTP autenticadas, concurrencia 8 y dos rondas: p95 calendario 0,1328 s y actividades 0,1253 s, bajo sus umbrales. Entorno Linux x86_64 de cuatro CPU. SHA de checkout del PR: `04ea9d5379a79e2061c29f79825cb68dff6a77ea`, distinto del head al ser un merge sintético; `working_tree_dirty=false`. Configuración: `70a98fde43139ebbced7671b0f6258c01c54c6e0f35b056d3b74528810ba3759`.

Los reportes finales `qa-seed.json` y `qa-benchmark.json` adjuntos se toman del CI de main del SHA etiquetado. Registrar hardware/concurrencia/fecha al comparar. La medición sintética no acredita capacidad o latencia de Google Cloud, clientes ni IA reales.

## Alcance de la demo y navegador

CI verifica checkout limpio: construye API/PWA, migra e inicia PostgreSQL/API/worker/PWA en Docker sin archivos personales. Construye imágenes para comprobarlas; no las publica en Artifact Registry ni despliega.

En el equipo local Docker Desktop alcanzó su límite de disco. Sólo se limpiaron cachés propios; la continuación usó PostgreSQL Docker y API/worker/PWA en el host. Esa pasada local no sustituye la prueba Docker completa de CI. [ARRANQUE_Y_OPERACION](ARRANQUE_Y_OPERACION.md) incluye recuperación por falta de espacio sin borrar otros proyectos.

Chromium escritorio/móvil comprueba navegación completa offline. WebKit comprueba la página abierta sin red, borrado y vencimiento; la navegación completa sin red está limitada por [Playwright #42775](https://github.com/microsoft/playwright/issues/42775). Las pruebas de denegación/respuestas antiguas deshabilitan SW para interceptar el transporte. El guard comprueba que SW nunca cachea `/api`. Safari/iOS/Android físicos y HTTPS siguen pendientes.

Los proveedores usan transporte interceptado y datos sintéticos: no acredita correo, importación Intervals, Vertex ni Push reales. La revisión independiente fue técnica por agentes; no se registra aprobación humana de Josué.

## Pendientes externos de Josué

- Proyecto/cuenta/billing/dominio NODO, WIF/Environments y activación Google Cloud.
- Resend, OAuth Intervals, Vertex/modelo/gasto y VAPID con recepción/importación/evaluación reales.
- Dispositivos físicos, rendimiento del despliegue, alertas/costos y backup/PITR/restore/rollback reales.
- Aviso/retención legal, precio/soporte y aceptación fechada de Josué.

**Instrucción vigente:** no crear, modificar ni desplegar Google Cloud en esta ejecución. Vibe Conversa queda fuera. No se enviaron mensajes reales ni se registró aceptación humana. La release publica código; atletas reales conservan NO-GO hasta [LANZAMIENTO](LANZAMIENTO.md).

# Arranque y operación para Josué

Actualizado: 30-09-2026. Entrega candidata `v0.5.0-rc.1`; comprobar publicación y evidencia en [VALIDACION_HANDOVER](VALIDACION_HANDOVER.md).

## Recibir y levantar la demo

Instalar Git, Python 3 y Docker Desktop con Compose y motor Linux activo. No requiere credenciales cloud, Node ni una base previa. Reservar espacio para las imágenes/compilación; si Docker muestra `ENOSPC`, ampliar su disco antes de repetir. No borrar imágenes o volúmenes de otros proyectos.

```bash
git clone https://github.com/Josuesp34/NODO.git
cd NODO
git checkout v0.5.0-rc.1
python3 ops/demo.py up
python3 ops/demo.py status
```

Windows: sustituir `python3` por `py`. Abrir `http://127.0.0.1:3300`; cuentas/password sintéticos se generan en `.local/nodo-demo/credentials.json`. Hay administrador, coach, atleta, persona sin coach y cuenta multirol. API local: `http://127.0.0.1:8800/docs`. La IA y el envío externo permanecen simulados; no usar la demo con datos reales ni exponerla a internet.

`up` compila contenedores, crea base aislada, aplica Alembic hasta `0009_operations`, inicia API/worker/PWA, espera salud y siembra por API. Repetir no duplica las cuentas/sesión de la demo. Las credenciales y el almacenamiento están ignorados por Git. Cada checkout tiene nombre Compose propio.

Puertos por defecto: 3300 PWA, 8800 API y 55432 PostgreSQL, ligados a loopback. Si están ocupados, establecer `NODO_DEMO_WEB_PORT`, `NODO_DEMO_API_PORT`, `NODO_DEMO_DB_PORT` antes del primer arranque. En un arranque existente, detenerlo y editar únicamente esos tres valores de `.local/nodo-demo/.env`; no cambiar password o URL de la base ya creada. Para el navegador E2E con puertos propios, usar `NODO_E2E_WEB_URL` y `NODO_E2E_API_URL` correspondientes.

## Recorrido de recepción

1. Coach: abrir atletas, perfil/calendario, crear borrador y publicarlo. Atleta: comprobar Hoy/Semana; sólo ve lo publicado.
2. Importar un FIT sintético, repetirlo y revisar historial, detalle, enlace a sesión y comparación. Faltas de sensores/unidades se muestran como datos insuficientes.
3. Guardar check-in/molestia y revisar evolución/decisión en coach. Probar grupos, plantillas y propuestas con versión vigente.
4. Abrir ambos chats; verificar el indicador de simulación, citas e historial. Una confirmación crea borrador; la publicación requiere acción del coach.
5. Revisar escenarios precompetencia con sus supuestos, preferencias de avisos y uso/costo IA estimado. No confundir estimación con factura ni la cola con Push recibido.
6. Probar multirol, cierre/cambio de cuenta en dos pestañas y copia offline con vencimiento de 24 h. Exportación/borrado: sólo con cuentas sintéticas de prueba que se puedan eliminar.
7. Administrador: planes/cupos/suscripciones manuales, cola y estado del worker. No fijar precio ni simular un pago real para cerrar la recepción.

Registrar versión, fecha, participantes, resultado y pendientes en [HANDOVER_JOSUE](HANDOVER_JOSUE.md). La aceptación de Josué requiere esa sesión real.

## Detener, inspeccionar y recuperar

```bash
python3 ops/demo.py status
python3 ops/demo.py logs
python3 ops/demo.py restart-worker
python3 ops/demo.py seed
python3 ops/demo.py stop
```

`stop` conserva PostgreSQL/archivos; `up` vuelve a iniciar. Nunca usar `down -v` para solucionar un fallo. Si falla migración o salud, revisar `logs`, puertos y espacio libre; conservar el error y versión exacta antes de cambiar configuración. Si faltan credenciales, `seed` regenera el archivo local y reutiliza la semilla; no recrear la base. Reiniciar el worker conserva los trabajos pendientes y recupera leases caducados.

Las copias locales viven en `.local/nodo-demo/postgres` y `.local/nodo-demo/files`; parar antes de respaldarlas. No subir esos directorios ni logs con cookies/secrets a GitHub o WhatsApp. Un dump de desarrollo no acredita backup/restore productivo.

## Repetir la verificación técnica

Para desarrollar/pruebas, instalar dependencias de `backend/api/requirements-dev.txt` en Python 3.11/3.12 y ejecutar `npm ci` en `frontend` con Node 22. Desde `frontend`:

```bash
npm run typecheck
npm run test:web
npm run build:web
npm run build:lab
npx playwright install --with-deps chromium webkit
npm run test:e2e
```

Desde raíz, con el intérprete que tiene las dependencias backend: `python ops/qa_demo.py` siembra el corpus local de 70 atletas × 12 semanas y mide solicitudes autenticadas; guarda reportes sintéticos en `.local/nodo-demo/qa-*.json`. El guard rechaza ejecución sin entorno explícito de desarrollo o destino permitido. Este corpus modifica únicamente la demo sintética y no debe apuntar a un servidor externo. Consultar [QA_CORPUS_70_ATLETAS](QA_CORPUS_70_ATLETAS.md).

CI repite Docker desde checkout limpio, E2E, corpus, PostgreSQL/migraciones, builds, infraestructura y seguridad. Los checks y sus límites se leen en la evidencia de release. WebKit emulado no sustituye Safari/iOS físico; la navegación totalmente offline se verifica con Chromium y la vista ya abierta con WebKit por una limitación documentada del emulador.

## Activación externa reservada a Josué

Esta ejecución no crea, modifica ni despliega Google Cloud. Vibe Conversa queda fuera. Para activar NODO, seguir en orden el [plan de pendientes](PLAN_CIERRE_PRE_HANDOVER.md#activación-que-recibe-josué), [runbook de producción](RUNBOOK_PRODUCCION.md) y [configuración de proveedores](RUNBOOK_PROVEEDORES_OPERACION.md).

Josué coordina cuentas/proyectos/billing/dominio; WIF y Environments; Terraform/Secret Manager y migración/bootstrap; Resend, OAuth Intervals, Vertex y VAPID. Luego verifica HTTPS, recepción real, dispositivos, backup/PITR/rollback, alertas y costos. Aviso de privacidad, precio, soporte y GO del piloto requieren decisión humana. No registrar un pendiente como cerrado por tener una variable o un script.

FIT privados usan prefijo por dueño y retención de 365 días desde ingesta/creación del objeto; exportaciones 30 días. La retención de datos de actividad se aplica por fecha y la de backups tiene política propia. Borrado remoto/PITR y plazos legales deben verificarse al activar; el código de limpieza conserva reintentos cuando falla el proveedor.

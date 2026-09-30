# Frontend vigente: PWA unificada

Actualizado: 30 de septiembre de 2026. Candidato `v0.5.0-rc.1` en ejecución.

El producto activo es `frontend/apps/nodo-web`, una PWA Next.js con módulos coach, atleta y ajustes. `nodo-lab` conserva la referencia anterior y se compila para detectar regresiones. Expo (`nodo-mobile`) está congelado y fuera del workspace activo según ADR 0003; no reactivarlo sin revisar dependencias/seguridad.

Código y pruebas locales siguen autorizados; no crear, modificar ni desplegar Google Cloud. Josué recibe el frontend y la configuración preparada. Vibe Conversa queda fuera.

## Sesión y autorización

El navegador llama rutas same-origin de Next. El BFF envía el access token a FastAPI; access/refresh permanecen en cookies httpOnly y SameSite=Lax, con Secure para HTTPS. Refresh rotado y logout revocado se resuelven en servidor. La PWA utiliza capacidades de la identidad multirol; los permisos definitivos se comprueban en el backend para cada recurso.

Login, activación, recuperación, logout y escrituras requieren el Origin exacto. Configurar `NODO_APP_ORIGIN` con la URL canónica; headers de host externos no autorizan escrituras. Los límites incrementales son sesión 16 KiB, JSON 1 MiB y FIT 10 MiB más 64 KiB multipart, configurables por variables de servidor. FIT permanece alineado con `MAX_FIT_BYTES`.

## Superficies

| Módulo | Rutas y capacidades |
| --- | --- |
| Pública | `/`, `/login`, `/activate`, `/password-reset`, `/offline`, `/privacy`, `/terms`, `/support`, `/guide/fit` |
| Coach | `/coach`, `/coach/athletes`, calendario/perfil/actividades por atleta autorizado, `/coach/review`, `/coach/recommendations`, `/coach/groups`, `/coach/templates`, `/coach/copilot` |
| Atleta | `/athlete/today`, `/athlete/week`, detalle de workout, `/athlete/check-in`, molestias/alta, `/athlete/profile`, `/athlete/activities` y detalle, `/athlete/connections`, `/athlete/assistant` |
| Ajustes | `/settings/account`, `/settings/notifications`, `/settings/privacy`, `/settings/data`, `/settings/commercial` |
| Administración | `/admin/operations` y comercial con selectores de entidades autorizadas; capacidades restringidas en servidor |

Historial/detalle/vinculación y comparación consumen API, con paginación y estados de insuficiencia/calidad. Perfil/competencias, evolución de molestias, grupos/plantillas y propuestas conservan versiones y permisos. El panel de escenarios precompetencia/costos agregados y reminders está en cierre de integración; no darlo por aceptado sin su evidencia final.

`AssistantWorkspace` conecta ambos chats al API: conversaciones persistidas, fuentes/citas, previews/confirmaciones, request_key, streaming/cancelación y uso. El proveedor por defecto sigue `simulated`, indicado como tal; el adaptador Vertex existe pero no se ha evaluado con un proveedor real. El servidor revalida todos los atletas usados en contexto/historial aunque el modelo no los cite, y protege replay y exportación tras revocación.

`IntervalsConnection` gestiona OAuth/retorno, estado/sincronización y desconexión. Se precisa app aprobada y configuración servidor; no mostrar conexión real por una simulación ni inventar refresh tokens. FIT manual permanece disponible.

Notificaciones permiten preferencias/categorías, zona/silencio, consentimiento, alta y baja de dispositivos. El navegador solicita permiso sólo en la acción del usuario. Suscripción confirmada no significa recepción verificada. El service worker muestra un aviso genérico y abre `/app`; no expone métricas, nombres ni URLs privadas en pantalla bloqueada.

## Desarrollo y demo

Desde `frontend`:

```bash
npm ci
cp .env.example apps/nodo-web/.env.local
npm run dev:web
npm run typecheck
npm run test:web
npm run build:web
npm run build:lab
```

La API local usa `NODO_API_URL=http://127.0.0.1:8000/api/v1`. Esta variable pertenece al servidor Next. No publicar tokens/secretos mediante `NEXT_PUBLIC_*`. `NODO_LOCAL_DEMO=true` habilita sólo la demo local sintética; nunca exponer development públicamente.

La demo integrada desde la raíz usa `python3 ops/demo.py up` y genera credenciales fuera de Git; ver [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md). Las pruebas del navegador, TypeScript, build, API y worker del SHA final se registran en [VALIDACION_HANDOVER.md](VALIDACION_HANDOVER.md).

## Offline y dispositivos

El service worker precarga landing, fallback e icono; no cachea `/api/*`, tokens ni conversaciones. El cache de sesiones publicadas se limita al atleta/identidad, hasta 100 sesiones y 24 horas; al vencer se descarta. Logout, error de sesión, cambio de cuenta, revocación/borrado y eventos entre pestañas invalidan estado local. Estas comprobaciones están en el cierre integrado de contratos y navegador.

Una copia descargada o un dispositivo distinto desconectado no puede retirarse a distancia en el instante de revocación. La expiración acota la copia offline y el servidor vuelve a comprobar permisos al reconectar. Emulación de navegador no sustituye Safari iOS/Chrome Android físicos ni recepción Push.

## Conexión preparada para Cloud Run

Terraform prepara `NODO_API_URL` con `/api/v1` y `NODO_CLOUD_RUN_AUDIENCE` con la raíz de API. El BFF obtiene identidad desde metadata y usa `X-Serverless-Authorization`; `Authorization` conserva la sesión NODO. La API queda privada con `roles/run.invoker` para la PWA. Esto tiene pruebas de transporte local, pero requiere verificación posterior en Cloud por Josué. No ejecutar despliegue desde esta entrega.

Guía funcional: [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md). Trazabilidad: [MATRIZ_REQUISITOS.md](MATRIZ_REQUISITOS.md). Restricciones y recepción: [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md).

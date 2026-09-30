# Frontend vigente: PWA unificada

Actualizado: 29 de septiembre de 2026.

El producto desplegable es `frontend/apps/nodo-web`: una PWA Next.js responsive con módulos de coach, atleta y ajustes. `nodo-lab` y `nodo-mobile` permanecen como referencias anteriores y no son el objetivo de producción.

El workspace activo instala `nodo-web`, `nodo-lab` y los paquetes compartidos. Expo (`nodo-mobile`) está congelado y excluido de la instalación/CI activo según ADR 0003; su carpeta e historial se conservan como referencia. Reactivar ese cliente exigiría revisar sus dependencias y seguridad por separado. No se fuerza un override ESM incompatible para ocultar las alertas de su cadena antigua.

## Arquitectura de sesión

- El navegador llama rutas same-origin de Next.
- El BFF llama FastAPI con el access token.
- Access y refresh viven en cookies `httpOnly`, `SameSite=Lax`.
- El proxy protege `/app`, `/coach`, `/athlete` y `/settings`.
- Logout borra cookies, storage y cache autenticada.

## Superficies

### Públicas

- `/`: landing.
- `/login`: acceso.
- `/activate`: activación de atleta.
- `/offline`, `/privacy`, `/terms`, `/support`.

### Coach

- `/coach`: centro de mando.
- `/coach/athletes`: equipo e invitación.
- `/coach/athletes/{id}/calendar`: bloques, editor y publicación.
- `/coach/athletes/{id}/profile`: perfil deportivo.
- `/coach/review`: revisión.
- `/coach/recommendations`: propuestas.
- `/coach/groups`: grupos.
- `/coach/templates`: plantillas.
- `/coach/copilot`: simulación local; no usa modelo real.

### Atleta

- `/athlete/today`, `/week` y `/workouts/{id}`.
- `/athlete/check-in`.
- `/athlete/complaints` y `/complaints/new`.
- `/athlete/connections`: simulación Intervals.icu y carga FIT.
- `/athlete/profile`.

### Ajustes

- cuenta, notificaciones, privacidad, datos y operación comercial.
- Notificaciones permanece como capacidad no habilitada.

## Desarrollo

```bash
cd frontend
npm install
NODO_API_URL=http://127.0.0.1:8000/api/v1 npm run dev:web
npm run typecheck
npm run test:web
npm run build:web
```

En producción, `NODO_API_URL` es sólo del servidor Next. No crear variables `NEXT_PUBLIC_*` con secretos o tokens.

## Offline

El service worker precarga landing, fallback e icono. No cachea respuestas `/api/*` ni tokens. Las sesiones publicadas pueden conservarse en almacenamiento local sin credenciales; logout elimina ese estado.

## Funciones externas

- FIT manual: funcional y descrito en [GUIA_CARGA_FIT_E_INTERVALS.md](GUIA_CARGA_FIT_E_INTERVALS.md).
- Intervals.icu real: parcial, no ofrecer como conectado.
- IA real: no configurada; Copiloto está claramente marcado como simulación.
- Push: pendiente.

Ver [FUNCIONALIDADES_PRODUCTO.md](FUNCIONALIDADES_PRODUCTO.md) para la matriz completa.

## Conexión privada en Cloud Run

Terraform configura `NODO_API_URL` con `/api/v1` y `NODO_CLOUD_RUN_AUDIENCE` con la URL raíz de la API. El BFF obtiene identidad desde metadata y la envía mediante `X-Serverless-Authorization`; `Authorization` conserva la sesión NODO. La API sigue privada con `roles/run.invoker` para la PWA. Referencia: [autenticación entre servicios de Google Cloud](https://docs.cloud.google.com/run/docs/authenticating/service-to-service). Esto requiere verificación real tras desplegar.
## Protección de escrituras BFF

Login, activación, recuperación, logout y escrituras del proxy requieren el `Origin` exacto de la PWA. En Cloud Run configurar `NODO_APP_ORIGIN` con su URL HTTPS canónica en `pwa_env`; no tomar headers de host externos como autorización. Un origen ausente o ajeno se rechaza antes del backend.

La lectura del cuerpo es incremental y acotada aun sin `Content-Length`: sesión 16 KiB, JSON 1 MiB, archivo FIT 10 MiB más 64 KiB de framing multipart. Los límites `NODO_BFF_SESSION_MAX_BYTES`, `NODO_BFF_JSON_MAX_BYTES` y `NODO_BFF_FIT_MAX_BYTES` son configurables; el límite FIT debe permanecer alineado con `MAX_FIT_BYTES` del backend. Estas variables son de servidor y no se publican al cliente.

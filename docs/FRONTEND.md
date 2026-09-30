# Frontend vigente: PWA unificada

Actualizado: 20 de septiembre de 2026.

El producto desplegable es `frontend/apps/nodo-web`: una PWA Next.js responsive con módulos de coach, atleta y ajustes. `nodo-lab` y `nodo-mobile` permanecen como referencias anteriores y no son el objetivo de producción.

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

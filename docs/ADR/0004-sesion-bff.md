# ADR 0004: la sesión vive en una cookie httpOnly emitida por el servidor de Next

**Estado:** aceptada el 14 de septiembre de 2026. Se implementa en la fase F2 de `../PLAN_EJECUCION.md`. Todavía no está construida.

## Contexto

Hoy el prototipo de NODO Lab guarda el par de tokens opacos en `sessionStorage` y los adjunta desde el navegador (`frontend/apps/nodo-lab/src/app/page.tsx`). Cualquier script que se ejecute en la página —una dependencia comprometida, una extensión, un XSS— puede leerlos. Además, cada pantalla resuelve por su cuenta cuándo renovar el token, así que dos pestañas pueden rotar el refresh token a la vez y dejarse fuera mutuamente.

El backend ya emite tokens **opacos** revocables con rotación de refresh (`app/core/security.py`), lo que es la mitad buena del problema: no hay nada que descifrar en el cliente y una sesión se puede cortar del lado del servidor.

## Decisión

La PWA del ADR 0003 actúa como **BFF** (backend for frontend) de su propia sesión.

- Los route handlers de Next bajo `/api/session/*` (login, refresh, logout, me) son los únicos que hablan con `/api/v1/auth/*`.
- El token viaja al navegador en una cookie `httpOnly`, `Secure`, `SameSite=Lax`, con `Path=/`. El JavaScript del navegador nunca lo ve.
- La renovación ocurre en el servidor de Next: ante un `401` de la API, renueva una vez y repite la petición original. Si el refresh falla, borra la cookie y devuelve `401` al cliente.
- El middleware protege rutas por capacidad usando la sesión resuelta en el servidor.
- `sessionStorage` y `localStorage` dejan de contener tokens. Pueden seguir guardando preferencias locales sin valor de acceso.

La autorización de datos sigue siendo del servidor de la API. El BFF no decide quién ve a qué atleta; sólo evita que el token quede expuesto y centraliza la renovación.

## Consecuencias

- La PWA necesita un servidor Node en ejecución (no exportación estática). Eso ya era cierto por el App Router.
- `SameSite=Lax` implica que la API y la PWA se sirven bajo el mismo sitio en producción; si terminan en dominios distintos habrá que revisar CORS y la política de cookies antes del piloto, no después.
- En desarrollo `Secure` debe poder apagarse (`SESSION_COOKIE_SECURE=false`) sin que quede apagado en ningún entorno compartido.
- Criterio de verificación de F2: el token no aparece en `localStorage`, ni en `sessionStorage`, ni en el HTML servido. Se prueba con un e2e, no con una revisión a ojo.
- El `api-client` compartido pierde la responsabilidad de guardar tokens; conserva tipos y rutas.

## Alternativas descartadas

- **Seguir con `sessionStorage`.** Es lo que hay y funciona en el prototipo, pero expone el token a cualquier script de la página y multiplica las estrategias de renovación.
- **JWT con expiración corta en memoria.** Evita el almacenamiento persistente, pero pierde la sesión en cada recarga y obliga a cambiar el modelo de tokens opacos revocables que el backend ya implementa y que permite cortar una sesión de verdad.

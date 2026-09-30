# Frontend de NODO

## PWA unificada

`apps/nodo-web` es la nueva superficie de producto para atleta y entrenador. Usa una sesión BFF con cookies `httpOnly`; el navegador consume la API únicamente mediante rutas same-origin de Next.

```bash
npm install
cp .env.example apps/nodo-web/.env.local
npm run dev:web
npm run typecheck
npm run test:web
npm run build:web
```

La aplicación conserva estados honestos para contratos que todavía no existen. Esas pantallas no guardan fixtures ni representan datos sintéticos como reales. `apps/nodo-lab` y `apps/nodo-mobile` son referencias anteriores; el objetivo de despliegue es `apps/nodo-web`.

Este workspace conserva las dos aplicaciones anteriores para consulta:

- `apps/nodo-lab`: web para entrenadores, con calendario, atletas y planeación.
- `apps/nodo-mobile`: app Expo para atletas, con el entrenamiento del día, check-in y recuperación.

Los contratos HTTP y los tipos comunes viven en `packages/api-client`. No se comparte UI entre web y móvil: cada experiencia conserva controles y navegación apropiados para su dispositivo.

## Primer arranque de la PWA

1. Ejecutar `npm install` desde este directorio.
2. Definir `NODO_API_URL=http://127.0.0.1:8000/api/v1`.
3. Ejecutar `npm run dev:web`.
4. Abrir `http://127.0.0.1:3000`.

La PWA se prueba desde el navegador móvil contra una URL HTTPS de staging; no exponer una API local ni credenciales a internet para simular producción.

Inventario funcional: [`docs/FUNCIONALIDADES_PRODUCTO.md`](../docs/FUNCIONALIDADES_PRODUCTO.md). Guía FIT e Intervals: [`docs/GUIA_CARGA_FIT_E_INTERVALS.md`](../docs/GUIA_CARGA_FIT_E_INTERVALS.md).

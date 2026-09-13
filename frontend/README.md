# Frontend de NODO

Este workspace reúne dos aplicaciones que consumen la misma API:

- `apps/nodo-lab`: web para entrenadores, con calendario, atletas y planeación.
- `apps/nodo-mobile`: app Expo para atletas, con el entrenamiento del día, check-in y recuperación.

Los contratos HTTP y los tipos comunes viven en `packages/api-client`. No se comparte UI entre web y móvil: cada experiencia conserva controles y navegación apropiados para su dispositivo.

## Primer arranque

1. Copiar `.env.example` como `.env.local` en cada app que se vaya a ejecutar y ajustar la URL de la API.
2. Ejecutar `npm install` desde este directorio.
3. Para NODO Lab: `npm run dev:lab`.
4. Para NODO móvil: `npm run dev:mobile` y abrir el QR con Expo Go durante el prototipo.

En un teléfono físico, `localhost` apunta al propio teléfono. Para Expo, usar la IP LAN de la laptop en `EXPO_PUBLIC_NODO_API_URL` y permitir el puerto de la API en el firewall local.

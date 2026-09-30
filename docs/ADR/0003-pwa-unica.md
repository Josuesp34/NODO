# ADR 0003: una sola PWA en lugar de app web y app móvil

**Estado:** aceptada el 14 de septiembre de 2026. Se implementa en la fase F2 de `../PLAN_EJECUCION.md`. Todavía no está construida.

## Contexto

El workspace actual tiene dos aplicaciones: `frontend/apps/nodo-lab` (Next.js, entrenador) y `frontend/apps/nodo-mobile` (Expo/React Native, atleta). El ADR 0001 aceptó que una persona puede ser atleta y entrenadora a la vez. Con dos aplicaciones, esa persona tendría que instalar dos cosas para ser lo que es, iniciar sesión dos veces y mantener dos estados de sesión distintos.

Mantener dos superficies también duplica el costo de cada pantalla nueva del plan: calendario, editor de sesiones, check-in, molestias y bandeja de revisión tendrían dos implementaciones y dos formas de equivocarse con permisos.

## Decisión

Se sustituyen las dos aplicaciones por **una sola PWA**: `frontend/apps/nodo-web`, Next.js 16 con App Router.

- Route groups `(coach)` y `(atleta)` sobre una sesión compartida.
- El layout raíz resuelve las capacidades de la persona autenticada y habilita los módulos correspondientes. Una persona con ambas capacidades ve las dos zonas sin cambiar de cuenta ni de aplicación.
- UI con Tailwind v4 y componentes propios. Sin librería de componentes pesada: el calendario y el editor de pasos son a medida de todos modos.
- `frontend/packages/api-client` se conserva como contrato REST compartido.
- `frontend/apps/nodo-mobile` se congela en la rama `archive/expo` y sale del workspace. No se borra su historial.
- Instalable: manifest, iconos, `theme-color` y service worker con caché de la vista "hoy" para consulta sin señal.

La autorización sigue resolviéndose en el servidor. Los route groups y el middleware sólo deciden qué se dibuja; nunca sustituyen la verificación de la API.

## Consecuencias

- Se pierde HealthKit y la notificación push nativa de iOS. Si HealthKit vuelve como requisito, se envuelve la **misma** PWA en Capacitor en lugar de reabrir una app React Native.
- Web push funciona en Android y en iOS sólo con la PWA instalada. La fase F13 debe degradar con claridad cuando no esté disponible, no prometer notificación.
- `npm run build:lab` y `dev:mobile` se reemplazan por los scripts de `nodo-web` cuando F2 aterrice. Hasta entonces `nodo-lab` sigue siendo la app que compila el CI.
- La documentación deja de hablar de "app web" y "app móvil" como productos separados: NODO es la plataforma y NODO Lab es el módulo de entrenador dentro de ella.

## Alternativas descartadas

- **Mantener las dos apps.** Coherente con el estado actual del repo, pero contradice el ADR 0001 y duplica cada pantalla del plan.
- **React Native Web para unificar desde el móvil.** Obligaría a renunciar al App Router y a reescribir el calendario del entrenador, que es la pantalla más pesada del producto y la que menos se parece a una vista móvil.
- **Capacitor desde el principio.** Añade una cadena de compilación y una tienda antes de tener producto que instalar. Queda disponible como paso posterior sin cambiar el código de la PWA.

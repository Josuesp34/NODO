# Pendientes del MVP de NODO

Actualizado: 14 de septiembre de 2026.

Este documento describe qué falta para que NODO pueda probarse de extremo a extremo con un entrenador y un primer atleta. No amplía el contrato actual de la API ni convierte capacidades futuras en funcionalidades implementadas.

## Estado resumido

| Área | Estado | Nota |
|---|---|---|
| Landing pública | Listo | Entrada visual en NODO Lab web. |
| Registro local de entrenador | Listo para desarrollo | Requiere `ALLOW_COACH_REGISTRATION=true`; no es registro público. |
| Login, refresh, logout y sesión actual | Backend listo; refresh de cliente por consolidar | La API rota refresh tokens. Las pantallas todavía deben compartir una única estrategia de renovación. |
| Roles y aislamiento entrenador-atleta | Listo para MVP | El servidor valida `coach`/`athlete` y la relación de propiedad. |
| Invitación de atleta | Listo para desarrollo | El token se muestra temporalmente; todavía no hay correo ni entrega verificada. |
| Activación de atleta web | Listo para desarrollo | `/activate` crea la sesión del atleta. |
| NODO web atleta | Parcial | Shell autenticado listo; falta consumir sesiones publicadas. |
| NODO móvil atleta | Pendiente | La pantalla actual es un placeholder; falta autenticación y almacenamiento seguro. |
| NODO Lab: atletas | Listo | Lista real desde `GET /auth/athletes`. |
| NODO Lab: bloques y sesiones | Parcial funcional | Crear bloques, crear borradores, calendario y publicar. Falta edición completa del borrador existente. |
| Integridad del esquema | Verificada | Migraciones alineadas; `alembic check` sin operaciones pendientes. |
| Recuperación, molestias y conectores | Fuera del MVP de prueba | No existen endpoints; no simular datos. |

## Ruta crítica antes de probar con un atleta

```text
Crear coach local
  → iniciar sesión
  → invitar atleta
  → copiar token de desarrollo
  → activar atleta
  → crear bloque
  → crear sesión estructurada
  → guardar borrador
  → publicar
  → atleta consulta su sesión publicada
```

El último paso es el bloqueo principal pendiente: el backend ya permite que el atleta consulte sus sesiones, pero las experiencias web y móvil todavía no las presentan como entrenamiento del día.

## Trabajo pendiente por capa

### API y dominio

- Consolidar el contrato de sesión del cliente para renovar el access token una sola vez tras un `401` y repetir la petición original.
- Mantener las validaciones de rol y relación en backend; la UI no sustituye autorización.
- Añadir pruebas de regresión para publicación repetida, edición de publicados, conflicto `409` y rango de bloques.
- Definir idempotencia para invitaciones e importación FIT antes de conectar fuentes externas.
- Mantener eventos y trabajos asíncronos fuera de la petición HTTP cuando se agreguen notificaciones o ingesta.

### NODO Lab web

- Permitir abrir un borrador existente, editarlo y manejar conflicto `409` con refresco y decisión explícita.
- Añadir selección de objetivos de ritmo, potencia, frecuencia cardiaca y RPE en el editor.
- Mostrar el detalle de bloques y sesiones sin representar métricas que aún no provienen del backend.
- Añadir pruebas de UI para invitación, errores de autorización, validación `422` y conflicto `409`.

### NODO web atleta

- Consultar `GET /athletes/{athlete_id}/workouts` usando el `athlete_id` de la identidad autenticada.
- Mostrar sólo sesiones `published` del propio atleta.
- Construir entrenamiento del día, calendario y estado vacío.
- Resolver zona horaria del atleta al agrupar sesiones por fecha local.
- Añadir logout y estados de sesión caducada.

### NODO móvil

- Activación por invitación y login.
- Guardar access/refresh token en almacenamiento seguro de Expo, no en `AsyncStorage` ni logs.
- Renovar sesión una vez tras `401` y cerrar sesión cuando el refresh sea inválido.
- Consumir sesiones publicadas del propio atleta.
- Añadir navegación inicial y estado vacío.
- No crear check-in, recuperación o molestias hasta tener contrato backend.

### Datos, esquema y operación

- Ejecutar `alembic upgrade head` en cada entorno antes de probar cambios de modelo.
- Ejecutar `alembic check` para detectar deriva entre modelos y migraciones.
- No usar `create_all` como mecanismo de actualización.
- Mantener `coach_id`, `athlete_id`, versión y estado como invariantes del servidor.
- No subir `.env`, tokens, datos reales, archivos FIT, capturas ni logs.

## Fuera del alcance inmediato

No bloquear el primer piloto técnico con estas áreas:

- Garmin, Apple Health, Health Connect, Polar, COROS u otros conectores.
- Recuperación, sueño, HRV, FC de reposo o estrés.
- Reportes y revisión de molestias.
- Notificaciones y correo de invitación.
- Equipos con varios entrenadores.
- Copiloto de IA, recomendaciones automáticas o cambios automáticos del plan.
- Camunda u otro orquestador; primero deben estabilizarse los casos de uso, eventos e idempotencia.

## Criterios para la primera prueba con un amigo atleta

- El coach puede crear una cuenta local y entrar.
- El coach puede invitar un atleta desde la interfaz.
- El atleta puede activar su cuenta con un token de desarrollo.
- El coach puede crear un bloque y una sesión estructurada.
- El servidor rechaza una sesión fuera del bloque y una publicación con versión obsoleta.
- El coach puede publicar la sesión.
- El atleta ve únicamente sus sesiones publicadas.
- El estado vacío aparece cuando no hay sesión publicada.
- Backend, typecheck, build y migraciones están verdes.

## Validación vigente

```powershell
cd backend/api
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/alembic.exe -c alembic.ini check

cd ../../frontend
npm run typecheck
npm run build:lab
```

La última validación local registrada: 39 pruebas backend correctas, typecheck de NODO Lab y NODO Mobile correcto, build de NODO Lab correcto y `alembic check` sin operaciones nuevas.

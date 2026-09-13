# Frontend: NODO y NODO Lab

Se trabajará en un solo repositorio y dos aplicaciones: NODO Lab web para el entrenador y NODO móvil con Expo/React Native para el atleta. Ambas usan la misma API FastAPI y las mismas reglas de autorización; la interfaz no se comparte porque sus tareas y tamaños de pantalla son distintos.

## Primer corte de producto

NODO Lab implementará autenticación de entrenador, lista de atletas, calendario por atleta y editor/publicación de sesiones. NODO móvil implementará activación, inicio de sesión, entrenamiento del día, check-in de recuperación y consulta de sesiones publicadas.

El cliente compartido vive en `frontend/packages/api-client`. Debe reflejar `docs/API_NODO.md`; al añadir un endpoint al backend, se actualiza su tipo y un consumidor antes de integrarlo a la interfaz.

## Datos de reloj y salud

La primera interfaz no lee Apple Health, Health Connect ni proveedores de reloj directamente. Esa integración llegará como adaptadores nativos de NODO móvil y sincronizará al backend con consentimiento explícito. Así NODO Lab sólo ve datos consolidados y autorizados, y la lógica clínica/deportiva permanece en el backend.

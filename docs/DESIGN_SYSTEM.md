# NODO — DesignContext y sistema visual

Estado: contrato activo para la PWA única. Última actualización: 20-09-2026.

## Trabajo principal

NODO ayuda a un entrenador de resistencia a decidir qué necesita atención, convertir su criterio en
sesiones estructuradas y mantener el control antes de publicar cualquier cambio. Para el atleta,
NODO convierte el plan en una instrucción clara para hoy y recoge el contexto que el reloj no ve.

- Audiencia principal: coaches independientes y responsables de equipos de resistencia en LATAM.
- Audiencia secundaria: atletas adultos que usan el teléfono antes, durante y después de entrenar.
- Acción comercial: solicitar acceso al piloto. No abrir registro público ni fijar precio sin decisión.
- Acción coach: revisar → editar → publicar → comparar → decidir.
- Acción atleta: entender → ejecutar → reportar → dar seguimiento.

## Locks

1. Una sola PWA `apps/nodo-web`; NODO Lab es el módulo coach, no otro producto.
2. Una identidad puede reunir capacidades de coach y atleta sin cambiar de sesión.
3. La sesión vive en cookie `httpOnly`; ningún token llega a JavaScript, HTML, URL o logs.
4. La UI representa `401`, `403`, `404`, `409` y `422`; ocultar un control no sustituye permisos.
5. La IA crea borradores y propuestas. Nunca publica ni aplica cambios sin confirmación autorizada.
6. No simular conexión, frescura, salud, pago o disponibilidad. Todo estado visible proviene del sistema.
7. Español operativo. El inglés queda como acento de marca corto, no como navegación principal.
8. No hacer afirmaciones médicas ni prometer prevención, retorno deportivo o rendimiento exacto.

## ADN visual

- Fondo: `#101110`.
- Superficie elevada: `#171916`.
- Texto principal: `#F2F0E8`.
- Texto secundario: `#A8ADA1`, siempre con contraste AA.
- Acción/selección: lima `#D7FF3F`.
- Atención/conflicto: coral `#FF734F`; nunca como decoración abundante.
- Bordes: gris oliva de bajo contraste, visibles sin competir con el contenido.
- Retícula técnica, líneas y nodos representan relaciones reales entre plan, ejecución, sensación y decisión.

La paleta, retícula y tono editorial forman el patrón observado que debe preservar continuidad. Si el
logo se retirara, la relación visual plan → ejecución → evidencia → decisión todavía debe identificar
a NODO; los círculos decorativos por sí solos no pasan el Brand-Off test.

## Jerarquía

- Landing: un solo mensaje primario; titulares de 72–144 px según viewport.
- Producto: títulos de página de 32–48 px; sección 24–32 px; cuerpo 16–18 px.
- Metadata: mínimo 12–13 px. Nada operativo a 8–10 px.
- Cuerpo de lectura: 45–75 caracteres por línea y altura 1.45–1.6.
- Lima sólo para acción primaria o selección; coral para conflicto o atención.
- El contenido operativo aparece antes del pliegue; los héroes grandes se reservan para páginas públicas.

## Estructura de experiencia

### Coach

Rail lateral compacto, topbar contextual y área de trabajo amplia. La primera vista prioriza bandeja,
atletas que requieren atención y calendario. Calendario mensual/semanal en escritorio; agenda clara
en móvil. Ningún día pierde una segunda sesión.

### Atleta

Lectura centrada de 680–760 px y navegación inferior: Hoy, Semana, Reportar y Perfil. “Hoy” muestra
una sesión real, sus pasos y fuentes; nunca una tarjeta-promesa. Check-in y molestia funcionan aun sin
reloj.

### Estados

Todo módulo incluye carga, vacío, error, permiso, conflicto, offline y reintento. `409` presenta la
versión remota y obliga a elegir entre recargar o conservar un borrador local; no reintenta a ciegas.

## Componentes base

`AppShell`, `CapabilitySwitcher`, `PageHeader`, `Button`, `Field`, `Select`, `Textarea`,
`StatusBadge`, `SourceBadge`, `FreshnessBadge`, `Dialog`, `Drawer`, `Toast`, `Skeleton`,
`EmptyState`, `ErrorState`, `OfflineBanner`, `ConflictDialog` y `PermissionState`.

Las superficies de planificación, revisión, bienestar, copiloto y grupos se construyen con estos
componentes y tokens; no duplican estilos por ruta.

## Accesibilidad y QA

- Contraste mínimo 4.5:1 para cuerpo y 3:1 para texto grande; objetivo 7:1 en lectura prolongada.
- Controles táctiles de al menos 44 × 44 px, foco visible y navegación completa por teclado.
- Etiquetas explícitas, mensajes asociados al campo y anuncios `aria-live` para resultados asíncronos.
- No depender sólo de color; cada estado usa texto e iconografía coherente.
- Verificar visualmente 390, 768, 1280 y 1440 px, con textos largos, datos vacíos y errores.
- La aprobación final se hace sobre el producto renderizado, no sobre este documento.

## Landing vendible

Orden: promesa específica → recorrido real → diferenciador → control/seguridad → límites → FAQ →
CTA “Solicitar acceso al piloto”. Las capturas son reales o están rotuladas como demo. No se publican
testimonios, precios, integraciones o métricas sin evidencia.

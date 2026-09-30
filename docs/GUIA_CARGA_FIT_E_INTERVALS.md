# Guía de usuario: cargar un archivo FIT y conectar datos

Actualizado: 20 de septiembre de 2026.

## Cuándo usar un archivo FIT

Un archivo `.fit` contiene una actividad registrada por un reloj, ciclocomputador o aplicación deportiva. En el piloto de NODO es la vía funcional para añadir una actividad cuando la sincronización automática no está disponible.

No envíes el archivo por correo al equipo ni lo subas a carpetas compartidas. Cárgalo directamente desde tu cuenta de NODO.

## Antes de empezar

- Inicia sesión con la cuenta del atleta dueño de la actividad.
- Exporta la actividad original en formato `.fit` desde la plataforma de tu dispositivo.
- Usa un archivo de una sola sesión y de máximo 10 MiB.
- No renombres otro formato como `.fit`; NODO valida su contenido.
- Fuera del entorno de desarrollo, autoriza primero el consentimiento de procesamiento de datos en **Ajustes → Privacidad**.

## Carga desde la PWA

1. Abre **Mi NODO → Conexiones**.
2. En **Cargar archivo FIT**, pulsa el selector de archivo.
3. Elige el `.fit` original de la actividad correcta.
4. Verifica que estás en la cuenta del atleta correspondiente.
5. Pulsa **Cargar de forma segura** y espera la confirmación.

NODO asocia la actividad al usuario autenticado, calcula un hash para impedir duplicados, decodifica laps y telemetría, y encola el recálculo de carga diaria.

## Cómo interpretar el resultado

| Mensaje/estado | Significado | Qué hacer |
|---|---|---|
| `imported` | La actividad se guardó correctamente | No vuelvas a cargar el mismo archivo |
| `already_imported` | El mismo archivo ya estaba asociado al atleta | No se creó un duplicado |
| `trimp_status=calculated` | Había duración, FC y perfil suficientes | Revisa el valor dentro del contexto del plan |
| `trimp_status=insufficient_inputs` | Faltó perfil o resumen cardiaco suficiente | La actividad sigue guardada; completa el perfil si aplica |
| `CONSENT_REQUIRED` | Falta consentimiento vigente | Autoriza en **Ajustes → Privacidad** |
| Archivo inválido o multisesión | NODO no puede procesarlo con seguridad | Exporta una sola actividad original |
| Archivo demasiado grande | Supera 10 MiB | Exporta la actividad sin adjuntos o solicita soporte |

NODO conserva sensores ausentes como “sin dato”; nunca los convierte en cero. La importación no es un diagnóstico ni una garantía de rendimiento.

## Privacidad y soporte

- Carga sólo actividades propias o de un atleta que te haya autorizado.
- No publiques archivos FIT, capturas con datos de salud ni códigos de invitación.
- Si una importación falla, conserva el archivo original y reporta fecha, dispositivo y mensaje visible; no compartas tokens ni contraseñas.

## Estado de Intervals.icu

La pantalla muestra el estado real de la integración y mantiene una herramienta de prueba durante el desarrollo:

- **Probar simulación:** guarda un estado simulado sin contactar a Intervals.icu ni compartir credenciales.
- **Conexión real pendiente:** está deshabilitada porque esta versión no completa OAuth, sincronización ni webhooks. La API también rechaza el modo real si faltan credenciales servidoras con `INTERVALS_CONFIGURATION_REQUIRED`.

No interpretes `simulated` o `authorization_pending` como una sincronización activa. Hasta que NODO muestre una confirmación real de proveedor, última sincronización y opción de revocación verificada, usa la carga FIT.

La integración real necesita todavía registro y aprobación de la aplicación, consentimiento de términos, OAuth con anti-CSRF, cifrado del token, callback, revocación remota, webhooks, backfill y pruebas con una cuenta autorizada. La documentación vigente del proveedor no publica un refresh token: si la autorización deja de funcionar, el producto debe pedir reconexión. Ninguna credencial debe pegarse en la PWA o guardarse en Git.

## Flujo futuro esperado de Intervals.icu

Cuando la integración esté aprobada, el usuario hará:

1. **Mi NODO → Conexiones → Conectar Intervals.icu**.
2. NODO abrirá la autorización oficial de Intervals.icu.
3. El usuario aprobará los scopes visibles.
4. NODO confirmará **Conectado**, fecha de última sincronización y alcance.
5. El usuario podrá revocar sin borrar actividades ya importadas.

Ese flujo es un criterio de aceptación, no una función disponible hoy.

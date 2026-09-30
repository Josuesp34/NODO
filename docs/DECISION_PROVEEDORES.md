# Comparación de proveedores para NODO

Actualizado: 23-09-2026. **Decisión deportiva aceptada por Brandon: Intervals.icu como sincronización principal y FIT como respaldo permanente.** La elección no equivale a integración, compra ni autorización OAuth. Primeros atletas: Garmin y marcas mixtas. La elección de proveedor de IA continúa pendiente.

## Datos deportivos

| Opción | Ventaja para NODO | Límite o compuerta |
|---|---|---|
| [Intervals.icu](https://www.intervals.icu/features/open-api/) | API abierta con OAuth, actividades, bienestar, sesiones planificadas y webhooks; encaja con varias marcas si el atleta ya sincroniza allí. | Requiere app OAuth aprobada, cuenta del atleta en Intervals y pruebas de permisos/datos reales. El código de NODO sólo simula conexión hoy. |
| [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/overview/) | API directa de actividades, salud y planes para la mayoría Garmin. | Sólo Garmin; solicitud de acceso empresarial. [El FAQ](https://developer.garmin.com/gc-developer-program/program-faq/) indica que el acceso base no tiene cuota de licencia, pero algunas métricas comerciales sí pueden exigir pago o compra mínima. |
| [Polar AccessLink](https://www.polar.com/accesslink-api/) | OAuth, ejercicios FIT, sueño y métricas Polar. | Sólo Polar; sería segundo conector, no sustituye a Garmin. |
| [Terra](https://tryterra.co/pricing) | Unifica muchas marcas y webhooks en un esquema. | Desde USD 399/mes anual o USD 499/mes mensual, antes de extras; excede el presupuesto inicial propuesto. |
| [Strava](https://developers.strava.com/docs/getting-started/) | Popular y multimarcas. | Una app nueva empieza en modo de un usuario y requiere revisión para escalar. [Su acuerdo API 2026](https://www.strava.com/legal/api) restringe mostrar datos de un atleta a otra persona; el caso coach de NODO requiere autorización legal explícita del proveedor. No elegirlo como fuente principal sin esa confirmación. |

Apple [HealthKit](https://developer.apple.com/documentation/xcode/configuring-healthkit-access) y Android [Health Connect](https://developer.android.com/health-and-fitness/health-connect) son rutas para una app nativa futura; la PWA actual no accede directamente a esas tiendas de datos.

**Implementación acordada:** Intervals primero para marcas mixtas + FIT permanente. Garmin directo después sólo si los primeros coaches necesitan datos no disponibles en Intervals o reducir fricción. Terra no cabe en el presupuesto inicial. Antes del GO real, confirmar cuántos atletas ya usan Intervals, sus fuentes Garmin/otras, términos de acceso para coach y aprobación OAuth.

## Modelos de IA

Vertex AI (ahora dentro de Agent Platform) es la capa de Google Cloud para consumir Gemini con IAM, facturación y observabilidad del proyecto; **no es un modelo diferente**. NODO sólo tiene un proveedor `simulated`, sin inferencia real ni pruebas con datos de atletas.

| Ruta | Ejemplo para prueba inicial | Precio público de texto por 1M tokens de entrada/salida* | Consideración |
|---|---|---:|---|
| [Google Cloud / Gemini](https://cloud.google.com/vertex-ai/generative-ai/pricing) | Gemini 3.1 Flash-Lite global | USD 0.25 / 1.50 | Misma nube prevista para NODO; verificar región, cuotas y precio efectivo en el proyecto. |
| [OpenAI API](https://developers.openai.com/api/docs/models) | GPT-6 Luna | USD 0.10 / 0.50 | Entrada económica para volumen; cuenta, facturación y datos separados de GCP. |
| [Anthropic API](https://platform.claude.com/docs/en/models/overview) | Claude Haiku 4.5 | USD 1 / 5 | Tercera referencia de calidad; costo unitario mayor en este ejemplo. |

\* Precios públicos consultados el 23-09-2026, sin descuentos, caché, herramientas, impuestos ni modalidad regional; pueden cambiar. No predicen calidad ni costo por conversación. La [documentación oficial de OpenAI](https://developers.openai.com/api/docs/guides/model-selection) recomienda comparar modelos con el trabajo real y ajustar calidad, latencia y costo.

**Siguiente decisión conjunta:** correr el corpus sintético y los gates de [EVALUACIONES_LLM.md](EVALUACIONES_LLM.md) en los tres proveedores, con el mismo prompt/herramientas, techo aprobado de gasto y revisión humana. No activar un modelo real ni enviar datos de salud a terceros antes de elegir proveedor, región, contrato de datos y consentimiento. Mantener simulación y flujos manuales mientras tanto.

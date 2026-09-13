# ADR 0002: pipeline persistente para datos y recomendaciones

**Estado:** aceptada como requisito antes de sincronizaciones reales.

## Decisión

Las cargas FIT, webhooks de dispositivos, recálculos y tareas de IA no se ejecutarán dentro de la solicitud HTTP. Cada entrada se registrará de forma idempotente, se pondrá en una cola persistente y tendrá estado, reintentos y trazabilidad.

```text
origen autenticado → registro de recepción → cola persistente → worker
→ normalización/deduplicación → datos crudos y consolidados
→ recálculo de estado → propuesta revisable → decisión del entrenador
```

## Reglas

- Actividades y observaciones conservan proveedor, identificador externo, periodo observado, zona horaria, calidad y fecha de recepción.
- Reintentar no puede duplicar una actividad ni cambiar silenciosamente datos históricos.
- El worker debe sobrevivir reinicios y enviar fallos repetidos a una bandeja de revisión.
- La IA sólo crea borradores validados; no publica sesiones ni cambia métricas directamente.

El endpoint FIT actual sigue siendo un prototipo local y no forma parte de este pipeline todavía.

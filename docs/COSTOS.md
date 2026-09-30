# Costos y guardas financieras

Estado: **modelo de costos listo para cotizar; sin precios, créditos ni facturación verificados**.

No se fijan cifras desde documentación estática porque precios, cuotas, región y créditos cambian. Antes del primer plan, una persona autorizada usa la calculadora oficial y conserva una captura o export privado con fecha.

## Variables a cotizar

| Componente | Driver principal | Guarda inicial |
|---|---|---|
| Cloud Run PWA/API | CPU, memoria, solicitudes, instancias mínimas | staging escala a cero; prod se dimensiona con carga |
| Worker pool | instancias y tiempo activo | desactivado hasta existir trabajo persistente probado |
| Cloud SQL | tier, disco, HA, backups/PITR, egress | tier variable; autosize; sin IP pública |
| Storage | GB-mes, operaciones, retención y egress | lifecycle por tipo; no borrar por alerta |
| Artifact Registry | almacenamiento y egress | retener digests de releases/rollback |
| Logging/Monitoring | volumen y retención | no registrar cuerpos/PII; ajustar exclusiones seguras |
| IA | modelo, tokens, caché, evaluaciones | límites por petición/usuario y presupuesto separado |
| Terceros | correo, dominio, intervals.icu | cotizar fuera de créditos GCP |

## Proceso de aprobación

1. Confirmar proyectos, región, moneda, impuestos, créditos elegibles y fecha de vencimiento.
2. Estimar bruto sin créditos y neto con créditos verificables por separado.
3. Confirmar que la suma cabe en los límites humanos vigentes del plan maestro.
4. Definir `monthly_budget_units` y canales; revisar el `terraform plan`.
5. Revisar semanalmente durante piloto y después mensualmente.

Las alertas configurables son 25/50/75/90/100 %. Un budget no es un límite duro y no garantiza cero sobrecostos. No apagar producción, borrar datos o deshabilitar billing automáticamente al cruzar un umbral.

# Avisos, escenarios y costos de IA

Paquete de cierre B6/F13/F14. Verificación local sobre PostgreSQL 16, Python 3.12 y Next 16.3.8; no despliegue ni recursos cloud.

## Avisos y recordatorios

`app.services.product_notifications.queue_product_event` persiste un Job `product_notification` por destinatario junto con la mutación de negocio, sin bloquear a otro usuario. Su clave única resume destinatario/categoría/evento. `INSERT ON CONFLICT DO NOTHING` conserva la transacción exterior y evita duplicados incluso con dos schedulers. El payload contiene IDs, categoría, clave de evento, entidad, versión y plazo opcional; no nombres, notas ni métricas del atleta.

`dispatch_product_notification(db, job)` bloquea únicamente al destinatario. Revalida cuenta, consentimiento del atleta, rol, asignación y organización/suscripción específicas; comprueba que la fuente siga vigente. Publicación y molestias incluyen versión; propuestas requieren estado pendiente y su coach; sincronización requiere conexión con error o reconexión pendiente. Luego usa el servicio Push existente y adjunta `product_source` a los jobs `send_web_push`. El servicio de entrega vuelve a revalidar la fuente antes del transporte: locks NOWAIT en savepoint difieren contención sin gastar intentos; cuenta/consentimiento/asignación/organización se leen vigentes. El reloj se comprueba después de locks y dentro de la llamada de transporte. `cancel_user_processing` detecta los IDs de ese contexto recursivamente.

Hooks incluidos antes del commit de negocio:

- Publicación de entrenamiento: aviso `plan` al atleta.
- Reporte, empeoramiento y reapertura de molestia: aviso `review` a coaches asignados.
- Propuesta nueva: aviso `review` al coach que debe revisarla.

Integración completada en el worker y rutas:

- `dispatch_product_notification` registrado como handler.
- `schedule_workout_reminders(db)` se ejecuta y confirma antes de reclamar jobs.
- La confirmación del asistente añade el aviso de molestia en la misma transacción, con ID/versión y dedupe.
- Intervals 401 marca reconexión requerida y avisa. Un fallo terminal 5xx/timeout, tras rollback, sólo marca error/avisa si conserva claim, consentimiento, conexión/token y no hubo sincronización posterior; el episodio usa el Job ID estable. Una claim perdida revierte estado y outbox. Los FIT se conservan.

El scheduler local considera sesiones publicadas cuyo inicio cae en los próximos 60 minutos. Exige preferencias activadas, categoría `reminder` y consentimiento Web Push vigente; usa la zona horaria de la preferencia para el día de la clave. No genera alertas pasadas. Si el silencio termina después del inicio, omite el recordatorio. `valid_until` se propaga al job Push; el handler de privacidad cancela plazos vencidos, inválidos o incompatibles con el silencio antes de llamar al transporte. La recepción física HTTPS en dispositivo consentido requiere la configuración y validación operativa de Josué.

## Escenarios precompetencia

`POST /athletes/{athlete_id}/competitions/{competition_id}/scenarios`, accesible sólo al coach autorizado, compara 2–4 alternativas con una carga explícita por día durante 1–42 días, hasta la competencia inclusive. El formulario presenta dos alternativas. La competencia requiere su versión vigente; un cambio responde 409. Las cargas finitas, no negativas, comparten una única unidad TRIMP o TSS. Cambiar competencia o unidad borra las entradas para evitar conversiones implícitas.

El cálculo usa EWMA 42/7 y muestra CTL/ATL al cierre y TSB al inicio del día. El estado inicial procede exactamente del día anterior con la misma unidad y fórmula, o de una hipótesis manual con explicación. Si falta, devuelve valores de estado `null`, nunca un estado cero inventado. Cada resultado incluye sus supuestos y unidad. Son proyecciones matemáticas de cargas manuales, sin predicción de rendimiento, autorización médica, selección automática ni escritura/publicación de calendario. Las molestias abiertas producen una nota de revisión.

Pantalla: `/coach/athletes/{athlete_id}/scenarios`, enlazada desde Competencias.

## Costos y reservas

`GET /admin/commercial/ai-costs` exige administrador; `GET /account/ai-costs` devuelve únicamente la cuenta autenticada. Ambos aceptan `month=YYYY-MM-01`, interpretado en UTC. El reporte agrega `AssistantRun` una vez por usuario, incluso multirol, y separa consultas completadas, reserva de consultas en curso y reserva incierta de fallos/cancelaciones. Los importes persistidos son enteros microUSD; no consulta facturación del proveedor ni contenido conversacional.

Los contadores `AssistantBudget` de ámbitos `user` y `organization` se presentan separados, sin sumarlos entre sí. El reparto por atleta/coach activo usa denominadores actuales; no representa una fotografía histórica ni una factura individual. Tarifas, modelo, capacidades y límites visibles son configuración actual, sin atribuirlos a runs históricos. No incluye costos de infraestructura ni afirma facturación real.

Pantalla: `/settings/ai-costs`, enlazada desde Ajustes.

## Verificación reproducible

Pruebas API/domain/cola: `backend/api/tests/api/test_product_insights_notifications.py`, en SQLite y PostgreSQL. Usan datos sintéticos, esquemas aislados y transporte stub. Cubren atomicidad/rollback, dedupe, fuentes/versiones vencidas, revocación, borrado, preferencias, silencio, día local, deadline, conexión recuperada/organización suspendida, escenarios con estado faltante, autorización y costos sin doble conteo. Dos casos exclusivos PostgreSQL ejercen locks opuestos de actores y schedulers simultáneos.

```bash
cd backend/api
NODO_PRIVACY_TEST_DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@127.0.0.1:PORT/TEST_DATABASE' \
  python -m pytest -q tests/api/test_product_insights_notifications.py
```

La URL debe apuntar a PostgreSQL de prueba local. El fixture crea y elimina su propio esquema; no usa datos reales. Para repetir las 10 invariantes del worker/email en ambos motores, usar `NODO_WORKER_TEST_DATABASE_URL` y `tests/services/test_worker_claims.py`.

`frontend/e2e/insights.spec.ts` añade pruebas reales de navegador para comparar cargas explícitas sin modificar sesiones y separar costos admin/cuenta propia. Se ejecuta sobre la demo local reconstruida con el paquete integrado:

```bash
cd /ruta/al/checkout/NODO/frontend
npm run test:e2e -- e2e/insights.spec.ts
```

Hooks/guardas ya integrados. CI del corte c29a584 aprobó la suite completa PG (262 pruebas) y 39 casos de navegador, incluidos estos escenarios/costos. Locks fuente, vencimiento durante espera/transporte y fallo terminal sync tienen regresiones reales PG. Evidencia del SHA final en [VALIDACION_HANDOVER](VALIDACION_HANDOVER.md) y comprobante de release. No equivale a entrega física Push, facturación externa ni producción activa.

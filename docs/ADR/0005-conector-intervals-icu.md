# ADR 0005: intervals.icu como vía principal de datos, con carga manual de FIT como respaldo

**Estado:** aceptada el 14 de septiembre de 2026. Se implementa en la fase F6 de `../PLAN_EJECUCION.md`. Todavía no está construida y depende de una compuerta humana.

## Contexto

NODO necesita que las actividades y el bienestar diario lleguen solos. Las alternativas son integrar con cada fabricante (Garmin, COROS, Polar, Wahoo), pagar un agregador, o apoyarse en una plataforma que ya haya hecho ese trabajo.

Strava queda fuera por sus términos: restringen mostrar datos de un atleta a un tercero —su entrenador— y procesarlos con IA. Integrar a través de Strava obligaría a apagar justo lo que el producto hace.

## Decisión

Se integra **intervals.icu** como fuente principal, y se pide al atleta conectar su reloj **directo** (Garmin, COROS, Polar, Wahoo) en intervals, no vía Strava.

- OAuth 2.0 con scopes, estado anti-CSRF en el inicio y renovación de token.
- `athlete_connections` guarda los tokens **cifrados en reposo**, con la clave en variable de entorno (`PROVIDER_TOKEN_ENCRYPTION_KEY`), nunca en Git y distinta por entorno.
- Webhooks de actividad, calendario y atleta. El receptor **sólo** registra en `ingestion_events` y encola: no procesa dentro de la petición HTTP (ADR 0002).
- Backfill inicial acotado, 90 días por defecto y configurable.
- El mapeo a `activities`, `activity_laps` y `observations` conserva proveedor, identificador externo, método, unidad, periodo observado, zona horaria y calidad. Cuando `device_name` indique un dispositivo Garmin, el dato se atribuye a Garmin.
- El atleta tiene una pantalla "conectar mi reloj" con estado y revocación. El entrenador ve el estado de sincronización por atleta y un aviso cuando una conexión cae.
- La escritura de sesiones planificadas al calendario de intervals queda **detrás de una bandera apagada por defecto** (`INTERVALS_PUSH_WORKOUTS`). NODO es la fuente de verdad del plan.

**La carga manual de FIT nunca se retira.** Es el plan B permanente, no una etapa de transición.

## Compuerta humana

Registrar la aplicación OAuth en intervals.icu y entregar `client_id` y `client_secret` por un canal seguro es decisión de Brandon y Josué. La sesión de desarrollo no la cruza sola. Tampoco acepta términos de terceros en nombre del proyecto.

## Consecuencias

- Se acepta una dependencia de una plataforma pequeña, sin SLA, que además vende funciones de entrenador por unos 4 USD al mes. Se documenta como riesgo con plan B en el plan de ejecución, sección 9.
- Un cambio de términos, una caída o un límite nuevo de su API se detecta por errores repetidos en la cola y por su foro. La respuesta es la carga manual, y evaluar un agregador de pago sólo si el ingreso lo sostiene.
- El texto que devuelva el proveedor —nombres de actividad, notas, descripciones— es **dato**, nunca instrucción para el copiloto (regla 5 del plan).
- Criterios que las pruebas deben sostener: un webhook duplicado no duplica actividad; un token expirado se renueva y reintenta una vez; una revocación deja la conexión en `revoked` sin borrar datos ya recibidos; una observación de HRV conserva su método.

## Alternativas descartadas

- **Integrar cada fabricante directamente.** Es el camino correcto a largo plazo y el más caro ahora: cada uno con su programa de desarrollador, su revisión y su calendario.
- **Agregador de pago (tipo Terra o Vital).** Resuelve el problema el primer día y cobra por atleta activo desde el primer día, antes de que exista ingreso.
- **Sólo carga manual de FIT.** Sostiene el piloto técnico pero no el producto: pedirle a un atleta que exporte y suba un archivo tras cada sesión es la fricción que hace que los datos dejen de llegar a la segunda semana.

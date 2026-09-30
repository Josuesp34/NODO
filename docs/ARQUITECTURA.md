# Arquitectura objetivo y contratos de trabajo

Estado: diseño propuesto, salvo lo identificado como implementado en `ESTADO_TECNICO.md`.

## Estructura

Backend modular en FastAPI, PostgreSQL y TimescaleDB para series temporales. NODO será la plataforma web y móvil de cada persona. NODO Lab será su módulo de entrenador; ambas experiencias usarán la misma API, cuenta y reglas de acceso. La identidad multirol se detalla en `ADR/0001-multi-role-identity.md`. El backend vive en `backend/api`; la carpeta se llamó `backend/fit-parser` hasta la fase F0 del plan de ejecución, cuando dejó de ser sólo un extractor de archivos FIT. El backend puede ampliarse por módulos antes de dividirlo en servicios. Kubernetes no es necesario para este piloto.

- `api`: HTTP, validación del contrato y autenticación/autorización.
- `domain`: conceptos y cálculos independientes de la infraestructura.
- `services`: casos de uso de importación, planificación, revisión y recomendaciones.
- `infrastructure`: persistencia, conectores y proveedor de IA.
- `core`: configuración y conexiones.

Separar trabajos largos en un worker persistente cuando se incorporen sincronización e IA. Los reintentos deben sobrevivir a reinicios; una tarea solo en memoria no basta para webhooks. La extracción FIT local ya sale del event loop, pero no tiene una cola persistente.

## Entidades que necesitamos

| Entidad | Información mínima e invariantes |
|---|---|
| Organización/equipo y membresía | Aislamiento de cuentas, roles y atletas autorizados; no confiar en un ID enviado por el cliente |
| Perfil del atleta | Deportes, zona horaria, historial, objetivos, disponibilidad, parámetros fisiológicos con fuente y vigencia |
| Grupo y asignación | Plantilla colectiva, copia individual y excepciones persistentes |
| Competencia | Fecha, disciplina y prioridad; más de una competencia por bloque |
| Bloque de plan | Inicio/fin libres, intención, metodología explícita y versión |
| Sesión y pasos | Calentamiento, trabajo, descanso, vuelta a la calma; orden, repeticiones, duración/distancia y objetivo con unidad |
| Actividad, sesión FIT y lap | Dueño obligatorio, origen, identificador externo/hash, periodos y vínculo a la prescripción |
| Observación de bienestar | Tipo, valor, unidad, método, proveedor, dispositivo, periodo, contexto y calidad |
| Check-in subjetivo | Fecha local, fatiga, descanso percibido, esfuerzo cuando corresponda y notas |
| Molestia | Zona, lateralidad, intensidad, inicio, limitación, actualizaciones y revisión |
| Recomendación y decisión | Evidencia, versión de reglas/modelo, plan base, cambios propuestos y aprobación/rechazo |

Los modelos ORM actuales no implementan aún todo este contrato. En particular, `DailyPhysiology` es un boceto de una fila por día; se debe migrar antes de recibir múltiples proveedores o varias lecturas del día. No agregar todas las métricas diferentes en `rmssd` ni sobreescribir silenciosamente datos de una fuente con otra.

## Contratos funcionales a implementar

### Planificación

La sesión contiene pasos estructurados, cada uno con tipo, repetición y objetivo tipado (ritmo, potencia, FC o percepción, con unidades). La instrucción conversacional es una entrada para crear esos pasos, no la fuente de verdad del calendario.

Una propuesta registra `base_plan_version` y una lista de cambios concretos. Aprobar verifica permisos y versión dentro de una transacción. Si otra persona editó el plan, responder conflicto y recalcular. El cliente puede previsualizar el cambio colectivo y sus excepciones.

### Observaciones diarias

Cada observación conserva `athlete_id`, `metric_type`, `value`, `unit`, `method`, `source`, `device_id`, `observed_start`, `observed_end`, `received_at`, `timezone`, `external_id` y `quality`. No todos los proveedores ofrecen todos los campos; la ausencia debe ser explícita. Ejemplos: `heart_rate/bpm`, `hrv/ms/method=sdnn`, `sleep_duration/min`, `vendor_recovery_score/vendor_scale`.

Separar series de pulso de resúmenes diarios. Al agregar, considerar día local, sueño que cruza medianoche, duplicados, cobertura parcial y lecturas recibidas tarde. Una nueva fuente no sustituye la referencia anterior sin indicar el cambio. No mezclar escalas de recuperación de fabricantes.

### Reportes de molestias

Crear y actualizar con identidad del atleta autenticado. El entrenador autorizado marca revisión y registra una decisión. Estado de la molestia y estado de una sesión son distintos. El cierre no equivale a certificación médica. Generar un elemento de bandeja deduplicado por reporte; actualizaciones relevantes reabren revisión, conservando historial.

### Ingesta

Autenticar el origen → identificar atleta autorizado → verificar hash/ID y tamaño → decodificar/normalizar → guardar actividad, sesiones y laps en transacción → recalcular días afectados → actualizar comparación y bandeja.

El cálculo diario suma todas las sesiones del día y procesa descansos con carga cero. Actividades históricas recibidas tarde exigen recalcular desde el día afectado. Guardar versión de fórmula y parámetros vigentes del atleta. No mezclar TRIMP y TSS como si fueran unidades idénticas.

### Copiloto

El proveedor de lenguaje recibe contexto mínimo y devuelve un borrador validado. Los cálculos numéricos provienen de funciones deterministas. Todas las recomendaciones conservan razones y campos ausentes. Textos de archivos, reportes o proveedores se tratan como datos, no como instrucciones que cambian permisos o ejecutan acciones. Sin respuesta del proveedor, el calendario manual sigue disponible.

## Entrega incremental y migraciones

Introducir Alembic antes del piloto con datos persistentes. Primer objetivo: migración inicial reproducible y estrategia de adopción de bases de desarrollo existentes, sin ejecutar `create_all` como actualización de esquema. El bootstrap actual solo cubre una base nueva.

Antes del piloto externo: autenticación, permisos por relación entrenador-atleta, pruebas de acceso cruzado, consentimiento, borrado/exportación, backups restaurables, errores sin datos personales y una política de datos del proveedor IA. La revisión de dependencias y el fijado de imágenes/versiones forman parte del hito de preparación operativa.

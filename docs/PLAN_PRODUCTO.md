# Plataforma de entrenamiento con copiloto: visión y plan inicial

Versión 1.0 · 13 de septiembre de 2026 · Equipo de dos personas.

Este documento recoge las decisiones de la conversación y actualiza la propuesta del PDF original. Es la referencia inicial de producto. Las metas y fechas son hipótesis de trabajo, no resultados logrados. El estado implementado se describe en el README y en `ESTADO_TECNICO.md`.

## 1. Propósito y propuesta de valor

Permitir que un entrenador dé atención individual a un equipo numeroso, diseñe mejores planes y ajuste su trabajo con información de la ejecución, el descanso y las sensaciones de cada atleta.

El entrenador conserva su metodología y la decisión final. El copiloto convierte instrucciones en borradores estructurados, resume evidencia y propone cambios revisables. El atleta recibe un plan comprensible y puede comunicar cómo lo está asimilando.

Hipótesis principal: reducir el tiempo de planificación y seguimiento por atleta sin perder la calidad ni el control que necesita el entrenador. Un caso de referencia es un equipo de 70 personas; no implica que cada piloto deba tener ese tamaño.

## 2. Usuarios y alcance

- Comprador y usuario principal: entrenador independiente o responsable de un equipo de resistencia.
- Atleta: recreacional o de alto rendimiento, con objetivos, historial y disponibilidad individuales.
- Primera familia de deportes: carrera, ciclismo, natación y triatlón. El triatlón combina disciplinas y requiere revisar su carga conjunta.
- Futuro: equipos de fútbol y otros deportes de conjunto, nutrición y fisioterapia con acceso específico. No se incluyen en el primer lanzamiento.

El MVP contempla los cuatro deportes en el calendario y las sesiones. La validación empieza con entrenadores y disciplinas concretas, y se amplía por cohortes. No se asume que el mismo modelo de rendimiento funcione para todos los deportes o niveles.

## 3. Recorrido principal

Objetivo y competencias → planificación asistida → revisión y publicación del entrenador → ejecución → sincronización y reporte del atleta → comparación y revisión → propuesta de ajuste → aprobación o rechazo.

### Planificar con libertad

El entrenador crea una sesión o un bloque de fechas arbitrario: semana, quincena, mesociclo o temporada. Puede definir fases, competencias prioritarias y secundarias, disponibilidad, descansos y sesiones dobles. Ninguna duración de bloque se impone.

Un pedido como «preparemos seis semanas para 800–1500 siguiendo estos principios» usa el historial, las marcas actuales y las restricciones del atleta. La IA presenta un borrador editable; los objetivos de marca son metas, no garantías. Las metodologías se describen por principios concretos aprobados por el entrenador, no solo por nombres.

### Personalizar a escala

Se crea una estructura para un grupo y se adapta por atleta. Los ritmos, potencia, volumen y recuperaciones se individualizan. Al editar un grupo se muestra la lista de afectados y se preservan las excepciones. La personalización no debe obligar a abrir 70 conversaciones independientes.

### Comparar y ajustar

Se vincula la actividad a la sesión prescrita; se comparan duración, intervalos, distancias y objetivos disponibles. Se distingue sesión no realizada de sesión todavía no sincronizada. Una nueva sincronización reevalúa la situación, pero no modifica automáticamente el calendario.

Cada propuesta muestra motivo, datos utilizados, limitaciones, sesiones afectadas y diferencias antes/después. El entrenador puede aprobar, modificar o rechazar, dejando trazabilidad. Una propuesta queda obsoleta si el plan cambió desde que se generó; debe recalcularse antes de aplicarse.

## 4. Descanso y estado físico: parte central del producto

No se mostrará que una persona está «100 % descansada». La recuperación se trata como una estimación contextual y revisable, con calidad y antigüedad de los datos visibles. Un reloj no observa por sí solo toda la recuperación muscular ni diagnostica una lesión.

| Información | Uso propuesto | Condiciones y límites |
|---|---|---|
| Frecuencia cardíaca durante el día | Tendencias en periodos comparables y contexto de actividad | No confundir movimiento, huecos de registro o falta de uso con anomalías fisiológicas |
| Pulso en reposo | Comparación con referencia individual | Conservar fuente, horario y método; no imponer umbrales universales |
| HRV | Tendencia respecto a una referencia del mismo método | Guardar RMSSD, SDNN u otro método explícitamente; no mezclarlos |
| Sueño | Duración, regularidad, horario y percepción de descanso | Identificar estimación del dispositivo; fases y puntuaciones dependen de la fuente |
| Puntuación de recuperación del fabricante | Contexto adicional, si la API la entrega | Conservar nombre, escala y proveedor; no comparar puntuaciones de marcas como equivalentes |
| Sensaciones del atleta | Fatiga, descanso percibido, estrés y esfuerzo de sesión | Reporte breve, opcional donde corresponda, con fecha y sin convertir ausencia en cero |
| Molestias | Aviso al entrenador y seguimiento de evolución | Autorreporte, no detección automática de lesión a partir del reloj |

Los estados iniciales de revisión serán: «datos insuficientes», «sin señales destacadas en los datos disponibles» y «requiere revisión». No son una autorización médica para entrenar. Las reglas y la cantidad mínima de historial se acordarán con los entrenadores del piloto y quedarán versionadas; no inventaremos una fórmula de recuperación universal.

### Reporte de molestias

El atleta indica zona corporal, lateralidad, intensidad percibida 0–10, inicio, si afecta el movimiento o la sesión y una nota opcional. Puede actualizar su evolución. Debe poder reportar una molestia aunque no use reloj.

Flujo: reportada → revisada por el entrenador → decisión registrada → seguimiento → cierre. Una molestia nueva o que empeora entra en la bandeja de revisión. El entrenador decide ajustar o pausar la sesión y, cuando corresponda, recomendar valoración profesional. El copiloto no diagnostica ni autoriza el retorno tras una lesión. Un reporte importante nunca queda oculto por una puntuación favorable del reloj.

## 5. Inteligencia artificial y proyecciones

Tres responsabilidades separadas:

1. Copiloto de planificación: interpreta instrucciones y produce sesiones en un formato validado. Hace preguntas cuando faltan restricciones esenciales.
2. Analítica reproducible: compara plan y ejecución, controla calidad de datos y calcula tendencias con fórmulas explícitas. Los números no se delegan a texto libre del modelo.
3. Propuestas y escenarios: explica alternativas y el efecto estimado sobre el calendario. Aplica cambios solo tras decisión del entrenador.

Para el MVP, la proyección consiste en escenarios de carga y recuperación respecto a competencias. No se promete una fecha exacta de máximo rendimiento, una marca final ni prevención de lesiones. La predicción individual de rendimiento se evaluará posteriormente con resultados reales y separación temporal entre entrenamiento y evaluación del modelo.

La IA recibe solo el contexto necesario. Sus resultados se validan contra un esquema y las restricciones del entrenador; un fallo del proveedor no debe bloquear la edición manual del calendario. No se usarán datos del atleta para entrenar modelos por defecto. Rechazar una propuesta sirve como retroalimentación de producto, no como prueba automática de una verdad fisiológica.

## 6. Datos e integraciones

La arquitectura será independiente de la marca. Esto no significa que todas las conexiones estén disponibles en ocho semanas.

- Actividades: FIT manual como respaldo; integración automática priorizada según dispositivos de los pilotos y acceso real.
- Bienestar diario: flujo independiente de las actividades; un FIT de entrenamiento no garantiza sueño, HRV o pulso de todo el día.
- Apple Watch: evaluar HealthKit y el componente móvil/autorizaciones necesarios, o una vía de integración autorizada. No asumir un webhook de nube equivalente al de otros proveedores.
- Garmin, Polar y COROS: verificar permisos, cobertura, coste, historial y sincronización antes de prometer compatibilidad.
- Agregador: decidir por cobertura comprobada, condiciones de uso y coste por atleta activo. No contratarlo solo porque aparezca en el PDF.
- Enviar sesiones al reloj es una capacidad diferente de importar datos; se prioriza después de comprobar recepción y calidad.

Todo dato debe conservar atleta, proveedor, método, unidad, instante/periodo, zona horaria, fecha de recepción e identificador externo cuando exista. Habrá deduplicación, reintentos, seguimiento de sincronización y tratamiento explícito de datos faltantes. Cambiar de dispositivo puede requerir reconstruir la referencia individual.

## 7. Entregables del MVP vendible

| Prioridad | Entregable | Criterio de aceptación |
|---|---|---|
| P0 | Cuentas y permisos | Un entrenador solo accede a sus atletas; pruebas entre dos cuentas sin relación |
| P0 | Grupos, perfiles y objetivos | Un atleta puede tener ajustes propios sin perderlos en una edición colectiva |
| P0 | Calendario y sesiones estructuradas | Bloques libres, repeticiones, descansos y objetivos por disciplina; edición manual completa |
| P0 | Copiloto de planificación | Genera un borrador válido, muestra cambios y permite aprobar o descartar |
| P0 | Ingesta y comparación | Actividad vinculada al atleta y al plan; reimportar no duplica; intervalos verificables |
| P0 | Reporte de bienestar y molestias | El atleta reporta, el entrenador ve y registra una decisión y seguimiento |
| P0 | Bandeja de revisión | Ordena casos con razones visibles; diferencia falta de sincronización de incumplimiento |
| P0 | Propuestas de ajuste | No modifica sesiones sin aprobación; registra versión y motivo |
| P0 | Operación de piloto | Consentimiento, permisos, recuperación de backup, soporte y errores controlados |
| P1 | Sincronización automática | Al menos una vía autorizada verificada con los dispositivos del piloto |
| P1 | Datos diarios del reloj | Fuente y cobertura visibles; alternativa manual durante indisponibilidad |
| P1 | Escenarios precompetencia | Comparación de alternativas con supuestos y límites visibles |
| Posterior | Predicción avanzada y otras marcas | Solo tras validación; no condiciona el valor básico del calendario |

P0 bloquea el piloto pagado. P1 define qué se puede anunciar en la oferta inicial: no se venderá sincronización ni proyección mientras no estén verificadas. Si el mercado exige P1 para comprar, se convierte en bloqueo comercial y se ajusta fecha o alcance.

## 8. Plan de ocho semanas para dos personas

Calendario propuesto: 14 de septiembre a 8 de noviembre de 2026. Requiere dedicación sostenida de ambas personas; disponibilidad real y experiencia se confirman antes de comprometer fecha de venta. Los roles A y B son responsabilidades propuestas, no asignaciones personales definitivas.

| Semana | Persona A: plataforma y datos | Persona B: experiencia y copiloto | Hito conjunto |
|---|---|---|---|
| 1 · 14–20 sep | Arranque, migraciones, contratos y aislamiento de datos | Entrevistas, prototipo de calendario y revisión | 5 entrevistas propuestas; seleccionar 2–3 entrenadores de prueba y verificar dispositivos |
| 2 · 21–27 sep | Cuentas, atletas, grupos y API de planificación | Perfiles, calendario manual y sesiones | Crear un plan individual sin IA; prueba de permisos cruzados |
| 3 · 28 sep–4 oct | Versiones de plan, sesiones por disciplina e importación identificada | Borradores IA, edición y aplicación a grupos | Entrenador genera, corrige y publica un bloque |
| 4 · 5–11 oct | Laps, vinculación y comparación; check-ins y molestias | Vista atleta, comparación y bandeja de revisión | Piloto interno completo, con registro manual de bienestar |
| 5 · 12–18 oct | Integración prioritaria y calidad de datos diarios | Propuestas de ajuste y aprobación | Piloto cerrado con datos consentidos; medir tiempo y utilidad |
| 6 · 19–25 oct | Reintentos, métricas diarias y escenarios si P0 está estable | Grupos grandes, alertas útiles y onboarding | Segundo ciclo de uso y correcciones del piloto |
| 7 · 26 oct–1 nov | Backup/restauración, observabilidad y revisión de accesos | Oferta, precio experimental, soporte y pulido | Revisión de preparación para cobro |
| 8 · 2–8 nov | Estabilización y solución de incidencias | Acompañamiento y conversión del piloto | Venta limitada si se cumplen criterios; si no, extender piloto |

Primero recortar integraciones adicionales, exportación al reloj y proyecciones avanzadas si hay retrasos. Mantener planificación manual, controles de acceso, calidad de ingesta, molestias y aprobación humana. Si el soporte multideporte no pasa las pruebas, declarar las disciplinas disponibles y abrir las demás por cohortes, sin anunciar cobertura inexistente.

## 9. Validación y primeras ventas

Propuesta de piloto: 2–3 entrenadores y 15–30 atletas adultos en total, con casos recreacionales y competitivos. Validar el funcionamiento de una lista de 70 atletas con datos sintéticos, sin exigir 70 participantes reales inicialmente. Incorporar menores requeriría un flujo específico de tutor y permisos antes de invitarlos.

Antes de programar más pantallas, recoger un ejemplo real consentido de planificación, medir cuánto tarda y observar cómo revisa el entrenador la ejecución. Repetir el mismo trabajo en el piloto; no limitar la validación a preguntar si la idea gusta.

Metas propuestas de decisión, a revisar después de medir la línea base:

- Reducir al menos 30 % el tiempo mediano de planificación/revisión de tareas comparables, sin correcciones críticas según el entrenador.
- Al menos dos entrenadores completan dos ciclos semanales y manifiestan intención concreta de continuar bajo una oferta con precio explícito.
- Cada alerta puede calificarse útil/no útil; investigar alertas repetidas, ignoradas o que generan trabajo adicional.
- Cero accesos cruzados en pruebas, cero duplicados al reintentar la misma actividad y toda modificación de plan atribuible a una decisión.
- Medir coste de IA, integración y soporte por entrenador y atleta activo antes de fijar margen.

Venta inicial sugerida como experimento: suscripción por entrenador con cupos de atletas y acompañamiento de incorporación. Definir precio con entrevistas y costes; no hay un precio validado todavía. Cobro y facturación pueden gestionarse manualmente en el piloto, con condiciones claras, sin construir una pasarela completa antes de probar la demanda.

## 10. Trabajo compartido

- `main` debe pasar pruebas. Ramas breves `codex/...` o las acordadas por el equipo; PR revisada por la otra persona.
- Persona A propone cambios de contrato y migraciones; Persona B revisa su efecto en interfaz y copiloto antes de integrar.
- Cada tarea incluye problema, alcance, aceptación y pruebas. Una demo semanal verifica el recorrido completo.
- Documentar decisiones en el repositorio. No guardar datos personales, archivos FIT reales, contraseñas ni tokens en Git.
- Compartir solo los datos necesarios con proveedores de IA; definir retención, revocación, exportación y borrado antes del piloto externo. Revisar requisitos aplicables con asesoría adecuada antes del cobro.
- Evaluar carga real cada semana. Dos meses es un objetivo para una venta limitada, no una garantía de disponibilidad general.

## 11. Decisiones pendientes de la primera semana

1. Dedicación y reparto definitivo de las dos personas.
2. Entrenadores piloto, disciplinas y dispositivos presentes.
3. Proveedor de IA, presupuesto máximo e integración autorizada prioritaria.
4. Reglas de revisión acordadas con entrenadores, sin umbrales médicos inventados.
5. Oferta inicial, precio a probar y criterios de continuidad del piloto.

## 12. Fuentes y límites del documento

Fuentes consultadas el 13 de septiembre de 2026. La disponibilidad por API debe verificarse durante la integración.

- [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/): describe datos diarios de pulso, sueño y estrés sujetos a acceso aprobado.
- [Apple HealthKit: HRV SDNN](https://developer.apple.com/documentation/healthkit/hkquantitytypeidentifier/heartratevariabilitysdnn): identifica el método SDNN; justifica conservar el método de cada lectura, sin asumir que toda HRV es RMSSD.
- [Garmin: Body Battery](https://support.garmin.com/en-SG/?faq=2qczgfbN00AIMJbX33dRq9): describe una estimación propia que combina señales; su presencia en un dispositivo no garantiza acceso por nuestra integración.
- [Sleep and the athlete: consenso 2021, repositorio de los autores](https://researchonline.ljmu.ac.uk/id/eprint/16297/): referencia para revisar descanso y limitaciones de medición con profesionales del piloto.
- [ACWR: problemas conceptuales y metodológicos](https://pubmed.ncbi.nlm.nih.gov/32502973/): fundamento para no convertir un cociente de carga en diagnóstico o promesa de prevención de lesiones.

Las decisiones de alcance, fechas, objetivos comerciales y reglas de producto son propuestas del equipo; no se presentan como conclusiones de estas fuentes.

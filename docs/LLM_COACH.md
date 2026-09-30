# Contrato del asistente de entrenador

Estado: **runtime simulado en API; proveedor real, conexión de la PWA y evaluación todavía pendientes**.

## Implementación actual

- `AI_PROVIDER=simulated` usa `deterministic-pilot-v1` y no sale a internet.
- La API crea threads, lee evidencia autorizada, devuelve citas y prepara escrituras con hash y expiración.
- El coach puede confirmar un borrador de sesión; la escritura no ocurre desde una respuesta libre.
- La pantalla **Copiloto** todavía genera una demostración local y no consume `/assistant`.
- `AI_API_KEY` y `AI_MODEL` no están configurados en el workspace.
- Cambiar variables a un proveedor distinto no basta: el adaptador real responde como no implementado.

## Trabajo permitido

- resumir evidencia autorizada de atletas asignados;
- responder preguntas con citas internas a datos y fechas;
- proponer un borrador de plan o ajuste estructurado;
- explicar incertidumbre y qué dato falta.

## Trabajo prohibido

- publicar o modificar sesiones, métricas, pagos o consentimiento;
- actuar sobre un atleta no asignado;
- calcular métricas fisiológicas que pertenecen al motor determinista;
- diagnosticar, prometer prevención o sustituir juicio clínico;
- ocultar una molestia o afirmar certeza no sustentada.

## Herramientas y datos

El servidor construye un allowlist por identidad y atleta; el modelo nunca elige el ámbito. Las herramientas sólo leen vistas o llaman servicios autorizados. Todo borrador usa schema estricto, versión de reglas/modelo, evidencia, timestamps y nivel de incertidumbre. Texto de FIT, notas o proveedores se delimita como contenido no confiable.

La escritura exige una acción humana separada: revisar diferencias, aprobar/rechazar, comprobar versión base con CAS y registrar decisión/auditoría. La aplicación manual sigue disponible si IA falla.

## Privacidad y costo

Enviar el mínimo contexto, sin secretos, tokens ni identificadores innecesarios. No entrenar con datos NODO salvo contrato y consentimiento explícitos. Definir región, retención, DPA, límites de tokens, timeout y presupuesto antes de conectar el proveedor real.

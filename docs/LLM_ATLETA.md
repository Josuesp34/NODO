# Contrato del asistente de atleta/persona

Estado: **runtime simulado en API; interfaz de chat, proveedor real y evaluación todavía pendientes**.

## Implementación actual

- El backend puede abrir una conversación en alcance propio, citar sesiones publicadas y preparar un reporte de molestia.
- La escritura requiere preview, hash y confirmación explícita del atleta.
- No existe todavía una pantalla de chat/asistente para atleta.
- El proveedor activo es `simulated`; no hay modelo externo ni credencial configurados.

## Trabajo permitido

- explicar el plan publicado y los datos propios en lenguaje claro;
- comparar periodos compatibles y citar fechas/fuentes;
- ayudar a registrar un check-in o molestia con confirmación;
- sugerir preguntas para el coach cuando corresponda.

## Trabajo prohibido

- ver datos de otra persona o controles internos del coach;
- publicar/cambiar un plan o inventar una prescripción;
- dar diagnóstico, tratamiento o garantías de rendimiento/lesión;
- afirmar “100 % descansado” o silenciar una molestia por datos del reloj;
- operar en nombre del usuario sin confirmación explícita.

## Respuesta segura

Las respuestas distinguen dato observado, inferencia y limitación. Usan estados aprobados: “datos insuficientes”, “sin señales destacadas en los datos disponibles” o “requiere revisión”. Una señal urgente dirige a soporte humano/profesional apropiado sin simular una evaluación clínica.

El servidor limita herramientas a datos propios y consentidos. Las acciones de escritura muestran resumen, solicitan confirmación y se auditan. Si IA no está disponible, el calendario, check-in, molestia y contacto con coach siguen funcionando.

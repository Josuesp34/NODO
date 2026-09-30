# Correo transaccional de NODO (Resend)

Estado al 23-09-2026: adaptador, cola, invitaciones y recuperación implementados y probados con transporte simulado. **No hay dominio ni entrega real verificada**. Este documento no autoriza contratar dominio, abrir una cuenta de pago o enviar mensajes a atletas reales.

## Activación con Brandon

1. Elegir y comprar un dominio de NODO. Decidir `app.dominio` para PWA y `acceso@dominio` para correo.
2. Crear cuenta Resend y verificar ese dominio con los registros DNS que Resend muestre para SPF y DKIM; configurar DMARC y comprobar el estado *verified*. [Documentación de dominios](https://resend.com/docs/dashboard/domains/introduction).
3. Crear una API key con alcance mínimo y guardar `RESEND_API_KEY` en Secret Manager, una versión distinta por entorno. No pegarla en chat, `terraform.tfvars` ni logs.
4. Generar una clave Fernet aleatoria para `EMAIL_QUEUE_KEY` y guardarla por entorno en Secret Manager. API y worker de un mismo entorno deben leer la **misma** versión. No rotarla mientras haya trabajos pendientes: la cola cifrada antigua dejaría de poder leerse.
5. Configurar `RESEND_FROM_EMAIL`, `PUBLIC_APP_URL` HTTPS, bindings de secretos de API/worker y `enable_worker=true`. Ejecutar migración Alembic 0005 antes de activar el tráfico.
   En desarrollo con Compose, iniciar también `docker compose up -d --build api worker` para que la cola avance.
6. En staging, invitar a una cuenta sintética autorizada y solicitar recuperación. Confirmar recepción, activar, restablecer contraseña, verificar que la sesión vieja ya no sirve y que el mismo código no se reutiliza. Revisar trabajos `dead` y métricas de Resend, sin imprimir códigos.
7. Repetir en producción sólo tras aprobación del dominio, legal/privacidad, costos y despliegue. La respuesta de API significa **en cola**, no «entregado»; el estado final lo confirma Resend y una prueba de bandeja.

## Contrato técnico

- `POST /auth/athletes` no expone el código en producción y falla con `503` si el correo no está listo. En desarrollo sin Resend aún puede entregarse manualmente el código para pruebas locales.
- `POST /auth/password-reset/request` devuelve la misma respuesta `202` si el correo existe o no. Limita intentos y no genera otro código para esa cuenta durante 15 minutos.
- El código de recuperación expira a los 30 minutos; al cambiar contraseña se invalida y se revocan todas las sesiones.
- Los mensajes se guardan cifrados en la tabla `jobs`, con una clave de idempotencia estable para reintentos. El worker usa la [API de envío](https://resend.com/docs/api-reference/emails/send-email) y el [encabezado de idempotencia](https://resend.com/changelog/idempotency-keys) de Resend. Después de un envío exitoso se elimina el cuerpo cifrado de la cola. La garantía de idempotencia de Resend dura 24 h: investigar trabajos viejos antes de reintentarlos manualmente.
- La cola no tiene webhooks de entrega ni reintento administrativo por UI; antes del GO comercial se requiere alerta para trabajos `dead` y validación manual de rebotes/entrega.

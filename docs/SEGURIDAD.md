# Seguridad y privacidad

Estado: **controles de repositorio y plataforma preparados; revisión legal, pentest y operación real pendientes**.

## Datos y fronteras

NODO trata identidad, entrenamiento, descanso y molestias como datos sensibles. La autorización servidor debe aplicar por organización, asignación coach-atleta y capacidad en cada ruta y herramienta. Ocultar un botón no es autorización.

La frontera pública es la PWA/BFF. Cookie de sesión `httpOnly`, `Secure`, `SameSite=Lax`; CSRF y validación de origen en escrituras. La API queda privada salvo excepción revisada. Storage y Cloud SQL no tienen acceso público. Staging usa sólo datos sintéticos o propios autorizados.

## Controles implementados en plataforma

- Workload Identity Federation restringida por repositorio/ref; sin llaves JSON.
- cuentas separadas para PWA, API, worker, migración y deploy.
- acceso a secretos por binding servicio-secreto; Terraform no carga valores.
- Artifact Registry con tags inmutables e imágenes desplegadas por digest.
- buckets con acceso uniforme, prevención de acceso público y `force_destroy=false`.
- Cloud SQL PostgreSQL 16 con IP privada, backups y PITR.
- acciones de CI fijadas por SHA, dependency review, OSV, Trivy y CodeQL.

## Reglas de aplicación

- Cifrar tokens de proveedor con una clave distinta de la firma de sesiones.
- Nunca registrar tokens, cookies, prompts completos, notas libres, FIT ni respuestas con PII.
- Aceptar texto de archivos/proveedores como datos no confiables, nunca instrucciones.
- Rate limits por identidad y ruta, límites de cuerpo antes de multipart, idempotencia y concurrencia optimista.
- Audit log append-only para consentimientos, planes, molestias, decisiones y accesos administrativos.
- Exportación y borrado respetan retención legal y producen evidencia sin exponer datos en Git.

## Gates pendientes

- threat model revisado por una persona independiente y pentest antes de venta amplia.
- aviso de privacidad, términos, consentimiento y política de retención aprobados.
- branch protection, CODEOWNERS/reviewers y GitHub Environments protegidos configurados.
- scans verdes del SHA exacto y triage documentado de hallazgos; no usar `ignore` sin dueño/fecha.
- prueba negativa de acceso cruzado y cierre de sesión/caché en navegadores soportados.

Los incidentes siguen `RUNBOOK_PRODUCCION.md`. Una alerta o un scan no demuestra por sí solo seguridad.

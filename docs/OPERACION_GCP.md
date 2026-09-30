# Operación de NODO en Google Cloud

Estado: **runbook preparado; sin proyecto ni credenciales verificados en esta entrega**.

## Preflight obligatorio

Un operador autorizado confirma la cuenta, proyecto, billing y región sin crear recursos:

```bash
export EXPECTED_GCP_ACCOUNT='cuenta-aprobada'
export GCP_PROJECT_ID='proyecto-aprobado'
export GCP_REGION='region-aprobada'
bash ops/preflight-gcp.sh
```

No copiar la salida completa a tickets públicos. Registrar únicamente fecha, operador, proyecto, región, billing habilitado sí/no y decisión.

## Terraform

1. Crear por procedimiento separado un bucket privado y versionado para estado.
2. Copiar `backend.hcl.example` y `terraform.tfvars.example` fuera de Git.
3. Ejecutar `terraform init -backend-config=backend.hcl`.
4. Ejecutar `terraform plan -out=reviewed.tfplan`; revisar destrucciones, costos, IAM y región.
5. Requerir aprobación humana para el primer `apply` y cualquier destrucción.
6. Aplicar primero con `deploy_workloads=false`.
7. Cargar versiones de secretos por un canal seguro; publicar imágenes escaneadas por digest.
8. Planear y aplicar los workloads.

No se automatiza el `terraform apply` desde GitHub. Los workflows de despliegue sólo actualizan imágenes de workloads ya creados.

## Operación diaria

- Revisar disponibilidad, 5xx, latencia, disco, backups y cola de trabajos.
- Revisar presupuesto y tendencia de costo; un budget no corta el gasto.
- Confirmar que no existen secretos en logs y que no se registran cuerpos con datos de salud.
- Rotar versiones de secretos, desplegar y deshabilitar la versión anterior tras verificar.
- Mantener registro de SHA, digest, revisión, migración, smoke y operador.

## Accesos

Producción usa GitHub OIDC/WIF y cuentas de servicio separadas. No crear llaves JSON persistentes. El acceso humano se otorga por grupos o identidades nominativas con MFA y mínimo privilegio; no mediante cuentas compartidas.

## Promoción entre proyectos

Antes de promover digests del registro staging, configurar `artifact_reader_members` en staging para la identidad de deploy prod y el service agent Cloud Run del proyecto prod. Terraform conserva los digests y los workflows autentican el scanner en los registros fuente; los permisos reales se verifican en staging antes de la primera promoción.

El Environment `production` debe tener `SOURCE_IMAGE_PREFIX=REGION-docker.pkg.dev/STAGING_PROJECT/REPOSITORY`, configurado por el operador. El preflight exige que la imagen API sea exactamente `${SOURCE_IMAGE_PREFIX}/api@sha256:…` y la PWA `${SOURCE_IMAGE_PREFIX}/pwa@sha256:…`; rechaza otros hosts, proyectos, repositorios o tags antes de obtener credenciales. No derivar el origen confiable de inputs del workflow.

En `pwa_env` configurar `NODO_APP_ORIGIN` con la URL HTTPS canónica de cada entorno y `SESSION_COOKIE_SECURE=true`. El BFF valida ese origen antes de las escrituras y acota el cuerpo antes de llamar a la API.

La base de plataforma aún requiere crear un usuario PostgreSQL con acceso mínimo y guardar `DATABASE_URL` para API/worker/migraciones en Secret Manager. Terraform no genera ni persiste contraseñas. No habilitar registro development en producción para crear el primer administrador.

## Primer administrador sin abrir development

La imagen incluye `python -m app.bootstrap_admin` como comando de job de una sola ejecución. Exige `NODO_BOOTSTRAP_CONFIRM=CREATE-FIRST-ADMIN` y `NODO_BOOTSTRAP_EMAIL`, `NODO_BOOTSTRAP_PASSWORD`, `NODO_BOOTSTRAP_FIRST_NAME`, `NODO_BOOTSTRAP_LAST_NAME` (zona opcional `NODO_BOOTSTRAP_TIMEZONE`). Correo/contraseña se enlazan desde secretos sólo a ese job; no se pasan como argumentos ni se imprimen. La cuenta de servicio necesita base y los secretos concretos.

Ejecutar después de migrar: crea únicamente el primer superusuario y su organización, registra auditoría, es idempotente para la misma cuenta y rechaza elevar una cuenta existente o crear otro primer administrador. PostgreSQL serializa ejecuciones competidoras. No cambia las banderas HTTP de registro/bootstrap de desarrollo. Revocar acceso a los secretos de bootstrap y eliminar el job temporal tras verificar login y entregar acceso por canal seguro. No se ha ejecutado sobre una base real en esta entrega.

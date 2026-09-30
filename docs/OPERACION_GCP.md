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

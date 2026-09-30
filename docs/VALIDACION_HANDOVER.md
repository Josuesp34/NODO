# Evidencia de entrega de NODO

Fecha: 29-09-2026. Esta evidencia se completa después de ejecutar los checks y leer el estado remoto. No registra una validación humana que no haya ocurrido.

## Evidencia actual

- Backend integrado: **58 pruebas aprobadas**, Ruff check/format y `pip check` aprobados. Incluye revocación efectiva en asistentes/recomendaciones/export y bootstrap seguro del primer administrador por job.
- PWA integrada: **34 pruebas aprobadas**, typecheck de los workspaces y build de producción de 37 rutas aprobados. Incluye renovación de sesión, IAM Cloud Run, validación de origen y cuerpos acotados. Expo sale del workspace activo según ADR 0003 y conserva su código de referencia.
- Prueba HTTP de las protecciones BFF: 18 solicitudes maliciosas rechazadas sin llamadas backend y seis endpoints legítimos aceptados en un entorno sintético.
- Terraform 1.13.3: formato y validación staging/prod aprobados; no se ejecutó plan/apply.
- Dependencias Python de producción: resolución Python 3.11 Linux y Python 3.12 macOS, 45 paquetes por entorno y sin advisories OSV conocidos al consultar. El CI vuelve a escanear el lock de frontend y backend.
- El origen de imágenes de producción se valida contra un prefijo Artifact Registry aprobado antes de obtener credenciales; referencias sintéticas cubren registro ajeno, proyecto ajeno y tags mutables.
- Docker Desktop no estaba activo en este equipo; migraciones/contenedores requieren evidencia del CI para esta entrega.
- Google ADC pudo renovarse y consultar proyectos, pero no se verificó la identidad prevista y no se encontró proyecto NODO. No se aprovisionaron recursos.
- GitHub no tenía Environments, variables ni secretos de despliegue de NODO en el preflight.

## Pendientes de evidencia

- [ ] CI del SHA exacto, builds/scans y migraciones PostgreSQL 16.
- [ ] PR completo integrado a dev y release integrado a main.
- [ ] Tag/version publicada y readback remoto.
- [ ] URL de staging/producción y E2E real.
- [ ] IA, Intervals, correo y push reales.
- [ ] Restauración, monitoreo, costo y dispositivos físicos.
- [ ] Demo y aceptación de Josué.

La autorización general de producción fue recibida. Los pendientes de datos/acceso y los criterios de apertura están en [HANDOVER_JOSUE.md](HANDOVER_JOSUE.md).

La evidencia inmutable del SHA final, PRs, runs y tag se adjunta a [GitHub Release v0.4.0-rc.1](https://github.com/Josuesp34/NODO/releases/tag/v0.4.0-rc.1) al publicar. Un resultado local no se presenta como CI, y un tag no se presenta como un despliegue.

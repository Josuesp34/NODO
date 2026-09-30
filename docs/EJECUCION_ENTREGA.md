# Ejecución de la entrega completa

Inicio: 30-09-2026. Estado: **en ejecución**.

Brandon autorizó ejecutar el plan completo, integrar y publicar sin repetir autorizaciones generales. La aceptación de Josué, cuentas propietarias, consentimiento y resultados reales se registran cuando existan.

**Restricción posterior de Brandon:** no crear, modificar ni desplegar recursos en Google Cloud. Vibe Conversa pertenece a otro proyecto y queda fuera de este encargo. Se mantiene la publicación del código y las versiones en GitHub; la activación y el despliegue cloud se entregan a Josué como pendientes. La pestaña de consola abierta para consultar accesos se cerró sin modificaciones.

## Carriles y dependencias

| Carril | Rama | Trabajo |
|---|---|---|
| Integración, demo, E2E y plataforma | `codex/completar-entrega` | B0/B1/B8/B9/B10/B11, revisión e integración |
| Producto y comparación | `codex/producto-completo` | B2/B3; migración 0006 reservada |
| Asistentes y proveedores | `codex/proveedores-completos` | B4/B5; migración 0007 reservada |
| Privacidad, push y comercial | `codex/privacidad-push` | B6/B7; migración 0008 reservada |

Los implementadores usan worktrees distintos. Integración revisa contratos, encadena migraciones y verifica el producto completo antes de publicar. Ninguna rama independiente equivale a entrega.

## Preflight externo observado

- GitHub: escritura disponible, administración no disponible; Environments/variables aún vacíos.
- GCP CLI: sin identidad autenticada ni proyecto activo.
- ADC: renovación y lectura de proyectos/billing disponibles, pero sin scope de identidad; no permite comprobar que corresponda a `brandonmuro.work@gmail.com`.
- No se encontró proyecto NODO en la consulta realizada. Hay una cuenta billing visible, pero no está verificada su vinculación al encargo ni créditos/costos.
- No se crearon recursos cloud. Se continúa todo trabajo independiente.

Josué deberá autenticar la identidad propietaria y confirmar proyecto/billing/dominio/cuentas proveedor cuando active la infraestructura. Estos datos no se sustituyen utilizando otros proyectos.

## Evidencia y próximos pasos

- [ ] Demo de clon limpio y semilla sintética idempotente.
- [ ] E2E navegador con API/PostgreSQL/worker reales.
- [ ] Producto y comparación integrados.
- [ ] Ambos chats y adaptadores de proveedores integrados.
- [ ] Push, privacidad, retención y comercial integrados.
- [ ] Corpus 70 × 12 semanas, carga y seguridad verificadas.
- [ ] CI del SHA actual; PR dev/main y nueva versión publicados.
- [ ] Preparación verificable del despliegue; ejecución en Google Cloud reservada a Josué por instrucción de Brandon.
- [ ] Handover y mensaje actualizados con evidencia y pendientes exactos.

Actualizar este registro conforme se ejecuten las comprobaciones; nunca convertir una prueba simulada en recepción o integración real.

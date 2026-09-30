# Funcionalidades actuales de NODO

Actualizado: 29 de septiembre de 2026.

Este documento es el inventario funcional vigente. Distingue una función operativa de una simulación, una integración parcial y una capacidad todavía pendiente. La referencia ejecutable sigue siendo OpenAPI en `/docs` y las pruebas del repositorio.

## Estados

- **Funcional:** existe código consumido por la PWA o API, con prueba local verificable.
- **Funcional con operación manual:** sirve para el piloto, pero requiere una acción humana fuera de NODO.
- **Simulado:** valida permisos, datos y experiencia sin llamar a un proveedor externo.
- **Parcial:** existe una parte del contrato, pero falta un recorrido necesario para usuarios reales.
- **Pendiente:** no debe ofrecerse como disponible.

## Inventario por área

| Área | Funcionalidad | Estado | Evidencia y límites |
|---|---|---|---|
| Pública | Landing, acceso, activación, recuperación, soporte, privacidad, términos y fallback offline | Funcional en código | Rutas Next, build PWA y QA visual local; recuperación exige correo real |
| Sesión | BFF con cookies `httpOnly`, refresh rotado, logout y protección de rutas | Funcional | Pruebas PWA y backend; HTTPS real pendiente del despliegue |
| Identidad | Coach, atleta, superusuario de bootstrap, roles múltiples y capacidades | Funcional | Acceso cruzado y normalización de capacidades probados |
| Bootstrap | Job explícito para el primer administrador, idempotente y auditado | Funcional en código/pruebas | Sin registro development público; ejecución en producción pendiente |
| Equipo | Invitación, activación y revocación de asignación coach-atleta | Funcional local; correo pendiente de activar | En producción la API encola el código cifrado con Resend y no lo devuelve; falta dominio, secretos y envío real. Desarrollo conserva entrega manual |
| Correo/recuperación | Resend en cola, recuperación de contraseña y revocación de sesiones | Funcional en código; no operativo aún | Pruebas locales con transporte simulado; sin dominio verificado ni email real. Ver `RESEND_CONFIGURACION.md` |
| Organizaciones | Organización, membresías, asignaciones y cupos por plan | Funcional | Persistencia y límite comercial en backend |
| Planificación | Bloques, sesiones estructuradas, varias sesiones por día, edición CAS y publicación idempotente | Funcional | E2E local coach → publicación → atleta |
| Experiencia atleta | Hoy, semana y detalle de sesión publicada | Funcional | La persona sólo recibe versiones publicadas |
| Perfil | Perfil deportivo versionado y lectura coach/atleta | Funcional | Conserva fuente y vigencia |
| Contexto | Competencias, observaciones y check-in diario | Funcional en API; check-in y perfil consumidos por PWA | No toda captura administrativa tiene pantalla dedicada |
| Molestias | Alta, historial, actualizaciones y creación de revisión | Funcional | No diagnostica ni reemplaza atención clínica |
| Revisión | Bandeja y decisión con nota | Funcional | Prioridades con razón visible; no se ocultan molestias |
| FIT | Carga autenticada, deduplicación, laps, telemetría, auditoría y job de carga diaria | Funcional | Archivo de una sola sesión, máximo 10 MiB; guía en `GUIA_CARGA_FIT_E_INTERVALS.md` |
| Actividades | Historial básico por atleta | Funcional en API | La PWA muestra el resultado de importación; el historial completo aún no tiene pantalla propia |
| Grupos | Crear, listar y gestionar miembros | Funcional | Restringido al coach autenticado |
| Plantillas | Crear, listar y aplicar de forma idempotente | Funcional | Edición avanzada de plantillas no disponible |
| Recomendaciones | Crear, listar, aprobar/rechazar y proteger contra plan obsoleto | Funcional | Requiere una sesión borrador válida |
| Privacidad | Consentimiento versionado, historial, revocación, exportación y desidentificación | Funcional | Revisión legal y retención de producción pendientes |
| Comercial | Planes, suscripciones, cupos y pagos administrados | Funcional para superusuario | No procesa tarjetas, no factura y no inventa precios |
| Cola | Jobs persistentes, lease, reintentos y deduplicación | Funcional en código/pruebas | Worker desplegado y métricas de cola pendientes |
| IA coach | API de conversación simulada, citas, vista previa y confirmación para crear borrador | Simulado | La pantalla Copiloto usa una simulación local; no llama a un modelo real |
| IA atleta | API simulada con alcance propio y confirmación para registrar molestia | Simulado en API | No existe aún una pantalla de chat para atleta |
| IA real | Adaptador y modelo externo | Pendiente | No hay proveedor implementado, credencial, modelo ni evaluación aprobada |
| Intervals.icu | Consulta de estado, simulación y revocación local | Simulado/parcial | No existe OAuth real completo, callback, webhook ni backfill |
| Notificaciones | Pantalla honesta de estado | Pendiente | Faltan preferencias, suscripción Web Push y envío |
| Plataforma | Terraform GCP, Cloud Run, Cloud SQL, Storage, Secret Manager, WIF, budgets y runbooks | Preparada en código | No hay `plan/apply`, recursos, URL HTTPS ni evidencia pública |

## Estado exacto de los modelos de IA

La configuración activa por defecto es:

```text
AI_PROVIDER=simulated
AI_API_KEY=no configurada
AI_MODEL=no configurado
```

El proveedor `simulated` es determinista y no sale a internet. Sirve para validar autorización, citas, preview y confirmación humana. Si se cambia `AI_PROVIDER` a otro valor, la API exige una clave y después responde que el adaptador real todavía requiere validación: establecer variables no convierte la IA real en funcional.

Antes de ofrecer IA real faltan, como mínimo:

1. elegir proveedor, modelo, región, retención y presupuesto;
2. implementar el adaptador servidor-a-servidor;
3. conectar las pantallas al API de asistentes;
4. ejecutar la suite de `EVALUACIONES_LLM.md`;
5. aprobar seguridad, costo, latencia y comportamiento;
6. conservar siempre los flujos manuales.

## Estado exacto de Intervals.icu

Hoy NODO permite consultar y persistir un estado `simulated`, solicitar modo real y revocar localmente. El modo real devuelve `INTERVALS_CONFIGURATION_REQUIRED` porque no hay credenciales configuradas. Aun con credenciales, el recorrido seguiría incompleto: faltan inicio OAuth con `state`, callback, intercambio y cifrado del token, revocación remota, webhooks verificados, backfill y sincronización. La documentación vigente del proveedor no publica refresh token; ante un token inválido corresponde marcar la conexión caída y pedir reconexión, no inventar una renovación.

Por eso la carga manual de FIT es el camino funcional del piloto. La pantalla no debe presentar Intervals.icu como “conectado” hasta que el servidor confirme una conexión real.

## Evidencia local vigente

- backend: 59 pruebas y Ruff check/format verdes;
- PWA: typecheck, 34 pruebas y build Next de 37 páginas estáticas/rutas dinámicas;
- PostgreSQL 16: migraciones 0001→0005, `alembic check`, downgrade base y upgrade head comprobados localmente; E2E coach → atleta comprobado previamente;
- Docker API/PWA y Terraform staging/prod validados localmente;
- sin credenciales reales de IA o Intervals.icu en el workspace.

Estas evidencias no sustituyen CI remoto, staging, URL HTTPS, proveedores reales, dispositivos, restore drill, pentest o aprobación legal/comercial.

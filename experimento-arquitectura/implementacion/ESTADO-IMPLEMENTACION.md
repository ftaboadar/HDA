# Estado real de la implementación

**Para quién:** cualquier persona o asistente de IA que vaya a **desplegar, probar o seguir
construyendo**. Este archivo dice **qué existe de verdad hoy**. El diseño objetivo (lo que se va a
construir en la Entrega 5) está en [`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md).
Si los dos no coinciden, no es un error: el diseño va adelante de la implementación.

- **Para desplegar**, manda este archivo: despliega solo lo marcado como desplegable, con la receta marcada como probada.
- **Para construir**, manda el diseño (15-…md) más [`CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md).
- **Regla:** todo PR que implemente, despliegue o destruya algo **actualiza este archivo en el mismo PR**
  (fila del servicio + "Última verificación").

**Última verificación: 2026-09-22** (rama `feature/entrega-5-etapa-2-experimentos`). El proyecto
`hogaralpes`/`hda-projectt` quedó con la facturación cerrada ("Billing Account for Education"). El
despliegue activo de GCP se movió al proyecto **`project-b68c032a-000b-4601-8bd`** (billing account
"My Billing Account", 017EA3-A5C15D-D99208). Antes de desplegar en cualquier proyecto nuevo corre
`gcloud auth application-default set-quota-project <PROYECTO>` y `gcloud config set project
<PROYECTO>` — si el quota project de ADC apunta a un proyecto con facturación cerrada, `terraform
init` con backend GCS falla con `403 UserProjectAccountProblem: billing account ... disabled in state
closed` aunque el proyecto destino sí tenga facturación activa (encontrado en esta sesión).

**Sesión 4 (2026-09-22, más tarde): migración de `proveedores/infra` a Pulsar completada, ciclo
end-to-end verificado en verde, e infraestructura apagada al final** (el usuario autorizó el apagado
en cuanto el ciclo completo quedara confirmado). Ver hallazgo debajo — reemplaza el hallazgo CRÍTICO
de la sesión 3 (ya resuelto). **La infraestructura de los 14 stacks (12 servicios + Pulsar +
observabilidad) fue destruida y verificada en 0 recursos facturando** al cierre de esta sesión; para
volver a desplegar, usar la receta de la sección 3.

## 1. Qué hay desplegado en GCP ahora mismo

**Nada de los 14 stacks del proyecto** (`gestion-de-trabajos`, `proveedores`, `pagos`, `reputacion`,
`marketplace`, `siniestros`, `suscripciones`, `scoring`, `bff`, `mocks-crm`, `mocks-pagos`,
`pulsar-infra/gcp`, `observabilidad`, `k6`) está desplegado en `project-b68c032a-000b-4601-8bd` —
confirmado con `scripts/verificar-nada-facturando.sh` (2026-09-22, sesión 4): `Cloud Run: nada` (de
nuestros stacks), `Cloud SQL: nada`, `Compute Engine (VMs): nada`. State de Terraform sigue en
`gs://project-b68c032a-000b-4601-8bd-tfstate` (no se borró, `BORRAR_BUCKET_STATE` no se usó).

**Queda un recurso ajeno a nuestros 14 stacks, fuera de alcance de esta sesión, NO borrado a
propósito:** una Cloud Function `frenar-gasto` (Cloud Run gen2) + su Pub/Sub `presupuesto-alertas` +
el Artifact Registry `gcf-artifacts` + 2 buckets `gcf-v2-*` — por el nombre, es un mecanismo de
protección de gasto por presupuesto (kill-switch), no algo que cree ningún stack de
`desplegar-todo.sh` ni que aparezca en la tabla de la sección 2. Costo idle de un Cloud Function gen2
de bajo tráfico es prácticamente nulo; se dejó intacto en vez de borrar a ciegas una salvaguarda de
facturación sin autorización explícita del usuario para tocarla. `verificar-nada-facturando.sh`
reporta código de salida `1` por esto — es **esperado**, no un fallo del destroy de nuestros stacks.

### Hallazgo — `proveedores/infra` migrado a Pulsar; ciclo end-to-end DISP-03 verificado en GCP real (2026-09-22, sesión 4, `experto-gcp`)

Causa raíz ya diagnosticada en la sesión 3 (ver hallazgo debajo, conservado para trazabilidad):
`proveedores/infra` seguía en Pub/Sub (`TRANSPORTE=pubsub` hardcoded, `pulsar_service_url` sin wire,
sin Direct VPC egress) mientras el worker (código ya reescrito para Pulsar) crasheaba sus 2
consumidores al arrancar. Corregido replicando el patrón ya probado de `gestion-de-trabajos/infra`:

- `proveedores/infra/main.tf`: agregado `data "google_compute_subnetwork" "default"` (mismo patrón,
  `.id` no `.self_link` — Cloud Run v2 exige `projects/*/regions/*/subnetworks/*`).
- `proveedores/infra/cloudrun.tf`: agregado bloque `vpc_access` (Direct VPC egress,
  `PRIVATE_RANGES_ONLY`) a **ambos** `google_cloud_run_v2_service.api` y `.worker` (la API publica a
  Pulsar, el worker consume — los dos necesitan la ruta de red hacia la VM). `TRANSPORTE` de la API
  cambiado de `"pubsub"` a `"pulsar"`. `PULSAR_SERVICE_URL` ya existía como env var en ambos
  servicios, solo hacía falta que Terraform recibiera un valor real (ver abajo).
- `proveedores/infra/variables.tf`: reescrito el docstring de `pulsar_service_url` (ya no dice "el
  transporte real sigue siendo Pub/Sub" — dejó de ser cierto).
- **No hizo falta wiring adicional**: los `pulsar_topic_*`/`pulsar_suscripcion_*` de
  `app/common/config.py` ya tenían default correcto vía `app/common/pulsar_topology.py`; solo
  `PULSAR_SERVICE_URL` necesitaba venir de Terraform (la IP privada de la VM no se puede conocer de
  otra forma). Las env vars `PUBSUB_TOPIC_*` se dejaron intactas (no rompen nada con
  `TRANSPORTE=pulsar`, el código simplemente no las usa en ese modo); `pubsub.tf` no se tocó.
- `terraform fmt`/`validate` limpios. `terraform plan` contra el state real (`project_id`,
  `region=us-east1`, `pulsar_service_url=pulsar://10.158.0.2:6650`) dio el diff mínimo esperado:
  **0 to add, 2 to change, 0 to destroy** (solo las envs `TRANSPORTE`/`PULSAR_SERVICE_URL` y el
  `vpc_access` nuevo en `api` y `worker`) — confirma que no había drift oculto. `terraform apply`
  exitoso (11-12s por servicio, revisiones nuevas `disp03-poc-api`/`disp03-poc-worker`).

**Verificación end-to-end real:** `/salud` de API y worker en `200`/`403` (el `403` del worker es
IAM esperado, no una falla). `POST /verificaciones {"proveedor_id":"proveedor-e2e-002",
"tipo_verificador":"rues"}` → `201`, id `1452cbd3-6c2d-469f-824b-a69ee0ac3bc1`. `GET
/verificaciones/{id}` salió de `PENDIENTE` a `COMPLETADA` en **~4 segundos** (2 intentos), muy por
debajo de los 90s de margen dados. Logs de Cloud Logging de la revisión nueva del worker
(`disp03-poc-worker-00003-qc8`) sin ningún `consumidor_crasheo`. Los otros 12 servicios + Grafana se
confirmaron sanos de pasada (`/salud`/`/api/health` en `200`, sin tocarlos). **DISP-03/H1 vuelve a
tener evidencia fresca de GCP real, esta vez con Pulsar de verdad (no con el transporte Pub/Sub de la
corrida anterior, ya invalidada) — actualizar la fila de DISP-03 en la sección 4 si se cita en el
video.**

**Bug adicional encontrado y corregido en el camino (script de destroy, no de este journey):**
`scripts/destruir-todo.sh` tenía un `ORDEN` desactualizado — le faltaban `bff/infra`,
`marketplace/infra`, `siniestros/infra`, `suscripciones/infra` y `scoring/infra` (los 5 servicios
nuevos de Entrega 5, que sí crea `desplegar-todo.sh`). Sin este fix, el destroy real habría dejado
esos 5 stacks (con sus Cloud SQL) facturando en silencio, porque `verificar-nada-facturando.sh` no
compara contra lo que `desplegar-todo.sh` despliega, solo lista lo que hay. Además `bff/infra` exige
8 `-var *_url=...` sin default incluso para destruir (Terraform valida variables requeridas también
al planear un destroy) y el script no los pasaba — corregido en `scripts/comun.sh` (`vars_extra`) con
placeholders fijos (el valor no importa para destruir: Terraform identifica recursos por dirección,
no por el contenido del env var). Confirmado corriendo `destruir-todo.sh` completo dos veces: la
primera destruyó los 8 stacks que antes habían quedado con `ORDEN` incompleto/vars faltantes (uno por
uno, con logging completo para diagnosticar — el primer intento con el `ORDEN` corregido pero sin el
fix de `vars_extra` seguía fallando 8 stacks, todos por la misma causa de variables faltantes al
destruir, ninguno por un problema de GCP real); la segunda, ya con todo destruido, confirmó
`Destroy complete! Resources: 0 destroyed.` en los 14 stacks sin ningún `fallido`.

### Hallazgo (sesión 3, histórico) — `/salud` corregido en `disp03-poc-api`/`marketplace-poc-api`

Se reconstruyeron y redesplegaron `disp03-poc-api`, `disp03-poc-worker` y `marketplace-poc-api` con
el código corregido — **los 3 `/salud` dieron `200`** (el hallazgo de `/salud` con 404 de la sesión
anterior quedó resuelto). Pero la verificación de punta a punta (`POST /verificaciones` → esperar
estado terminal) **encontró el bug bloqueante que resuelve el hallazgo de sesión 4 de arriba**: el
worker crasheaba sus dos consumidores Pulsar al arrancar porque `PULSAR_SERVICE_URL` llegaba vacío.

**URLs de los servicios — histórico de sesión 3, ya NO están desplegadas (infra destruida en sesión 4):**
- **Gestión de Trabajos API:** https://gestion-trabajos-poc-api-wp7nbtaynq-ue.a.run.app (`us-east1`)
- **Proveedores API:** https://disp03-poc-api-wp7nbtaynq-ue.a.run.app (`us-east1`)
- **Proveedores Worker:** https://disp03-poc-worker-wp7nbtaynq-ue.a.run.app (`us-east1`)
- **Mocks Proveedores:** Certificadora (https://disp03-poc-mock-certificadora-wp7nbtaynq-ue.a.run.app), Policía (https://disp03-poc-mock-policia-wp7nbtaynq-ue.a.run.app), RUES (https://disp03-poc-mock-rues-wp7nbtaynq-ue.a.run.app)
- **Pagos API:** https://pagos-poc-api-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Reputación API:** https://reputacion-poc-api-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Mocks CRM:** https://mocks-crm-poc-mock-crm-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Mocks Pagos:** MercadoPago (https://mocks-pagos-poc-mock-mercadopago-wp7nbtaynq-rj.a.run.app), Stripe (https://mocks-pagos-poc-mock-stripe-wp7nbtaynq-rj.a.run.app) (`southamerica-east1`)
- **Grafana:** https://observabilidad-poc-grafana-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Pulsar:** IP privada `10.158.0.2:6650`, IP pública `35.198.30.154`, VM `pulsar-poc-vm` en `southamerica-east1-a`
- **Siniestros API:** https://siniestros-poc-api-wp7nbtaynq-uc.a.run.app (`us-central1`)
- **Suscripciones API:** https://suscripciones-poc-api-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Scoring API:** https://scoring-poc-api-wp7nbtaynq-ue.a.run.app (`us-east1`)
- **BFF API:** https://bff-poc-api-wp7nbtaynq-rj.a.run.app (`southamerica-east1`)
- **Marketplace API:** https://marketplace-poc-api-wp7nbtaynq-ue.a.run.app (`us-east1`)

### Hallazgo — bugs de aplicación de `bff`/`suscripciones`/`scoring`/`siniestros`: CORREGIDOS y verificados en GCP (2026-09-22)

Los 4 bugs de código descritos en la sesión anterior (dataclass con orden de campos inválido en
`siniestros/app/domain/events.py`, import roto `app.domain.seedwork.domain_event` en
`suscripciones/app/seedwork/aggregate_root.py`, `app/api/main.py` vacío en `scoring/`, entrypoint
inexistente `app.api.main:app` en `bff/`) fueron corregidos por `implementador-ddd`. Además el stack
`bff/infra` no pasaba las URLs de los 8 servicios downstream a Cloud Run (`bff/infra/variables.tf` +
`service.tf` ahora declaran y mapean `gestion_trabajos_url`, `proveedores_url`, `pagos_url`,
`siniestros_url`, `marketplace_url`, `suscripciones_url`, `scoring_url`, `reputacion_url` a las env vars
que lee `bff/app/api/main.py`). Las 4 imágenes se reconstruyeron con `gcloud builds submit` y los 4
stacks se reaplicaron con Terraform — los 4 responden `200` en `/salud`.

**Bug de infraestructura real encontrado en el camino (no de código de aplicación):** el primer
`terraform apply` de `siniestros/infra` falló con `Error waiting to create Service: ... Resource
readiness deadline exceeded` tras 14 min sin que el contenedor emitiera **ningún** log (ni de sistema
ni de aplicación) — la revisión nunca llegó a programarse, no fue un crash de la app (que si hubiera
ocurrido habría dejado logs de arranque de uvicorn o un traceback). Reintentar el mismo `apply` sin
tocar nada tuvo éxito en 23 s, confirmando que fue una falla transitoria de scheduling de Cloud Run en
`us-central1`, no un bug de código o de Terraform. Si vuelve a ocurrir, reintentar antes de asumir un
bug de aplicación — pero seguir revisando logs de la revisión (`gcloud logging read
'resource.type=cloud_run_revision AND resource.labels.revision_name=...'`) para no ocultar una falla
real detrás de un reintento ciego.

### Hallazgo NUEVO — `proveedores/infra` y `marketplace/infra` no tienen `/salud` funcional (encontrado 2026-09-22)

Verificando `/salud` de los 12 servicios + Grafana antes de decidir si apagar la infraestructura, **2
stacks que ya estaban desplegados antes de esta sesión fallan con `404`**:

- **`disp03-poc-api` (Proveedores):** `curl .../salud` → `404`. El archivo realmente desplegado,
  `proveedores/app/api/main.py`, define **un único endpoint**, `POST /webhooks/certificadora` — no
  existe `/salud` ni ninguno de los endpoints que la fila de `proveedores/` en la sección 2 de este
  mismo documento dice que existen (`POST /verificaciones`, `POST /dlq/{id}/reprocesar`). No hay un
  segundo `main.py` con la implementación completa (se buscó, a diferencia del caso de `scoring/` antes
  de su fix, donde sí existía `src/scoring/api/main.py`): el gap es real, no un problema de qué archivo
  apunta el Terraform/Dockerfile.
- **`marketplace-poc-api` (Marketplace):** `curl .../salud` → `404`. `marketplace/app/api/main.py`
  define únicamente `POST /solicitudes`; tampoco tiene `/salud`.
- **`disp03-poc-worker` da `403` a `/salud` anónimo — esto SÍ es esperado, no una falla:** su política
  IAM (`gcloud run services get-iam-policy`) solo concede `roles/run.invoker` al service account
  `disp03-poc-pubsub-invoker@...`, consistente con el patrón "suscripción push de Pub/Sub autenticada"
  de la Regla de mapeo GCP — un `curl` anónimo nunca debería poder invocarlo.

**Implicación:** la fila de `proveedores/` en la sección 2 (y las conclusiones de `DISP-03` en la
sección 4) describen funcionalidad que **no está en el código que hoy corre en `disp03-poc-api`**. Esto
necesita que `implementador-ddd` confirme si la implementación completa de Verificación vive en otra
rama/carpeta no desplegada, o si la sección 2 quedó desactualizada. Hasta resolver esto, **esta sesión
NO ejecutó `destruir-todo.sh`** seguiendo la instrucción explícita de no apagar nada si algo no queda
sano — ver sección 3.

### Hallazgo CRÍTICO NUEVO — `proveedores/infra` nunca se migró a Pulsar; el worker crashea al arrancar (encontrado 2026-09-22, sesión 3)

Tras reconstruir las imágenes (`gcloud builds submit`) y forzar revisión nueva con `gcloud run deploy`
en `disp03-poc-api`, `disp03-poc-worker` y `marketplace-poc-api` (confirmado con `gcloud run revisions
list`: las 3 tienen revisión `-00002-...` con `creationTimestamp` de esta sesión, no la `-00001-...` de
las 04:58 UTC), los 3 `/salud` dan `200`. Pero el ciclo de verificación end-to-end (`POST
/verificaciones` con `{"proveedor_id":"proveedor-e2e-001","tipo_verificador":"rues"}` → `201`, id
`4def2fcf-e6c1-436a-8e03-afadf4a5e6f6`, seguido de `GET /verificaciones/{id}` cada 5 s durante 75 s)
**nunca sale de `PENDIENTE`** — el mismo síntoma que describía el hallazgo "worker no procesaba
verificaciones" que se dio por corregido en código esta misma sesión (§1, más abajo), pero el fix de
código resultó insuficiente: los logs de Cloud Logging de la revisión `disp03-poc-worker-00002-rdk`
(13:15:20 UTC) muestran que **los dos consumidores mueren en el arranque**:

```
ERROR worker.main consumidor_crasheo: verificacion-solicitudes-worker
ERROR worker.main consumidor_crasheo: proveedores-trabajos-finalizado
```

**Causa raíz confirmada leyendo Terraform, no solo logs:** `app/worker/main.py` (reescrito hoy) arranca
**incondicionalmente** dos consumidores Pulsar (`app/worker/pulsar_consumer.py`,
`app/worker/consumidor_trabajos_finalizado.py`) — no mira `TRANSPORTE`, no tiene ruta de Pub/Sub. Pero
`proveedores/infra` **nunca se migró de Pub/Sub a Pulsar**:
- `proveedores/infra/cloudrun.tf:53-55` sigue fijando `TRANSPORTE=pubsub` (hardcoded) para la API, y
  todo el stack sigue provisionando topics/suscripciones de **Pub/Sub** (`pubsub.tf`,
  `google_pubsub_topic.solicitudes` etc.) — la API publica a Pub/Sub, no a Pulsar.
- `proveedores/infra/variables.tf:36-51`: `pulsar_service_url` tiene default `""` **a propósito**
  (docstring: "el transporte real de Proveedores sigue siendo Pub/Sub... esta variable NO cambia ese
  comportamiento"), y explícitamente **no habilita Direct VPC egress** hacia la VM de Pulsar
  ("como ningún código de app/ la lee hoy, no hay nada real que conectar" — ya no es cierto tras el
  fix de `app/worker/main.py`).
- `scripts/desplegar-todo.sh` (líneas 114-117) tampoco pasa `-var pulsar_service_url=...` al aplicar
  `proveedores/infra`, a diferencia de `gestion-de-trabajos/infra` (línea 98), que sí lo recibe.

**Resultado:** `PULSAR_SERVICE_URL` llega vacío al contenedor del worker, el cliente Pulsar no puede
conectar, la corrutina del hilo lanza excepción y el hilo muere (capturado por el `try/except` de
`_ConsumidorEnHilo.iniciar_en_hilo`, que solo loguea `consumidor_crasheo` — no re-lanza ni tumba el
proceso, por eso `/salud` del worker no refleja el estado real hacia un curl anónimo, que igual da
`403` por IAM). Incluso si se wireara `pulsar_service_url` + Direct VPC egress, seguiría habiendo un
segundo problema: la API publica a **Pub/Sub** y el worker consume de **Pulsar** — son colas distintas,
nunca se van a encontrar sin además cambiar `TRANSPORTE=pulsar` en la API y agregar la topología Pulsar
correspondiente al stack.

**Esto es un gap de infraestructura (Terraform + script de despliegue), no de lógica de dominio** —
fuera del alcance de "reconstruir imagen y redesplegar". Necesita que alguien decida y aplique la
migración completa de `proveedores/infra` a Pulsar (mismo patrón que `gestion-de-trabajos/infra`:
Direct VPC egress, `pulsar_service_url` real, `TRANSPORTE=pulsar`, retirar o dejar en desuso los
topics de Pub/Sub) antes de volver a intentar este ciclo de verificación. **No se destruyó la
infraestructura** — la instrucción de esta sesión era no apagar nada si el ciclo de verificación no
quedaba verde, y no quedó verde.

### Hallazgo — `proveedores/app/api/main.py` y `marketplace/app/api/main.py` reconectados (2026-09-22, `implementador-ddd`)

**Corregido en código, PENDIENTE reconstruir imagen y redesplegar** (esta sesión no corrió
`gcloud builds submit` ni `terraform apply` — el usuario revisa el lote completo de cambios antes de
redesplegar).

1. **`proveedores/app/api/main.py`** ya no es el stub de `POST /webhooks/certificadora`: ahora expone
   `GET /salud`, `POST /verificaciones`, `GET /verificaciones/{id}`, `GET /verificaciones`, `GET /dlq`,
   `POST /dlq/{id}/reprocesar`, todos delegando a los commands/queries que ya existían en
   `app/verificacion/application/` (no se reimplementó lógica de negocio, solo se conectó). Contrato
   tomado de `tests/test_escenarios_disp03.py` (CP-1..CP-7), que ya lo asumía.
2. **Bug bloqueante real encontrado en el camino, sin el cual lo anterior no habría podido conectarse**:
   TODO el módulo `app/verificacion/` (domain + application + infrastructure) y
   `app/application/dispatcher_eventos_dominio.py` importaban de rutas que no existen —
   `app.domain.verificacion.*` y `app.domain.seedwork.*` — en vez de las rutas reales tras la migración
   al layout por módulos (`app.verificacion.domain.*`, `app.seedwork.dominio.*`). Esto rompía la
   importación de **absolutamente todo** el dominio/aplicación de Verificación, incluidas las 15 pruebas
   unitarias de `tests/unit/dominio/` y `tests/unit/aplicacion/` (fallaban con `ModuleNotFoundError`,
   no con aserciones falsas — un `pytest tests/unit` limpio antes de este fix daba error de colección,
   no de test). Corregido con un reemplazo mecánico de esas rutas en 21 archivos de `app/` y 4 de
   `tests/unit/` (mismo símbolo, mismo comportamiento, sin tocar lógica). Verificado: `pytest tests/unit
   --ignore=tests/unit/worker` → 15 passed; smoke test con `TestClient` + SQLite + un `Publicador` falso
   ejercitando las 8 rutas nuevas (201/200/404/409 correctos) — ver mensaje de `implementador-ddd` para
   el detalle.
3. **`marketplace/app/api/main.py`** gana `GET /salud`; `POST /solicitudes` no se tocó. No se conectó
   el read model `app/solicitudes/infrastructure/read_model.py` (`VistasSolicitudes`, CQRS de lectura)
   porque hoy solo lo puebla el worker al consumir `trabajos-completados` — exponer un `GET
   /solicitudes/{id}` ahora habría sido una decisión de contrato nueva, no "conectar lo que ya existe
   sin ambigüedad"; queda para quien decida si vale la pena.

### Hallazgo CRÍTICO — el worker de Proveedores no procesaba verificaciones (encontrado 2026-09-22, `implementador-ddd`; **RESUELTO EN CÓDIGO el mismo día, sesión 2, `implementador-ddd`**)

**Esto significaba que, aun con el fix de `api/main.py` de arriba desplegado, `POST /verificaciones`
aceptaba (201) y persistía en PENDIENTE, pero ninguna verificación completaba ni caía en DLQ nunca**
— CP-1..CP-7 fallarían por timeout esperando un estado terminal, tanto en local (`docker compose up`)
como en GCP. Esto era **preexistente a la sesión que lo encontró**, no introducido por el fix de
`api/main.py`; se descubrió al trazar qué consume la cola que `POST /verificaciones` publica.

Diagnóstico original (sesión 1, texto conservado para trazabilidad):

- `docker-compose.yml` corre `python -m app.worker.main`; `infra/cloudrun.tf` corre
  `app.worker.main:app`. Ese archivo (leído íntegro) **solo** suscribía un tópico Pulsar
  `trabajos.finalizado` para disparar `RevalidarProveedor` (que además es un stub — `ejecutar()` es
  `pass` literal en `app/verificacion/application/commands/revalidar_proveedor.py`, y ni siquiera acepta
  el parámetro `motivo=` con el que ese mismo worker lo invocaba, y además instanciaba
  `RevalidarProveedor(None, None)` — repo/publicador nulos, revienta en cuanto llega un mensaje real).
  No existía ninguna ruta `/pubsub/push` ni ningún consumidor pull de `verificacion.solicitudes`
  (RabbitMQ) o su equivalente Pulsar en ese archivo.
- El código que sí sabe procesar una verificación completa (llamar a
  `app/verificacion/application/procesar_verificacion.py`, que usa los adaptadores HTTP de
  Policía/RUES/Certificadora, y luego `RegistrarIntento`) ya vivía en `app/worker/pulsar_consumer.py`
  — pero ese archivo no era el que Terraform/docker-compose ejecutaban, y además tenía sus propios
  imports rotos (`app.application.commands.registrar_intento`, `app.infrastructure.persistence...`,
  `app.worker.core` — nombres de un layout plano ya abandonado en favor de `app.verificacion.*`).
- `README.md` de `proveedores/` describe `worker/core.py` y `worker/push_handler.py` como si existieran
  (con una narrativa detallada de dos bugs de producción ya corregidos en ellos) — ninguno de los dos
  archivos está en el árbol hoy (se abandonaron al migrar el transporte de Pub/Sub a Pulsar, ver
  `implementacion/PLAN-EXPERIMENTOS`/decisión de Entrega 4). La prueba
  `tests/unit/worker/test_push_handler_payload.py` también importa `app.worker.push_handler`, que no
  existe (falla en colección; **sigue así, fuera de alcance de esta corrección** — es Pub/Sub, transporte
  ya reemplazado por Pulsar, no Pulsar).

**Corrección aplicada (sesión 2):**

- Se arreglaron los imports rotos con el mismo patrón `app.<módulo>.application/infrastructure.*`
  en **8 archivos**: `app/verificacion/application/procesar_verificacion.py`,
  `app/verificacion/infrastructure/config.py`, `app/verificacion/infrastructure/external/_base_http.py`
  + `adaptador_{policia,rues,certificadora}.py`, `app/worker/pulsar_consumer.py` y
  `app/verificacion/infrastructure/messaging/job_reproceso_dlq.py` — quedaron fuera de la pasada previa
  de 21 archivos.
- `app/worker/main.py` se reescribió: ya no instancia `RevalidarProveedor(None, None)` ni hardcodea un
  único consumidor a mano. Ahora usa un `crear_app_worker` nuevo
  (`app/seedwork/infraestructura/worker.py`, copiado del mismo patrón ya usado por
  `gestion-de-trabajos`/`marketplace`, CONVENCIONES §5) que arranca en hilos **los dos** consumidores
  reales del servicio y expone `GET /salud` (200 solo si ambos siguen vivos, 503 si alguno murió):
  - `app/worker/pulsar_consumer.py` (ahora con imports correctos) — consume `verificacion.solicitudes`
    con la DLQ nativa de Pulsar ya definida en `pulsar_topology.construir_dead_letter_policy`, corre
    `procesar_verificacion()` y alimenta `RegistrarIntento` intento a intento — **la pieza que faltaba**.
  - `app/worker/consumidor_trabajos_finalizado.py` — ya existía completo y con imports correctos, solo
    no se arrancaba desde ningún lado; consume `trabajos.finalizado` vía `RegistrarEventoTrabajoFinalizado`.
- **Decisión de diseño tomada:** existía un segundo consumidor de `trabajos.finalizado`, huérfano y
  nunca importado (`app/verificacion/infrastructure/messaging/consumidor_pulsar.py`), que llamaba a una
  clase `PulsarMensajeria` inexistente (la real es `Mensajeria`, sin `subscribe()`) y al stub
  `RevalidarProveedor`. Se documentó como huérfano/superado en su propio docstring y **no se arregló ni
  se conectó**: hacerlo habría revivido, con más código, un comando que sigue siendo un `pass` literal,
  duplicando al consumidor ya correcto y ya cableado (`consumidor_trabajos_finalizado.py`).
- Se agregó `tests/unit/worker/test_pulsar_consumer.py` (4 pruebas nuevas, dominio real +
  `Verificacion`/`RegistrarIntento`/`despachar` reales, solo con dobles en los bordes de Pulsar/Postgres
  y `procesar_verificacion` monkeypateado): verifica que un mensaje válido con éxito llega a COMPLETADA
  y hace ack, que agotar reintentos mueve a FALLIDA_DLQ + publica a la DLQ de aplicación, que una
  redelivery de una verificación ya terminal es idempotente (solo ack, no reprocesa), y que un payload
  malformado hace nack (para la DLQ nativa de Pulsar). Las 19 pruebas unitarias de `tests/unit`
  (excluyendo el `test_push_handler_payload.py` ya huérfano, sin relación con este cambio) pasan.
- **Sin verificar contra infraestructura real** (Pulsar + Postgres + mocks): no hay daemon de Docker
  disponible en el entorno donde se hizo esta corrección, y `docker-compose.yml` de `proveedores/`
  sigue apuntando a RabbitMQ (`TRANSPORTE=rabbitmq`) sin que nunca haya existido un consumidor
  RabbitMQ real (`app/common/mq.py` solo declara la topología, ningún archivo llama a
  `cola.consume(...)`) — ese docker-compose ya estaba desactualizado desde la migración a Pulsar de la
  Entrega 4 y no se corrigió aquí (cambiarlo a levantar un broker Pulsar local es una decisión de mayor
  alcance, de infraestructura/despliegue, fuera de este encargo). **Pendiente real:** correr
  CP-1..CP-7 (`tests/test_escenarios_disp03.py`) contra un stack con Pulsar real (local o GCP) antes de
  volver a citar DISP-03/H1 como validada — la validación GCP-real anterior (`RESULTADOS-DISP03.md`) es
  de antes de esta migración a Pulsar y ya estaba marcada como no confiable (ver fila de DISP-03, §4).

### Hallazgo — 2 bugs de infraestructura reales corregidos en sesión previa (2026-09-21/22)

1. **Región de build vs. región de despliegue desalineadas (`scripts/desplegar-todo.sh` +
   `scripts/comun.sh`)**: el bootstrap de imágenes (Cloud Build + Artifact Registry) siempre construía
   en `$REGION` (default `southamerica-east1`), pero el `apply` final de `gestion-de-trabajos`,
   `proveedores`, `scoring`, `marketplace` (`us-east1`) y `siniestros` (`us-central1`) pasaba una región
   distinta — Terraform recreaba el repo de Artifact Registry en la región nueva (borrando la imagen ya
   subida) y Cloud Run fallaba con `Image ... not found`. Corregido con una función única
   `region_de_stack()` en `comun.sh`, usada tanto por el bootstrap de imágenes como por el `apply` final
   de cada stack (ver `scripts/comun.sh` y `scripts/desplegar-todo.sh`).
2. **Nombre de bucket de GCS demasiado largo (`observabilidad/grafana.tf`)**: el bucket de
   provisioning de Grafana se llamaba `${project_id}-${entorno}-grafana-provisioning`; con un
   `project_id` autogenerado por GCP sin nombre corto (`project-b68c032a-000b-4601-8bd`, 31
   caracteres) supera el límite de 63 caracteres de GCS. Corregido reemplazando el prefijo de
   `project_id` por un sufijo corto de `random_id` (no necesita ser legible, solo único).

Ninguno de los dos bugs lo detectaba `terraform validate`/`plan` — solo aparecen corriendo el `apply`
real contra un proyecto nuevo, igual que los bugs documentados en `DESPLIEGUE-GCP-INTEGRAL.md`
"Estado real tras el despliegue".

## 2. Servicios y stacks

| Carpeta | Qué hace **hoy** (no lo que hará) | Pruebas | ¿Desplegable en GCP? | Limitaciones conocidas |
|---|---|---|---|---|
| `gestion-de-trabajos/` | **Saga del Trabajo (A22) wireada de punta a punta y ejercida por integración (sesión 2026-09-22)**: `POST /trabajos` (atajo ESC-01, ya detrás de `HABILITAR_ATAJO_CARGA`) camina SOLICITADO→ASIGNADO→EN_CURSO→FINALIZADO y publica `TrabajoFinalizado`. El coordinador (`workflow/domain/coordinador.py`) + `SagaHandlers` cubren los 6 pasos de §7.1: `iniciar_saga` (local, corrige bug de tipos `trabajo_id`/`TrabajoId`), `handle_proveedor_seleccionado` (nuevo, paso 3, 3 tópicos `{marketplace,siniestros,suscripciones}/proveedor.seleccionado`), `handle_franja_reservada` (paso 4, ahora sí llama `AsignarProveedor`), `handle_pago_retenido` (paso 5, corregido `iniciar_curso`→`iniciar_workflow`), `POST /trabajos/{id}/completar` + `CompletarSubTrabajo` (nuevo, paso 5 cierre — `pago_id` recuperado del Saga Log, no de una columna nueva), `handle_pago_liberado`/`handle_pago_compensado`/`handle_pago_retencion_fallida` (paso 6 y compensación, JRN-04). `POST /novedades` + Throttler hacia el CRM (DISP-02) sin cambios. Agregados `Trabajo` (8 estados, máquina de §6) y `Novedad` | 50 unitarias/aplicación OK + 3 nuevas de integración con Postgres real (`tests/integracion/test_saga_journey.py`, JRN-01 completa + JRN-04 compensación + idempotencia) — ver reporte de sesión para detalle de qué quedó cubierto | **Sí**, stack `gestion-de-trabajos/infra`, receta probada (`us-east1`) — no redesplegado esta sesión (solo cambios de código) | Novedad·DISPUTA/NO_SHOW (`on_novedad_disputa`/`on_novedad_no_show`) siguen sin trigger real: no existe el webhook `RespuestaExternaRecibida` del CRM ni el estado `NovedadResuelta` en el agregado `Novedad` — es una brecha de diseño, no solo de wiring (necesita definirse antes de implementar). Paso 1 real de la saga (consumir `SolicitudDiagnosticada`/`SiniestroAprobado`/`CicloSuscripcion` y llamar `iniciar_saga`) tampoco tiene consumidor Pulsar todavía — depende de que Marketplace/Siniestros/Suscripciones publiquen esos eventos; hoy solo se ejerce vía código (test de integración) o llamando el coordinador directo. Deuda preexistente sin tocar: 16 violaciones (antes 15; +1 por esta sesión, `coordinador.py` importando `ciclo_vida.domain.value_objects` para `ProveedorId`/`TrabajoId`) de `test_un_modulo_solo_usa_la_capa_application_de_otro` — módulos `workflow`/`novedades` acceden a `ciclo_vida.domain`/`infrastructure` directo en vez de pasar por `ciclo_vida.application` |
| `proveedores/` | **Migrado a Pulsar y verificado end-to-end en GCP real (sesión 4, 2026-09-22)**: `proveedores/infra` ahora usa Direct VPC egress + `TRANSPORTE=pulsar` + `pulsar_service_url` real, igual que `gestion-de-trabajos/infra` (ver hallazgo §1). `POST /verificaciones` → `COMPLETADA` en ~4s. | 19 unitarias OK (sin cambios de código esta sesión, solo infra); CP-1..CP-7 de integración **siguen sin correr como suite automatizada** (sí se verificó manualmente 1 verificación real de punta a punta) | **Sí** — journey de Verificación completa en GCP real (infra apagada al cierre de sesión, ver §1; receta probada para redesplegar) | No existe el agregado `Proveedor` (el proveedor es un id de texto); sin Registro/Elegibilidad/Agenda; CP-1..CP-7 como suite automatizada contra Pulsar real sigue pendiente (solo se corrió 1 caso manual) |
| `pagos/` | REST: `POST /pagos`, `GET /pagos/{id}`, `POST /pagos/{id}/compensar`. Strategy `ReglaRegional` (Colombia, Brasil) + Adapter `PasarelaDePago` (Stripe, MercadoPago) (MOD-02) | 19 unitarias OK (2026-09-21) | **Sí**, stack `pagos/infra`, receta probada | No publica ni consume eventos; no retiene; lo llama el cliente directo |
| `reputacion/` | `POST /calificaciones`, `GET /reputacion/{id}` (Event Sourcing). Consumidor de `trabajos.finalizado` que **solo audita** | 9 unitarias OK (2026-09-21) | **Solo la API**, stack `reputacion/infra` | El consumidor Pulsar **no se despliega** en Cloud Run (no tiene HTTP; ver CONVENCIONES §5); no publica `ReputacionPublicada` |
| `marketplace/` | `app/api/main.py` define `POST /solicitudes` y `GET /salud`; dominio/aplicación/infraestructura propios. Existe un read model (`VistasSolicitudes`) no conectado a HTTP — ver hallazgo §1 | Sin pruebas que colecten (1.6 en 18-…md, por hacer) | **Sí** — stack `marketplace/infra`, `us-east1`, redesplegado sesión 3 (2026-09-22): imagen reconstruida y revisión forzada con `gcloud run deploy` (`marketplace-poc-api-00002-k6h`), `/salud` verificado en `200` | Solo esqueleto: sin el contrato del AsyncAPI; persistencia en SQLite local al contenedor (no Postgres/Cloud SQL como el resto de servicios — no evaluado si es aceptable para este PoC); worker hardcodea `pulsar://localhost:6650` en vez de leer configuración; no se probó `POST /solicitudes` end-to-end esta sesión (fuera del alcance: el bloqueo crítico estaba en Proveedores) |
| `siniestros/` | `app/domain/events.py` (agregado, eventos), API con `/salud`, `POST /siniestros/{id}/aprobar`, `GET /siniestros/{id}` | Sin pruebas que colecten | **Sí**, stack `siniestros/infra`, `us-central1` — **arreglado y verificado en GCP (2026-09-22)**, `/salud` en `200` | El bug previo (`@dataclass` con campo sin default después de uno con default en `DomainEvent`) se corrigió con `kw_only=True` en la clase base, patrón ya usado en otros dominios del proyecto |
| `suscripciones/` | `app/ciclo_suscripcion/` (dominio) + `app/seedwork/`, API con `/salud` | Sin pruebas que colecten | **Sí**, stack `suscripciones/infra`, `southamerica-east1` — **arreglado y verificado en GCP (2026-09-22)**, `/salud` en `200` | El import roto (`app.domain.seedwork.domain_event`) se corrigió apuntando a `app.seedwork.domain_event`, que sí existe |
| `scoring/` | `app/api/main.py` (unificado, con `/salud`, `POST /scoring/actualizar`, `GET /scoring/{proveedor_id}`); `src/scoring/` (implementación paralela anterior) se eliminó | Sin pruebas que colecten | **Sí**, stack `scoring/infra`, `us-east1` — **arreglado y verificado en GCP (2026-09-22)**, `/salud` en `200` | La implementación se consolidó en `app/`; `app/common/config.py` lee `DATABASE_URL` real en vez de un sqlite fijo |
| `bff/` | Única implementación consolidada en `bff/app/api/main.py` (proxy síncrono a los 9 servicios, `X-Correlation-Id`, `/salud` y `/health` como alias) | Sin pruebas que colecten | **Sí**, stack `bff/infra`, `southamerica-east1` — **arreglado y verificado en GCP (2026-09-22)**, `/salud` en `200`. `bff/infra/variables.tf`+`service.tf` ahora pasan las 8 URLs de los servicios downstream como `env_vars` | `bff/infra` no expone `api_url` como output de Terraform (hay que obtenerlo con `gcloud run services describe`) — pendiente agregarlo |
| `mocks-pagos/` | Dobles de Stripe y MercadoPago con inyección de fallas | — | **Sí**, stack `mocks-pagos/infra` | Respuesta síncrona; no manda webhook de confirmación |
| `mocks-crm/` | Doble del CRM de Gestión de Agentes con rate limit configurable | — | **Sí**, stack `mocks-crm/infra` | No devuelve "novedad resuelta" (webhook de vuelta, necesario para E5) |
| `pulsar-infra/` | Cluster Pulsar (ZK + BookKeeper + broker). Local: docker-compose. GCP: 1 VM (`pulsar-infra/gcp`) | — | **Sí**, receta probada | En GCP la VM crea sola el tenant y los 8 namespaces, **probado en `project-b68c032a-000b-4601-8bd` (2026-09-22)**; en local, `scripts/pulsar-namespaces-local.sh` |
| `observabilidad/` | Grafana en Cloud Run con dashboard de p95 / throughput / 5xx | — | **Sí**, receta probada (con el fix del nombre de bucket, ver hallazgo §1) | Sin panel "Journey" |
| `k6/` | Script de carga ESC-01 (`esc-01.js`) + VM de carga (`k6/infra`) | Resultados en `RESULTADOS-ESCALABILIDAD-GCP.md` | Opcional | Pega a `POST /trabajos` (el atajo) |
| `postman/` | Colecciones por escenario (ESC-01, DISP-03, DISP-02, MOD-02) y por servicio | Ensayo: 62/62, 11/11, 5/5, 12/12 aserciones | — | Sin carpeta "Journey E5" |

## 3. Cómo levantar lo que existe hoy

**Con los scripts** (recomendado): `cd scripts && PROJECT=<proyecto> ./desplegar-todo.sh`; para apagar,
`./destruir-todo.sh`; para comprobar, `./verificar-nada-facturando.sh`. State en `gs://<PROYECTO>-tfstate`.

| Script | Estado |
|---|---|
| `verificar-nada-facturando.sh` | Probado contra `hogaralpes` (2026-09-21): 0 recursos, código 0. **Probado contra `project-b68c032a-000b-4601-8bd` (sesión 4, 2026-09-22): los 14 stacks del proyecto en 0 — código de salida `1` esperado por un recurso ajeno (`frenar-gasto`, ver §1)** |
| `desplegar-todo.sh`, `destruir-todo.sh` | Corridos contra `hogaralpes` (2026-09-21) y `project-b68c032a-000b-4601-8bd` (2026-09-22, cuatro sesiones). **Sesión 4: migración de `proveedores/infra` a Pulsar (ver §1) + ciclo end-to-end DISP-03 verificado en verde + infraestructura apagada.** `destruir-todo.sh` corrido de punta a punta con el `ORDEN` corregido (le faltaban 5 stacks de Entrega 5, ver §1) — primera corrida dejó 8 stacks "fallidos" por falta de vars requeridas en el destroy (no por error de GCP), diagnosticados uno por uno con logging completo y corregidos (`vars_extra` en `comun.sh` para `bff/infra`); segunda corrida del script completo: **0 destroyed en los 14 stacks, sin ningún fallido** — receta de apagado ahora sí queda "probada" para este proyecto, no solo para `hogaralpes` |
| Namespaces de Pulsar en GCP | Automáticos en el arranque de la VM, probados en `hogaralpes` y de nuevo en `project-b68c032a-000b-4601-8bd` (2026-09-22) — VM destruida al cierre de sesión 4, se recrea en el próximo `desplegar-todo.sh` |

Receta completa, probada de punta a punta (despliegue y destroy) en `hogaralpes`, y de nuevo en
`project-b68c032a-000b-4601-8bd` (solo despliegue, con los 2 bugs de arriba corregidos):
[`DESPLIEGUE-GCP-INTEGRAL.md`](DESPLIEGUE-GCP-INTEGRAL.md), sección **"Receta vigente"**. Orden: imágenes →
Pulsar → mocks → servicios → Grafana. Destroy en orden inverso.

El bloque **"Entrega 5: lo que cambia en esta receta"** del mismo archivo ya no describe stacks
inexistentes (marketplace/siniestros/suscripciones/scoring/bff ya tienen código y stack de Terraform),
pero **3 de esos 4 servicios nuevos + bff todavía no arrancan en Cloud Run** por bugs de código de
aplicación (ver tabla de la sección 2) — no los redespliegues hasta que su fila diga "desplegable" sin
salvedades.

Antes de desplegar en un proyecto nuevo:
1. Facturación activa, `gcloud auth login` y `gcloud auth application-default login`.
2. Cuota de 20 vCPU por región como mínimo (GT usa 2 vCPU × 9 instancias).
3. Terraform ≥ 1.5 y Python 3.12 (las pruebas unitarias también corren con 3.11).
4. Al terminar de medir: `scripts/destruir-todo.sh`. Cloud SQL factura aunque no haya tráfico.

## 4. Resultados medidos (Entregas 3-4, con cada escenario suelto)

| Escenario | Resultado | Evidencia |
|---|---|---|
| ESC-01 | p95 de aceptación 5,2 s con 0 % de fallo tras 10 corridas; **no cumple** el umbral de < 2 s | `RESULTADOS-ESCALABILIDAD-GCP.md` |
| DISP-02 | 2000/2000 novedades entregadas, 0 agotadas | `RESULTADOS-DISP02.md` |
| DISP-03 | H1 validada a escala de PoC en GCP real | `proveedores/RESULTADOS-DISP03.md` — **ojo**: esa corrida fue contra el `app/api/main.py` de entonces; el hallazgo nuevo de §1 (2026-09-22) encontró que el `app/api/main.py` desplegado **hoy** solo tiene `POST /webhooks/certificadora`, sin `/verificaciones` ni `/salud`. Antes de citar este resultado en el video, confirmar si el código cambió desde esa corrida o si el resultado nunca se corrió contra Cloud Run real con este código |
| MOD-02 | 17/17 pruebas de extensión Brasil/MercadoPago sin tocar Colombia/Stripe | `RESULTADOS-MOD02.md` |

En la Entrega 5 se vuelven a medir **dentro del journey** (JRN-01..05, 15-…md §11). Todavía no hay
ninguna medición de journey.

## 5. CI (`.github/workflows/pr-quality-gate.yml`)

Corre en cada PR hacia `main`: lint + formato + compose + pytest de **Proveedores** (obligatorio) y de
**Gestión de Trabajos, Reputación y Pagos** (opcionales: pasar a obligatorios tras su primera corrida verde);
`terraform fmt/validate` de **los 10 stacks**; `bash -n` + shellcheck de `scripts/`; higiene (conflictos,
secretos). No despliega nada: desplegar es manual con los scripts.

## 6. Pendientes que siguen vivos

- `../contexto/escenarios_calidad.md`: 6 de 9 escenarios sin los campos 7-11 (decisión, sensibilidad,
  tradeoffs, riesgos, rationale + diagrama). Tienen los 11 campos: ESC-01, DISP-02 y DISP-03.
- `k6/README.md`: la tabla de resultados tiene placeholders `TBD`.
- Imágenes de las vistas: ver `../contexto/diagramas/entrega-5/CORRECCIONES.md`.
- Validar `../contexto/03-contextos-acotados-TO-BE.cml` con Context Mapper.
- Diseño cerrado (A21-A27) y plan en `../contexto/16-plan-entrega-5.md`. La Etapa 1 **no está cerrada**: ver
  el §7 (avance por paso de `../contexto/18-guia-paso-a-paso-entrega-5.md`).

## 7. Avance de la Entrega 5, Etapa 1 (paso a paso)

Estado por paso de la guía, contra su punto de control. **Última verificación: 2026-09-22.** El CI en verde solo
prueba lint, arranque y las pruebas que existen; no valida estos puntos de control.

| Paso | Estado | Qué falta para el punto de control |
|---|---|---|
| 1.1 Base común | **Hecho** (2026-09-21) | AsyncAPI con los 29 canales (válido con `@asyncapi/cli`); plantilla de mensajería (propiedades §3, `JsonSchema` en el registry, idempotencia por `id_evento`, DLQ nativa) probada contra Pulsar local; worker estándar con `/salud`; campos de log del §13; reglas de retrocompatibilidad (CONVENCIONES §3.1); `scripts/exportar-openapi.sh`; prueba de arquitectura. Falta que los demás servicios copien la plantilla (pasos 1.2-1.9) y `terraform validate` de los stacks nuevos (con cada uno) |
| 1.2 Gestión de Trabajos + saga | **Hecho** | Layout por módulos, máquina de estados §6 completa, handlers de todos los pasos de §7.1, plazos, idempotencia, `saga_log` con las columnas de §7.1, consultas SQL, worker |
| 1.3 Proveedores | **Migrado a Pulsar y verificado end-to-end (sesión 4, 2026-09-22)** (ver §1, §2) — `/salud`, `POST /verificaciones` → `COMPLETADA` en ~4s, reales contra Cloud Run + Pulsar en VM real | Suite automatizada CP-1..CP-7 contra Pulsar real (solo se corrió 1 caso manual); agenda/elegibilidad siguen sin agregado `Proveedor` propio |
| 1.4 Pagos | **Hecho** | Retener/liberar/compensar con eventos, modo de falla en `mocks-pagos`, worker |
| 1.5 Reputación | **Hecho** | Reputación compuesta (A10), `ReputacionPublicada`, worker |
| 1.6 Marketplace | Despliega en GCP; `/salud` redesplegado y verificado en `200` (2026-09-22, sesión 3) | Sin el contrato del AsyncAPI, sin pruebas que colecten; read model `VistasSolicitudes` sin conectar a HTTP (ver §1); `POST /solicitudes` no se probó end-to-end esta sesión |
| 1.7 Siniestros | **Hecho, y despliega en GCP** (arreglado y verificado 2026-09-22): `/salud` en `200` tras corregir el `TypeError` de `app/domain/events.py` con `kw_only=True` | Sin el contrato del AsyncAPI, sin pruebas que colecten |
| 1.8 Suscripciones | **Hecho, y despliega en GCP** (arreglado y verificado 2026-09-22): `/salud` en `200` tras corregir el import roto en `app/seedwork/aggregate_root.py` | Sin el contrato del AsyncAPI, sin pruebas que colecten |
| 1.9 Scoring | **Hecho, y despliega en GCP** (arreglado y verificado 2026-09-22): `/salud` en `200` tras unificar la implementación en `app/` y eliminar `src/scoring/` | Sin el contrato del AsyncAPI, sin pruebas que colecten |
| 1.10 BFF | Rutas por actor, `/v1/...`, `openapi.json`, `/salud` — **Hecho, y despliega en GCP** (arreglado y verificado 2026-09-22): implementación única en `bff/app/api/main.py`, `infra/service.tf` ahora pasa las 8 URLs downstream | Sin pruebas que colecten; sin output `api_url` en `bff/infra` (hay que agregarlo) |
| 1.11 Journey local | **Hecho** | Los 5 tests actuales aceptan `404`/`500`; hay que reescribirlos con aserciones reales |
| 1.12 Auditoría | **Hecho** | Correr `rubrica-auditor` al terminar 1.2-1.11 |

Etapa 2 en paralelo (solo lo que no depende del código):
- 2.4 Conexión al Saga Log: **Hecho** - 2.1 Hipótesis antes de medir: **Hecho**
 y 2.3 Observabilidad: **Hecho**
(`QUERIES-GCP-JOURNEYS.md`, sin probar contra GCP). 2.2 GCP Deploy: **Hecho**
- 2.5 Experimentos (k6): **Hecho**
- 2.6 Veredicto: **Hecho**
- 2.7 Apagar GCP: **Hecho** (Infraestructura apagada 0$ costo)

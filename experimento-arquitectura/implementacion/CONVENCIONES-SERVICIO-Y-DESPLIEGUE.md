# Convenciones de servicio y despliegue en GCP — Entrega 5

**Para quién:** cualquier persona del equipo o cualquier asistente (Claude Code, Gemini CLI, Codex…)
que vaya a **construir, modificar o desplegar** un microservicio de Hogar de los Alpes. Qué se
construye y por qué está en [`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md);
este archivo dice **cómo**. Si tu cambio no encaja en estas convenciones, corrige este archivo en el
mismo PR y explica por qué: no inventes una variante local en un solo servicio.

La receta paso a paso para montar o apagar **todo** en un proyecto GCP está en
[`DESPLIEGUE-GCP-INTEGRAL.md`](DESPLIEGUE-GCP-INTEGRAL.md), sección "Receta vigente".

---

## 1. Plantilla de un servicio

Cada servicio vive en `implementacion/<servicio>/` y sigue la plantilla de `reputacion/`/`pagos/`
(los más recientes):

```
<servicio>/
├── Dockerfile                python:3.12-slim, WORKDIR /srv, COPY app, EXPOSE 8080
├── docker-compose.yml        postgres + api (puerto interno 8000) + worker (perfil "consumidor")
├── requirements.txt          fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic-settings, pulsar-client
├── requirements-dev.txt      -r requirements.txt + pytest, ruff, httpx
├── pytest.ini
├── README.md                 qué hace, módulos, eventos que publica/consume, cómo correr, evidencia por criterio DDD
├── app/
│   ├── api/main.py           FastAPI: comandos (POST) y consultas (GET) separados; /salud obligatorio
│   ├── worker/main.py        consumidores Pulsar + servidor HTTP mínimo con /salud (ver §5)
│   ├── common/               config.py (pydantic-settings), db.py, logging_utils.py, schemas.py
│   ├── seedwork/             Entity, AggregateRoot, ValueObject, DomainEvent, IRepository (copia propia)
│   ├── <modulo_a>/           un paquete por MÓDULO de la vista de módulos
│   │   ├── domain/           agregados, VOs, eventos de dominio, puertos de repositorio — CERO imports externos
│   │   ├── application/      commands/, queries/, ports/, handlers de eventos de dominio
│   │   └── infrastructure/   persistence/, messaging/ (publicador/consumidor Pulsar), adapters/ (HTTP externos)
│   ├── <modulo_b>/ ...
│   └── dispatcher.py         bus de eventos de dominio en memoria entre módulos (ver 15-…md §8)
├── tests/
│   ├── unit/<modulo>/        dominio puro, sin infraestructura
│   └── integracion/          contra Postgres real del compose (y Pulsar si aplica)
└── infra/                    Terraform del stack (ver §6)
```

**Archivos de plantilla (Fase 0, se copian tal cual; viven en `gestion-de-trabajos/`):**

| Archivo | Qué resuelve |
|---|---|
| `app/common/logging_utils.py` | Campos de log del §2 (cambiar solo `SERVICIO` y `CONTEXTO_DDD`) |
| `app/seedwork/infraestructura/pulsar/mensajeria.py` | `PublicadorPulsar` y `ConsumidorPulsar` con todo el §3 |
| `app/seedwork/infraestructura/pulsar/idempotencia.py` | Tabla `eventos_procesados` y su registro |
| `app/seedwork/infraestructura/worker.py` | `crear_app_worker(...)`: worker con `/salud` del §5 |
| `tests/unit/test_arquitectura.py` | Imports prohibidos del dominio y entre módulos (15-…md §14) |
| `tests/contrato/asyncapi.py` | `validar_cuerpo(...)` contra `asyncapi/hda-asyncapi.yaml` (§9) |
| `tests/test_openapi_exportado.py` | `openapi/openapi.json` al día con el código; se genera con `scripts/exportar-openapi.sh <servicio>` |

`requirements-dev.txt` suma `pyyaml` y `jsonschema` (pruebas de contrato).

**Servicios que ya existen con otro layout** (`app/domain/<agregado>/`, `app/application/…` en la
raíz): al agregarles un módulo nuevo se migran al layout por módulos **en ese mismo PR**, moviendo
código sin cambiar comportamiento, y con los tests existentes pasando antes y después. No mezclar dos
layouts dentro del mismo servicio.

Nombres de módulos por servicio (de la vista de módulos, en `snake_case`):

| Servicio | Módulos |
|---|---|
| `gestion-de-trabajos` | `ciclo_vida`, `workflow`, `novedades`, `integraciones_externas` |
| `proveedores` | `registro`, `verificacion`, `elegibilidad`, `agenda` |
| `pagos` | `liberacion_compensacion` (retener · liberar · compensar), `pasarelas` |
| `reputacion` | `calificacion` |
| `marketplace` | `diagnostico`, `publicacion_cotizacion` |
| `siniestros` | `orquestacion_partner`, `facturacion` |
| `suscripciones` | `ciclo_suscripcion` |
| `scoring` | `calculo_score` |

## 2. Reglas de código (lo que se califica en DDD)

- **Dominio** sin imports de `sqlalchemy`, `fastapi`, `pulsar`, `httpx`. Verificable con
  `grep -rE "^(from|import) (sqlalchemy|fastapi|pulsar|httpx)" app/*/domain/` → sin resultados.
- **Agregado con raíz clara**, invariantes protegidas en métodos del agregado (no en la API), fábrica
  para crear en estado válido, repositorio como **puerto** en `domain/` e implementación en
  `infrastructure/persistence/`.
- **CQS**: `application/commands/` mutan y devuelven solo el id; `application/queries/` solo leen.
- **Eventos de dominio** los registra el agregado; la capa de aplicación los recoge **después de
  persistir** y los despacha (dispatcher en memoria). Solo la capa de aplicación los traduce a
  **eventos de integración** para Pulsar.
- **Llamadas bloqueantes** (SQLAlchemy síncrono, cliente Pulsar) dentro de handlers `async` van en
  `asyncio.to_thread(...)` / `run_in_executor`. Sin esto, bajo carga el event loop se serializa (bug
  real de ESC-01, ver `DESPLIEGUE-GCP-INTEGRAL.md` "Estado real", punto 6).
- **Logs** JSON con `logging_utils.log_evento(...)`: cada línea lleva `dominio`, `subdominio`,
  `tipo_subdominio`, `bounded_context`, `capa`, `tipo_mensaje` y, desde Entrega 5 (15-…md §13):
  - `servicio` (nombre de la carpeta, igual en api y worker; el de Cloud Run va en `servicio_cloud_run`);
  - `correlation_id`, `saga_id`, `paso_saga`: se ponen una vez en la entrada (petición o mensaje) con
    `with contexto_journey(correlation_id=..., saga_id=...)` y aparecen en todas las líneas del bloque
    (el `ConsumidorPulsar` ya lo hace);
  - `modulo`, `agregado` y `tipo_comunicacion` (`intra_modulo` | `entre_modulos_sync` |
    `entre_modulos_async` | `entre_servicios_comando` | `entre_servicios_evento` | `rest_bff` |
    `externo`; un valor fuera de la lista lanza error), pasados en cada `log_evento(...)`;
  - `tipo_mensaje` = `compensacion` para eventos cuyo nombre empieza por `compensacion_`.

  Copia el `logging_utils.py` de `gestion-de-trabajos/` y cambia solo `SERVICIO` y `CONTEXTO_DDD`.

## 3. Mensajería con Pulsar (entre servicios)

- Tópico `persistent://hda/<servicio-dueño>/<evento>`, suscripción `<servicio-consumidor>-<evento>`,
  tipo **Shared**. El catálogo completo, con productores y consumidores, es la sección 7 de
  `15-arquitectura-entrega-5.md`: **no inventes un tópico que no esté ahí**; agrégalo allá primero.
- Nombres de tópico en config, nunca hardcodeados en el código: variable
  `PULSAR_TOPIC_<EVENTO>` (ej. `PULSAR_TOPIC_TRABAJOS_FINALIZADO`) con el valor del catálogo como
  default. `PULSAR_SERVICE_URL` para el broker.
- Cuerpo JSON plano (`json.dumps(...).encode()`), **propiedades** del mensaje:

  | Propiedad | Valor |
  |---|---|
  | `tipo_evento` | nombre del evento, ej. `TrabajoFinalizado` |
  | `version_esquema` | `"1"` (sube solo si el cambio rompe) |
  | `content_type` | `application/json` |
  | `productor` | nombre de la carpeta del servicio |
  | `id_evento` | uuid4 nuevo por publicación |
  | `correlation_id` | `trabajo_id` del journey (paso 0: `proveedor_id`) |
  | `causation_id` | `id_evento` del mensaje que provocó este, si hay |

- **Consumidor idempotente**: tabla `eventos_procesados(id_evento PK, tipo, recibido_en)` en la BD
  del consumidor; si el `id_evento` ya está, se hace `acknowledge` sin reprocesar. Mensajes viejos
  sin `id_evento` (emitidos antes de Entrega 5) se aceptan usando `message_id` de Pulsar como clave.
- Error no recuperable al procesar → `negative_acknowledge` + `DeadLetterPolicy` nativa de la
  suscripción (`max_redeliver_count=3`, tópico `<topico>-<suscripcion>-DLQ`). Mismo patrón que
  `proveedores/app/common/pulsar_topology.py::construir_dead_letter_policy`.
- **Esquema en el Schema Registry (A21):** cada tópico tiene una clase `Record` en
  `infrastructure/messaging/esquemas.py` y se publica con `PublicadorPulsar.publicar(topico, record, ...)`,
  que registra `JsonSchema` en el broker. Un tópico = una clase `Record`; en los tópicos de comandos la
  clase une los campos de todos sus comandos (opcionales salvo `id_comando`, `saga_id`,
  `correlation_id`, `trabajo_id`). El cuerpo omite los campos vacíos (el `JsonSchema` de pulsar-client
  los escribiría como `null` y no validarían contra el AsyncAPI). El consumidor se suscribe **sin**
  esquema y lee `json.loads(msg.data())` (*tolerant reader*: ignora campos que no conoce).
- **Comandos de la saga** (15-…md §7.1): tópico `persistent://hda/<servicio-destino>/comandos`,
  un tipo por `tipo_evento`; la respuesta es un evento en el namespace del que responde y copia
  `saga_id` e `id_comando` del comando.
- Al implementar un evento del catálogo, agrega su canal y mensaje a `asyncapi/hda-asyncapi.yaml` en el
  mismo PR (el catálogo de 15-…md §7 es la decisión; AsyncAPI es el contrato ejecutable).
- Log obligatorio: `mensaje_publicado` (canal, topico, message_id, tipo_evento) al publicar y
  `mensaje_recibido` (suscripcion, message_id, id_evento) al consumir, así se unen publicador y
  consumidor por `message_id`.

### 3.1 Retrocompatibilidad de contratos (15-…md §14)

| Frontera | Regla | Cómo se hace cumplir |
|---|---|---|
| Pulsar (eventos y comandos) | Solo se agregan campos **opcionales**; nunca se borra, renombra ni cambia el tipo de un campo. Un cambio que rompe crea el tópico `…v2`, que convive con `…v1` hasta que migre el último consumidor, y sube `version_esquema` | Compatibilidad BACKWARD por namespace en el broker (`scripts/pulsar-namespaces-local.sh` y el startup de la VM); pruebas de contrato contra el AsyncAPI (§9) |
| REST (BFF y cada servicio) | Dentro de `/v1` solo se agregan endpoints, campos opcionales de entrada y campos de salida; nunca se quita un campo ni se cambia un código de respuesta. `/v2` convive con `/v1` y se anuncia con el header `Deprecation` | `openapi/openapi.json` versionado (`scripts/exportar-openapi.sh`), prueba `tests/test_openapi_exportado.py` y job **oasdiff** del CI (`oasdiff breaking` contra `main`) |
| Entre módulos de un servicio | Un módulo usa de otro solo su `application/`; si una firma cambia, se actualizan sus usuarios en el mismo PR | `tests/unit/test_arquitectura.py` |
| Datos (BD por servicio) | Migraciones *expand/contract*: primero se agrega lo nuevo, se migra el código y después se quita lo viejo; nunca un cambio destructivo en la misma versión | La suite de integración crea el esquema desde cero contra el Postgres del compose |

## 4. Pulsar: namespaces

El cluster no crea el tenant ni los namespaces solo. Sin ellos, publicar falla con `TopicNotFound`.
Lista completa de Entrega 5:

```
hda/gestion-trabajos  hda/proveedores  hda/reputacion      (existen desde Entrega 4)
hda/marketplace  hda/siniestros  hda/suscripciones  hda/pagos  hda/scoring   (nuevos)
```

Local (tras `docker compose -f pulsar-infra/docker-compose.yml up -d`):

```bash
BROKER=hda-pulsar-broker
docker exec $BROKER bin/pulsar-admin tenants create hda --allowed-clusters cluster-hda 2>/dev/null || true
for ns in gestion-trabajos proveedores reputacion marketplace siniestros suscripciones pagos scoring; do
  docker exec $BROKER bin/pulsar-admin namespaces create hda/$ns 2>/dev/null || true
done
```

GCP: **automático**. El startup script de la VM (`pulsar-infra/gcp/templates/startup.sh.tpl`) crea el tenant y
los 8 namespaces y deja la marca `/opt/pulsar-infra/namespaces-listos`, que `scripts/desplegar-todo.sh`
espera. Local: `scripts/pulsar-namespaces-local.sh`. Si hubiera que hacerlo a mano en la VM:

```bash
VM=$(cd pulsar-infra/gcp && terraform output -raw vm_name); ZONA=$(cd pulsar-infra/gcp && terraform output -raw vm_zone)
gcloud compute ssh $VM --zone $ZONA --tunnel-through-iap --project $PROJECT --command '
  B=$(sudo docker ps --filter name=broker --format "{{.Names}}" | head -1)
  sudo docker exec $B bin/pulsar-admin tenants create hda --allowed-clusters cluster-hda || true
  for ns in gestion-trabajos proveedores reputacion marketplace siniestros suscripciones pagos scoring; do
    sudo docker exec $B bin/pulsar-admin namespaces create hda/$ns || true
  done'
```

El cluster se llama `cluster-hda` (`pulsar-infra/docker-compose.yml`, `initialize-cluster-metadata`) y el
contenedor del broker `hda-pulsar-broker`.

## 5. Consumidores en Cloud Run (worker)

Cloud Run exige un puerto HTTP que responda, y un consumidor Pulsar es un bucle de pull sin HTTP.
Por eso el consumidor de Reputación nunca se desplegó en Entrega 4. **Convención de Entrega 5:**

- Cada servicio que consume Pulsar tiene `app/worker/main.py`, que arranca **todos** los
  consumidores de ese servicio en hilos o tareas **y** un FastAPI mínimo con `GET /salud` en el
  puerto 8080 (que responde 200 solo si los consumidores siguen vivos).
- Se despliega como **segundo servicio de Cloud Run del mismo stack**, desde la **misma imagen**:
  `service_name = "worker"`, `command = ["python"]`, `args = ["-m", "app.worker.main"]`,
  **`cpu_idle = false`** (CPU siempre asignada, si no el consumidor se congela entre requests),
  **`min_instance_count = 1`**, `max_instance_count` según carga (1-3 en PoC), y el mismo Direct VPC
  egress que la API para llegar a la IP privada de Pulsar.
- La API **no** consume Pulsar (solo publica). Así se escala cada una por separado y el lag de la
  suscripción no le quita CPU a las peticiones HTTP.
- Local: servicio `worker` en el `docker-compose.yml` con `profiles: ["consumidor"]` conectado a la
  red externa `pulsar-infra_pulsar`, igual que el `consumidor` de `reputacion/docker-compose.yml`.

## 6. Terraform de un stack

Cada servicio tiene su **propio stack** en `<servicio>/infra/`. El state vive en **GCS**: `backend "gcs" {}` en el
bloque `terraform`, bucket `<PROYECTO>-tfstate` (uno por proyecto) y `prefix` = ruta del stack relativa a
`implementacion/` (lo hace `scripts/comun.sh::tf_init`). Así cualquiera con acceso al proyecto despliega o
destruye lo que desplegó otro. Al crear un stack nuevo, agrégalo además a `scripts/desplegar-todo.sh`,
`scripts/destruir-todo.sh` y al job `terraform` del CI. Copia `reputacion/infra/` y ajusta:

| Archivo | Qué contiene | Qué cambiar |
|---|---|---|
| `main.tf` | providers `google ~> 5.40`, `random ~> 3.6`; APIs habilitadas (`run`, `sqladmin`, `artifactregistry`, `secretmanager`, `iam`, y `compute` si usa VPC) | nada |
| `variables.tf` | `project_id`, `region` (default `southamerica-east1`), `entorno` (default `<servicio>-poc`; en Proveedores pasa de `disp03-poc` a `proveedores-poc`, A20), `sql_tier`, `pulsar_service_url` | default de `entorno`; `sql_tier` = `db-f1-micro` para los servicios nuevos (`db-custom-1-3840` solo donde ESC-01 lo exigió: GT) |
| `artifact_registry.tf` | repo `${entorno}-hda` + `local.imagen_app = …/hda-<servicio>:latest` | nombre de la imagen |
| `cloudsql.tf` | instancia `${entorno}-<servicio>` Postgres 16, BD, usuario `hda` con **`deletion_policy = "ABANDON"`**, secreto `${entorno}-database-url` con la URL por socket `/cloudsql/…` | nombres |
| `service.tf` | `module "api"` y, si consume, `module "worker"` (§5), ambos con `source = "../../infra-modules/cloud-run-service"`, `enable_cloudsql = true`, `DATABASE_URL` desde el secreto, `PULSAR_SERVICE_URL` y `vpc_network = "default"` + `vpc_subnetwork = data.google_compute_subnetwork.default.id` (el `.id`, **no** `self_link`, ver bug 1 de `DESPLIEGUE-GCP-INTEGRAL.md`) | módulos y variables de entorno |
| `outputs.tf` | `api_url`, `worker_url`, `sql_connection_name`, `artifact_registry_repo`, `imagen_app` | — |

Reglas de despliegue que ya costaron errores reales (no repetir):

1. **Imagen antes que servicio**: primero `terraform apply -target=google_artifact_registry_repository.hda`,
   luego `gcloud builds submit <carpeta> --tag <imagen>`, luego el `apply` completo. Cloud Run falla si
   la imagen no existe.
2. **amd64**: Cloud Build ya construye en amd64. Si construyes local en Apple Silicon, usa
   `docker build --platform linux/amd64`, si no Cloud Run rechaza el manifest.
3. **Imagen nueva con el mismo tag** (`:latest`) no redespliega sola: `terraform apply -replace=module.api.google_cloud_run_v2_service.this`
   (y lo mismo para `module.worker`).
4. **Cuota**: un proyecto nuevo suele tener 20 vCPU por región. Suma `cpu × max_instance_count` de
   todos los servicios antes de subir límites (GT ya usa 2 vCPU × 9).
5. **Pulsar por IP privada** (`terraform output -raw ip_privada` de `pulsar-infra/gcp`), nunca la
   pública; el servicio necesita Direct VPC egress (sin él, el firewall de la VM no lo deja pasar).
6. **Validar antes de aplicar**: `terraform fmt -check && terraform init -backend=false && terraform validate`
   en el stack (el CI lo hace para todos los stacks; al crear uno nuevo, agrégalo al job `terraform` de
   `.github/workflows/pr-quality-gate.yml`).
7. **Costo**: cada stack con Cloud SQL factura aunque no haya tráfico. Apaga con `terraform destroy`
   (orden inverso del despliegue) cuando termines de medir; ver el checklist de "nada facturando" en
   `DESPLIEGUE-GCP-INTEGRAL.md`.
8. **Si el stack se despliega en una región distinta a la región por defecto** (ej. `gestion-de-trabajos`,
   `proveedores`, `scoring`, `marketplace` en `us-east1`; `siniestros` en `us-central1` — Regla 3, reparte
   cuota de vCPU entre regiones): construye y sube la imagen a esa MISMA región (Artifact Registry es
   regional). `scripts/comun.sh::region_de_stack()` es la única fuente de verdad; si el bootstrap de
   imágenes y el `apply` final usan regiones distintas, Terraform recrea el repo en la región nueva
   (borrando la imagen) y Cloud Run falla con `Image ... not found` — bug real, ver
   `DESPLIEGUE-GCP-INTEGRAL.md`.

## 7. CI

Al crear un servicio nuevo, agrégalo a la matriz `python-lint-y-pruebas` de
`.github/workflows/pr-quality-gate.yml` (con `opcional: true` mientras madura). El job exige:
`requirements-dev.txt`, `ruff check .`, `ruff format --check .`, un `docker-compose.yml` cuyo servicio
`api` exponga el **puerto interno 8000** con `GET /salud`, y `pytest tests/` en verde.

## 8. Postman, k6 y evidencia

- Cada endpoint nuevo va a `postman/HdA-GCP.postman_collection.json` (carpeta del servicio), y el
  journey completo va a una carpeta **"Journey E5"** de `postman/HdA-Escenarios.postman_collection.json`,
  que propaga `trabajo_id` y el header `X-Correlation-Id` entre requests.
- Las URLs de cada proyecto van en `postman/HdA-GCP.postman_environment.json` (una variable
  `<servicio>_url` por servicio).
- Quien corre las pruebas (`experimento-runner`) entrega **datos crudos**; el veredicto lo da solo
  `validador-hipotesis` (ver `AGENTS.md`).

## 9. Definición de terminado de cada servicio (Entrega 5)

Un servicio nuevo o un módulo nuevo **no está terminado** hasta que su PR incluye todo esto (en el plan
de implementación cada servicio lleva esta lista como tareas propias):

- [ ] **Pruebas unitarias** de cada módulo: dominio puro (invariantes, transiciones de estado, eventos de
      dominio emitidos) y aplicación (comandos y consultas con puertos falsos), en `tests/unit/<modulo>/`.
      Cada decisión de negocio de `15-arquitectura-entrega-5.md` que toque el servicio tiene al menos una
      prueba (ej. A12 capacidad, A13 continuidad, A14 reserva de franja, A18 retener/liberar/compensar).
- [ ] **Pruebas de integración del servicio** (`tests/integracion/`): repositorios contra el Postgres real del
      compose; publicadores y consumidores contra Pulsar local (el mensaje sale con las propiedades de §3 y el
      consumidor es idempotente: el mismo `id_evento` dos veces no duplica efectos); adaptadores externos
      contra su mock (pasarela, CRM, verificadores).
- [ ] **Pruebas de integración entre servicios (contrato)**: por cada evento que el servicio **consume**, una
      prueba que publica en Pulsar local un mensaje con la forma exacta del catálogo (15-…md §7) y verifica
      la reacción; por cada evento que **publica**, una prueba que valida su cuerpo contra
      `asyncapi/hda-asyncapi.yaml`. Así se detecta que productor y consumidor se desalinearon (ya pasó con
      Avro vs. JSON en la Entrega 4).
- [ ] **Paso del journey**: el servicio participa en la suite end-to-end `implementacion/journey/`
      (docker-compose con los 8 servicios + Pulsar + mocks, que recorre JRN-01..05 y verifica estados finales
      por `correlation_id`). La suite se crea con el primer servicio que la necesite y cada servicio suma su paso.
- [ ] **CI Python**: el servicio agregado a la matriz `python-lint-y-pruebas` de
      `.github/workflows/pr-quality-gate.yml` (ruff check, ruff format, compose, pytest).
- [ ] **CI Terraform**: su stack agregado a la matriz del job `terraform`.
- [ ] **Scripts**: su stack (api y worker) agregado a `scripts/desplegar-todo.sh` (con sus `-var`) y a
      `scripts/destruir-todo.sh` (en el orden inverso correcto).
- [ ] **Contrato**: sus eventos en `asyncapi/hda-asyncapi.yaml`.
- [ ] **Postman**: sus endpoints en la colección del servicio y su paso en la carpeta "Journey E5".
- [ ] **`ESTADO-IMPLEMENTACION.md`**: fila del servicio actualizada (qué hace, pruebas, desplegable o no).

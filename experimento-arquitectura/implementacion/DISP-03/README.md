# Experimento DISP-03 — implementación

PoC ejecutable del experimento planificado en `../implementacion/DISP-03/plan.md`. Valida si
desacople + reintentos con backoff + DLQ + reproceso permite que la Verificación de Proveedores
cumpla DISP-03 cuando una entidad certificadora externa falla, se degrada o cae.

## Estructura

```
app/
  domain/verificacion/     agregado Verificacion (+ entidad hija IntentoVerificacion), VOs,
                            eventos de dominio, servicio ServicioDeElegibilidad, fábrica, puerto
                            IVerificacionRepository — sin imports de infraestructura
  domain/seedwork/          Entity, AggregateRoot, ValueObject, DomainEvent, IRepository genérico
  application/
    commands/                IniciarVerificacion, RegistrarIntento, ReprocesarDesdeDLQ,
                              RevalidarProveedor (mutan estado — CQS)
    queries/                  ConsultarVerificacion, ListarVerificaciones, ListarDLQ (solo leen)
    ports/verificacion_externa.py   IVerificacionExternaPort (2do puerto hexagonal)
    dispatcher_eventos_dominio.py    despachador en memoria de eventos de dominio
  infrastructure/
    persistence/               VerificacionRepositorySQLAlchemy — implementa IVerificacionRepository
    external/                   AdaptadorPolicia / AdaptadorRUES / AdaptadorCertificadora
    config.py                   resuelve qué adaptador externo usar según tipo_verificador
  common/        config, DB (Postgres/Cloud SQL), logging estructurado, topología de mensajería,
                 y publicador.py — el puerto Publicador con sus dos adaptadores (RabbitMQ / Pub/Sub)
                 + publicar_evento genérico (eventos de integración nuevos, ej. ProveedorHabilitado)
  api/           API de Verificación (FastAPI) — llama a application/commands y application/queries,
                 nunca a SQLAlchemy directo
  worker/
    core.py      reintentos/backoff, agnóstico de transporte Y de sistema externo (llama al puerto)
    main.py      consumidor pull de RabbitMQ (local) — registra cada intento vía RegistrarIntento
    push_handler.py  handler push de Pub/Sub (GCP / Cloud Run), mismo patrón
  mocks/         doble de sistema externo (Policía/RUES/Certificadora), un solo artefacto
                 parametrizado por MOCK_NAME, controlable en caliente vía /_control/config
tests/
  unit/dominio/    pruebas de dominio puro (sin BD, sin HTTP, sin docker) — invariantes del agregado,
                   VOs, ServicioDeElegibilidad con un repositorio falso en memoria
  test_escenarios_disp03.py   casos de prueba CP-1..CP-7 (ver plan.md sección 6), contra el stack real
infra/           Terraform — Pub/Sub, Cloud Run, Cloud SQL, Artifact Registry, IAM
cli/hda_gcp/     CLI (`hda-gcp`) para aprovisionar y operar todo desde local
```

## Correr localmente (docker-compose)

```bash
make local-run          # up + espera salud + pytest + reporte
# o paso a paso:
docker compose up -d --build
pip install -r requirements-dev.txt
pytest tests/ -v
python tests/reporte.py
docker compose down -v
```

RabbitMQ management UI: http://localhost:15672 (hda/hda). API: http://localhost:8000/docs.

## Correr en GCP (vía la CLI `hda-gcp`)

Requiere `gcloud` autenticado (`gcloud auth login` + `gcloud auth application-default login`) y un
proyecto de GCP con facturación habilitada. **Nada de esto se ejecutó desde este entorno de
desarrollo** (no hay `gcloud` instalado ni credenciales configuradas aquí) — el Terraform se validó
sintácticamente (`terraform init` + `terraform validate`), no contra un proyecto real.

```bash
python -m cli.hda_gcp.main check                                    # valida gcloud/terraform/docker

python -m cli.hda_gcp.main infra init
python -m cli.hda_gcp.main infra plan  --project TU_PROYECTO
python -m cli.hda_gcp.main infra apply --project TU_PROYECTO        # pide confirmación (recursos facturables)

python -m cli.hda_gcp.main images build-push --project TU_PROYECTO --repo disp03-poc-hda
python -m cli.hda_gcp.main infra apply --project TU_PROYECTO        # vuelve a aplicar para que Cloud Run tome la imagen nueva

python -m cli.hda_gcp.main run-experiment --target gcp               # corre los CP-1..CP-7 contra GCP real

python -m cli.hda_gcp.main teardown --target gcp --project TU_PROYECTO   # destruye todo, pide confirmación
```

## Dos capas de reintento (diseño intencional, no duplicación accidental)

En GCP, la suscripción push de Pub/Sub tiene su propia `retry_policy` + `dead_letter_policy`
(`infra/pubsub.tf`) — es una red de seguridad a nivel de infraestructura. El código de aplicación
(`worker/core.py`) gestiona sus propios reintintos con backoff y decide explícitamente cuándo algo
es "definitivamente fallido" y lo envía a la DLQ por su cuenta. Por diseño, el handler push
(`push_handler.py`) **siempre responde 200** una vez que `procesar_verificacion` resuelve (éxito o
fallo), precisamente para que la capa de Pub/Sub no dispare sus propios reintentos sobre algo que la
aplicación ya resolvió — evita que ambas capas reintenten el mismo mensaje sin coordinarse.

## Diferencias local (RabbitMQ) vs. GCP (Pub/Sub) — amenazas a la validez

Documentadas aquí para que `validador-hipotesis` las cite explícitamente si el veredicto pretende
generalizarse al despliegue real, no solo al entorno local:

- **Orden de mensajes**: RabbitMQ con una sola cola preserva orden FIFO razonablemente bien bajo
  esta topología; Pub/Sub sin `ordering key` no garantiza orden. Ninguno de los 7 casos de prueba
  depende de orden estricto, pero si un caso futuro lo necesitara, habría que fijar `ordering_key` en
  el publicador de Pub/Sub.
- **Semántica de entrega**: ambos son *at-least-once* — el código ya asume mensajes duplicados
  posibles (idempotencia parcial vía `verificacion_id`), pero no hay una prueba de prueba específica
  de duplicados en esta primera versión.
- **Transporte del worker**: pull continuo (RabbitMQ) vs. push por HTTP (Pub/Sub → Cloud Run). La
  lógica de reintentos (`worker/core.py`) es idéntica; el *trigger* no lo es.
- **DLQ**: local es una cola RabbitMQ poblada por la propia aplicación; en GCP hay dos mecanismos
  (aplicación + `dead_letter_policy` nativa de Pub/Sub) — ver sección anterior.

## Servicio DDD (Regla 5 de la rúbrica) — implementado

Los 5 criterios de la Regla 5 (`../../contexto/REGLAS-DURAS-rubrica-entrega-3.md`), con su evidencia:

| # | Criterio | Dónde |
|---|---|---|
| 1 | Patrón de dominio | `app/domain/seedwork/*`, `app/domain/verificacion/*` — agregado `Verificacion` (2 invariantes protegidos internamente), entidad hija `IntentoVerificacion`, VOs, servicio `ServicioDeElegibilidad`, fábrica, repositorio como interfaz |
| 2 | Hexagonal | `domain/` sin imports de infraestructura; 2 puertos — `IVerificacionRepository` (persistencia) e `IVerificacionExternaPort` (Policía/RUES/Certificadora) — vs. sus adaptadores en `infrastructure/persistence/` e `infrastructure/external/` |
| 3 | Persistencia real | Postgres/Cloud SQL, ahora detrás de `VerificacionRepositorySQLAlchemy` — las rutas HTTP ya no tocan `SessionLocal`/`VerificacionORM` |
| 4 | Eventos de dominio intra-servicio | `domain/verificacion/eventos.py` + `application/dispatcher_eventos_dominio.py` — `IntentoRegistrado`, `VerificacionCompletada`, `VerificacionAgotoReintentos`, todos internos, nunca cruzan a un broker directamente |
| 5 | CQS | `application/commands/*` (mutan) vs. `application/queries/*` (solo leen) |

**Decisión de diseño respecto a la propuesta original** (`../../contexto/11-implementacion-ddd-verificacion.md`):
no existe un comando público `MoverADLQ` separado — exponerlo permitiría forzar la transición a
FALLIDA_DLQ sin haber agotado los reintentos, violando el invariante que el agregado protege. La
transición ocurre dentro de `RegistrarIntento`, como efecto del propio agregado.

**Fuera de alcance a propósito** (no lo exige ningún criterio de la Regla 5 ni ninguna regla dura):
Kafka/Redpanda como tercer broker, Prometheus/Grafana, Postman/Newman, JMeter. El disparo automático
de `RevalidarProveedor` por cron/Cloud Scheduler o por alta de técnico nuevo tampoco se implementó —
solo el comando y un endpoint manual (`POST /proveedores/{id}/revalidar`).

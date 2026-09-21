# Mensajería, DDD y datos en la PoC (qué hay, por qué, y dónde verlo en los logs)

> **⚠ Revisado en Entrega 5 (2026-09-21).** La topología de la §3 es la de la Entrega 4. El catálogo completo de tópicos de la Entrega 5 (12 eventos, productores, consumidores, propiedades `id_evento`/`correlation_id`) está en [`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md) §7.


Este documento responde: contextos y subdominios, comandos y eventos, Pub/Sub y Pulsar,
formato de los mensajes (¿por qué JSON y no Avro/Protobuf?), evolución de contratos,
AsyncAPI y modelo de datos. Cada concepto indica el **campo del log** donde se ve en
Cloud Logging / Grafana (ver también [QUERIES-GCP-POR-ESCENARIO.md](QUERIES-GCP-POR-ESCENARIO.md)).

## 1. Dominio, subdominios y contextos acotados

Fuente: `contexto/01-dominios-subdominios.cml` y `03-contextos-acotados-TO-BE.cml`.
Cada línea de log trae estos cuatro campos automáticamente (`app/common/logging_utils.py`):

| Servicio Cloud Run | `dominio` | `subdominio` | `tipo_subdominio` | `bounded_context` |
|---|---|---|---|---|
| gestion-trabajos-poc-api | MarketplaceDeServicios | GestionDeTrabajos | CORE_DOMAIN | ContextoGestionDeTrabajos |
| disp03-poc-api / disp03-poc-worker | MarketplaceDeServicios | ProveedoresDeServicio | CORE_DOMAIN | ContextoProveedores |
| pagos-poc-api | FintechYPagos | Pagos | GENERIC_SUBDOMAIN | ContextoPagos |
| mocks-crm-poc-mock-crm | CapacidadesTransversales | OperacionDeAgentes | GENERIC_SUBDOMAIN | ContextoGestionAgentes (externo) |
| disp03-poc-mock-* | SistemaExterno | VerificadorExterno | EXTERNO | MockVerificadorExterno |
| reputacion-poc-api | MarketplaceDeServicios | ReputacionYCalidad | CORE_DOMAIN | ContextoReputacion (sin logs `evento`: usa `logger` plano) |

Relaciones del Context Map que la PoC ejercita (todas `[U, OHS, PL] -> [D, ACL]`):
Gestión de Trabajos → Reputación / Proveedores (eventos de integración, Pulsar);
Gestión de Trabajos → Gestión de Agentes (eventos → webhooks, DISP-02); Pagos ↔ Gestión de Trabajos (API REST).
Cada microservicio es su propio Bounded Context: cada uno tiene su base de datos y su copia de `logging_utils.py`.

**Capa hexagonal:** campo `capa` = `api | application | domain | infrastructure | worker | mocks`.

## 2. Comandos, consultas y eventos (dónde verlos)

Campo `tipo_mensaje`, que se infiere del prefijo del evento del log:

| `tipo_mensaje` | Ejemplos (campo `evento`) | Escenario |
|---|---|---|
| `comando` | `comando_crear_trabajo_ejecutado` (CrearTrabajo), `comando_pagar_trabajo_recibido` (PagarTrabajo) | ESC-01, MOD-02 |
| `evento_de_dominio` | `evento_dominio_trabajo_finalizado_emitido`, `evento_dominio_intento_registrado`, `evento_dominio_verificacion_completada`, `evento_dominio_pago_despachado` | todos |
| `evento_de_integracion` | `evento_integracion_trabajo_finalizado_publicado`, `evento_integracion_proveedor_habilitado_publicado` | ESC-01, DISP-03 |
| `mensajeria` | `mensaje_publicado`, `mensaje_recibido`, `mensaje_novedad_encolada` | ESC-01, DISP-03, DISP-02 |
| `aplicacion` | el resto (`trabajo_creado`, `crm_respuesta_recibida`, `pasarela_cobro_respuesta`…) | — |

Los comandos con CQS retornan solo el id (`CrearTrabajo`, `PagarTrabajo`, `IniciarVerificacion`,
`PublicarNovedad`, `Compensar`); las consultas (`ConsultarTrabajo`, `ConsultarPago`, …) no cambian estado.

**Dominio vs. integración:** `TrabajoFinalizado` nace como evento de **dominio** dentro del agregado `Trabajo`
(no conoce Pulsar). `application/dispatcher_eventos_dominio.py` lo traduce a evento de **integración**
publicado en Pulsar y a una reacción **intra-servicio** (`registro_trabajo_elegible_guardado`).
En el log se ven los dos pasos con `tipo_mensaje` distinto.

**Patrones de MOD-02 visibles en el log:** `regla_regional_aplicada` (`patron=Strategy`, `regla=ReglaColombia|ReglaBrasil`)
y `pasarela_seleccionada` (`patron=Adapter`, `adaptador=PasarelaStripe|PasarelaMercadoPago`).

## 3. Topología de datos: qué mensajes viajan y por dónde

| Canal | Tecnología | Publica | Suscribe | Semántica |
|---|---|---|---|---|
| `persistent://hda/gestion-trabajos/trabajos.finalizado` | **Apache Pulsar** (VM `pulsar-poc-vm`, 10.158.0.2) | gestion-trabajos-poc-api | Reputación (`reputacion-trabajos-finalizado`), Proveedores (`proveedores-trabajos-finalizado`), Shared | evento de integración, "fire and forget" desde el comando; si Pulsar falla el trabajo ya está guardado (`evento_integracion_..._fallo_publicacion`, nivel error) |
| `disp03-poc-verificacion-solicitudes` | **Pub/Sub** | disp03-poc-api | suscripción **push** → `POST /pubsub/push` del worker | cola de trabajo, at-least-once, ack_deadline 30 s, retry 1–20 s, dead-letter tras 5 entregas |
| `disp03-poc-verificacion-fallidas` | Pub/Sub | disp03-poc-worker | suscripción pull (reproceso manual `POST /dlq/{id}/reprocesar`) | DLQ |
| `disp03-poc-verificacion-eventos-integracion` | Pub/Sub | disp03-poc-worker | ninguno hoy | `proveedor.habilitado`; topic separado del de solicitudes (bug 2026-09-06) |
| cola en memoria del Throttler | `asyncio.Queue` | gestion-trabajos-poc-api | su propio worker | DISP-02: 202 inmediato, entrega al CRM asíncrona con token bucket |

Cómo verlo: `mensaje_publicado` (canal, topico, message_id, tamano_bytes) y `mensaje_recibido`
(suscripcion, intento_entrega_pubsub, mismo `message_id`). Buscar por `jsonPayload.message_id="..."` une publicador y consumidor.

Hallazgo de topología (no cambia nada desplegado): DISP-03 consumiría `persistent://hda/trabajos/trabajos.finalizado`
(`pulsar_topology.TOPIC_TRABAJOS_FINALIZADO`) mientras Gestión de Trabajos publica en
`persistent://hda/gestion-trabajos/trabajos.finalizado`. Reputación sí apunta al correcto. El consumidor de Proveedores no está
desplegado, pero si se despliega hay que alinear el namespace.

## 4. Formato de los mensajes: ¿por qué JSON y no Avro o Protobuf?

**Hoy: JSON plano (`application/json`) en los tres servicios que hablan mensajería.** No fue el primer intento:

- Gestión de Trabajos publicaba con `pulsar.schema.AvroSchema`. Se revirtió al correr contra un Pulsar real
  (documentado en el docstring de `publicador_pulsar.py`) por dos motivos:
  1. `pulsar-client` sin el extra `[avro]` no trae `fastavro`; `create_producer(..., schema=AvroSchema(...))` fallaba en cada publicación.
  2. Aun instalándolo, el consumidor (`reputacion/.../consumidor_pulsar.py`) hace `json.loads(mensaje.data())`: esperaba JSON, no bytes Avro con metadata de schema.
  Dos equipos, nunca probados juntos contra un broker real hasta ese momento.
- Se unificó a un solo formato entre Gestión, Proveedores y Reputación (el mismo `json.dumps(...).encode()` de DISP-03), en vez de que cada servicio invente el suyo.

| | JSON (actual) | Avro | Protobuf |
|---|---|---|---|
| Legible en logs/consola | sí | no (binario) | no (binario) |
| Contrato explícito | solo por convención + AsyncAPI | schema obligatorio, verificado por el broker | `.proto`, generado |
| Tamaño | mayor (182–207 B por mensaje aquí) | compacto | compacto |
| Evolución | manual (tolerant reader) | reglas de compatibilidad con Schema Registry | reglas por número de campo |
| Costo de adopción | ninguno | dependencia `[avro]` + registro de schemas + coordinación entre equipos | codegen en cada servicio |

Decisión razonable para una PoC de 4 servicios con volumen bajo y equipos separados; el costo es que **el contrato lo garantiza la
disciplina, no el broker**. Cuándo migrar: más consumidores de un mismo tópico, mensajes de alto volumen o necesidad de rechazar
publicaciones inválidas en el broker. Pulsar tiene Schema Registry nativo (Avro/Protobuf/JSON Schema) y lo natural sería activarlo por
tópico empezando por `trabajos.finalizado`, que es el que tiene más consumidores.

Detalle de serialización que sí está resuelto: los montos viajan como **string decimal** (`"200.00"`), no `float`, para no perder precisión;
y hacia las pasarelas el Adapter convierte: Stripe recibe **centavos enteros** (`monto_enviado: 20000`) y MercadoPago **unidades decimales**
(`200.0`) — visible en `pasarela_cobro_solicitado.unidad_monto`.

## 5. Evolución y versionamiento de mensajes

Política aplicada (visible en el log como `version_esquema`, hoy `"1"`):

- La versión viaja como **metadata**: propiedad del mensaje en Pulsar, atributo en Pub/Sub (`version_esquema`, `tipo_evento`, `content_type`, `productor`). No dentro del cuerpo, para no cambiar el contrato existente.
- Cambios **aditivos** (campo nuevo opcional) no suben la versión: los consumidores actuales leen por clave (`payload["trabajo_id"]`) e ignoran lo demás (*tolerant reader*).
- Un cambio que rompe (renombrar/quitar/cambiar tipo) sube a `"2"` y se publica **en paralelo** hasta que todos los suscriptores migren; los consumidores deben registrar (no ignorar en silencio) una versión que no reconocen. `mensaje_recibido` ya registra `version_esquema` (o `sin_version` para mensajes previos a este cambio).
- Idempotencia frente a redelivery (at-least-once): el worker ignora verificaciones ya terminales (`verificacion_redelivery_ignorada`).

## 6. AsyncAPI

[asyncapi/hda-asyncapi.yaml](asyncapi/hda-asyncapi.yaml) (AsyncAPI 2.6) documenta los 4 canales reales, sus servidores (Pulsar y Pub/Sub),
quién publica/suscribe, los `headers` (metadata de versión) y los schemas JSON de los 4 mensajes
(`TrabajoFinalizado`, `SolicitudVerificacion`, `VerificacionFallida`, `ProveedorHabilitado`). Para verlo renderizado:
`npx @asyncapi/cli start studio asyncapi/hda-asyncapi.yaml`.

## 7. Modelo de datos: qué y por qué

Una base Cloud SQL (Postgres) **por microservicio**, sin claves foráneas entre bases (referencia por id):

| Servicio | Tablas | Por qué |
|---|---|---|
| gestion-de-trabajos | `trabajos` (agregado Trabajo), `novedades` (agregado Novedad, `estado`/`intentos` de DISP-02), `trabajos_elegibles_pago` (registro propio poblado por el evento de dominio) | el agregado se persiste antes de despachar eventos; `novedades.intentos` deja trazada la entrega aunque el proceso muera |
| pagos | `pagos` (agregado Pago; `referencia_externa`, `motivo_falla`), `trabajos_elegibles_pago` (se puebla vía `POST /pagos`) | `trabajo_id` sin FK: el `Trabajo` vive en otro contexto |
| DISP-03 | `verificaciones`, `intentos_verificacion` (1:N), `eventos_recibidos` | el historial de intentos es evidencia de DISP-03 (reintentos, DLQ, reprocesos) |
| reputacion | `eventos_reputacion` (event store), `trabajos_vistos` | Event Sourcing previsto para la Saga (Entrega 5) |

Estados de negocio visibles en los logs: `Trabajo` (PENDIENTE, FINALIZADO), `Verificacion` (PENDIENTE, COMPLETADA, FALLIDA_DLQ), `Novedad`
(PENDIENTE, ENTREGADA, AGOTADA), `Pago` (PENDIENTE, EXITOSO, FALLIDO, COMPENSADO).

## 8. Costo y control del detalle de logs

Los eventos de trazado fino (`http_request_completada`, `comando_*`, `mensaje_publicado` de gestión, `evento_dominio_*_emitido`…) están
marcados `detalle=True` y se apagan con la variable de Terraform `log_detalle="minimo"` (env `LOG_DETALLE`) en gestion-de-trabajos y pagos.
**Usar `minimo` en una corrida real de ESC-01**: cada request emite ~6 líneas más y a ~1.000 req/s eso cuesta CPU y facturación de Cloud Logging.

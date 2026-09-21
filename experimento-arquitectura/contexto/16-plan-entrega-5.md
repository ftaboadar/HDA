> Copia en el repo del plan aprobado el 2026-09-21. Las decisiones viven en `15-arquitectura-entrega-5.md` (A21-A28, §3.4, §7.1-7.3, §11-14); si difieren, manda el 15.

# Plan — Entrega 5: Saga del Trabajo orquestada, BFF y journeys completos

## Context

La Entrega 5 (rúbrica en `contexto/REGLAS-DURAS-rubrica-entrega-5.md`, aclaraciones y observaciones del
profesor en `contexto/ACLARACIONES-entrega-5.md`) exige: una **saga** con al menos 3-4 servicios, con caso
exitoso y caso con **compensación** (19 pt); un **Saga Log** consultable con SQL junto al coordinador (8 pt);
un **BFF** REST como base del API (15 pt); **despliegue**, link y Postman vía BFF (10 pt); **3 escenarios**
validados con resultados cuantitativos y cualitativos y conclusiones de hipótesis (10 pt); **mapa de contextos
y vistas refinados con justificación** (8 pt); **sin regresión** (5 pt); y **contribución equitativa** (25 pt).
En la Entrega 4 se perdieron puntos por **no tener esquemas de eventos** (2,5/5) y por **no explicar la
topología de datos** (2,9/5).

El diseño está cerrado en `contexto/15-arquitectura-entrega-5.md` (A1-A20, journey, estados, catálogo,
JRN-01..05). Hoy no hay nada desplegado y existen 4 servicios (GT, Proveedores = solo Verificación, Pagos solo
REST, Reputación) — ver `implementacion/ESTADO-IMPLEMENTACION.md`. Este plan lleva el diseño a código
funcionando en GCP.

## Decisiones tomadas en esta sesión (se escriben en 15-…md como A21-A28, fase 0)

| # | Decisión |
|---|---|
| A21 | **Esquemas: JSON con Schema Registry de Pulsar** (`pulsar.schema.JsonSchema` + clases `Record`). Compatibilidad **BACKWARD** por namespace; un cambio que rompe = tópico nuevo `…v2`. Responde "¿Avro o Protobuf?": se eligió JSON con esquema por legibilidad en logs/video con las mismas garantías de registry y compatibilidad (justificar en el documento; Avro queda como ruta de mejora si el payload pesa en ESC-01) |
| A22 | **Saga orquestada**. Coordinador = módulo **Motor de Workflow** de Gestión de Trabajos. Envía **comandos** por Pulsar y recibe **eventos** de respuesta. **Saga Log** en la BD de GT (tabla append-only). Resuelve D1 |
| A23 | **Escenarios oficiales:** ESC-01 (escalabilidad), MOD-02 (modificabilidad), **DISP-02** (disponibilidad). DISP-03 sigue implementado dentro del journey (paso 0) y cuenta para "sin regresión" |
| A24 | **Todo en Pulsar**: la cola de Verificación deja Pub/Sub (`transporte="pulsar"` ya existe en `proveedores/app/common/config.py`; DLQ nativa en `pulsar_topology.py::construir_dead_letter_policy`). Se elimina `proveedores/infra/pubsub.tf` |
| A25 | **BFF REST** (FastAPI, OpenAPI en `/docs`), servicio nuevo `implementacion/bff/`, único punto de entrada para actores externos; llama síncrono a las APIs de los servicios. Son 9 servicios |
| A26 | **Topología descentralizada** (una BD por servicio, nadie lee la de otro), comparada con centralizada e híbrida en el documento. Almacenamiento: Postgres CRUD en todos, **Event Sourcing** en Reputación (existe) y en el Saga Log |
| A27 | **Alcance: todo lo decidido (A1-A20) es obligatorio**, incluidos agenda, sincronización con el partner, reputación compuesta, retención de pagos y los 3 caminos alternos |
| A28 | **Retrocompatibilidad de contratos, módulos y datos** (evolucionar sin romper a nadie) | Regla común: **solo se agrega, nunca se quita ni se renombra**. **Eventos y comandos (Pulsar):** Schema Registry con compatibilidad BACKWARD (solo campos nuevos con valor por defecto; los consumidores ignoran lo que no conocen); un cambio que rompe crea un tópico `…v2` que convive con el `…v1` hasta migrar al último consumidor. **APIs REST (BFF y servicios):** rutas `/v1`; dentro de `/v1` solo se agregan endpoints y campos opcionales; un cambio que rompe es `/v2` con el header `Deprecation`; el CI corre **oasdiff** y falla el PR si detecta un cambio que rompe. **Módulos de un servicio:** su interfaz pública (comandos, consultas y eventos de dominio de `application/`) se cambia en el mismo PR que sus usuarios; una **prueba de arquitectura** falla si un módulo importa el dominio o la infraestructura de otro. **Datos:** migraciones versionadas y *expand/contract* (primero se agrega, luego se migra el código, luego se quita). Detalle en §14 |
| A29 | **Comunicación (Inter vs Intra)** | **Entre servicios**: asíncrona vía Pulsar (desacople) y síncrona vía REST desde el BFF. **Entre módulos del mismo servicio**: síncrona en memoria vía Application Services y asíncrona vía Dispatcher local (eventos de dominio). Justificado explícitamente. |

## Justificación de cada decisión (se escribe en 15-…md §3.4 como ficha por decisión y es la base de la sustentación)

Formato de cada ficha: **problema de negocio → opciones evaluadas → decisión → atributo de calidad que
favorece → qué se sacrifica → cómo se demuestra (video o código)**. Las 8 fichas:

| Decisión | Por qué (negocio + atributo) | Qué se sacrifica | Descartadas y por qué |
|---|---|---|---|
| **A22 Orquestación y no coreografía** | La Saga del Trabajo es **larga y con pasos dependientes** (no se retiene el pago sin franja; no se libera sin trabajo terminado), con **3 compensaciones que cruzan servicios** (liberar franja, devolver lo retenido, cancelar) y **3 orígenes** con reglas distintas. El enunciado dice que **agentes humanos monitorean cada trabajo** (p.4 y p.14): un coordinador responde en un solo lugar *"¿en qué paso va y qué se compensó?"*, que es justo el Saga Log. GT ya es "Orquestación de flujos" en la vista de contexto. Favorece **modificabilidad del flujo** (un paso nuevo o un partner nuevo se agrega en el coordinador) y **disponibilidad** (plazos por paso con compensación automática) | GT concentra más responsabilidad (ya es SP1); se mitiga con réplicas, Saga Log persistente e idempotencia de comandos. Más acoplamiento al contrato de comandos | **Coreografía**: con 9 servicios y 3 compensaciones, el flujo quedaría repartido en reacciones implícitas; nadie sabe el estado global, se arriesga a ciclos de eventos, y el Saga Log habría que reconstruirlo desde afuera. Se conserva **coreografía** donde sí encaja: el fan-out de `TrabajoFinalizado` a Reputación, Scoring y Suscripciones (MOD-03: consumidores nuevos sin tocar el core) |
| **A22 Coordinador dentro de GT** | GT es dueño del agregado `Trabajo` y de su máquina de estados: el coordinador y el estado que coordina viven en el mismo contexto y la misma transacción local (Saga Log + estado del Trabajo se escriben juntos) | GT crece; se separa por módulo (`workflow`) para no mezclarlo con `ciclo_vida` | **Servicio coordinador aparte**: un servicio más sin dominio propio que tendría que consultar el estado del Trabajo a GT, sumando una llamada y un punto de falla |
| **A21 JSON con Schema Registry** | El 2,5/5 de la Entrega 4 fue por **no tener esquemas**, no por el formato. El Schema Registry de Pulsar da **contrato registrado, versiones y rechazo de cambios incompatibles** (BACKWARD) con JSON igual que con Avro. JSON mantiene los mensajes **legibles** en Cloud Logging, en `pulsar-admin` y en el video, y es el formato que ya usan y entienden los 3 servicios existentes (menos riesgo de repetir el fallo de la Entrega 4). Favorece **modificabilidad** (evolución controlada) | Mensajes más grandes y serialización más lenta que binario. Se cuantifica en ESC-01 (tamaño de mensaje en `mensaje_publicado.tamano_bytes`); hoy ~191 bytes por `TrabajoFinalizado`, despreciable frente a los ~380 ms medidos en la publicación | **Avro**: binario y compacto, pero ilegible sin herramientas, y en la Entrega 4 falló por dependencia (`fastavro`) y por desalineación de consumidores; se deja como ruta de mejora si ESC-01 mostrara que el tamaño pesa. **Protobuf**: requiere compilar `.proto` en cada servicio y el soporte nativo de Pulsar en Python es más limitado |
| **A21 Versionamiento** | Cambios **aditivos** (campo nuevo con default) no rompen: los acepta BACKWARD. Cambio que rompe → tópico `…v2` y ambos conviven hasta migrar consumidores (*Event Stream Versioning*). APIs REST versionadas en el BFF (`/v1`). Favorece **modificabilidad** con 9 equipos evolucionando por separado | Convivencia temporal de dos versiones de un tópico | Versionar solo en el cuerpo del mensaje sin registry: nadie lo hace cumplir |
| **A25 BFF REST** | Los 3 actores (dueño, proveedor, partner) y los agentes necesitan **una sola puerta** con capacidades de negocio, no 9 APIs. El BFF **oculta la topología interna**, traduce llamadas síncronas del cliente en comandos del sistema, propaga el `correlation_id` y permite cerrar los servicios internos al público. REST porque Postman, OpenAPI y el equipo ya lo usan. Favorece **modificabilidad** (los servicios cambian sin romper clientes) y **seguridad/operación** | Un salto de red más y un componente que debe escalar con el tráfico de entrada (sin estado, escala horizontal en Cloud Run) | **API Gateway genérico**: enruta, pero no compone capacidades por actor. **GraphQL**: flexible para componer, pero más trabajo y menos directo con Postman |
| **A24 Todo en Pulsar** | El enunciado pide Pulsar como broker y el profesor observó el doble broker. Pulsar da la **DLQ nativa** que DISP-03 necesita, así que no se pierde la táctica. Un solo broker = una sola forma de operar, monitorear y documentar (AsyncAPI) | Se pierde la comparabilidad exacta con la medición de DISP-03 en Pub/Sub (se re-mide dentro del journey) | Mantener Pub/Sub: dos tecnologías para lo mismo, sin beneficio de negocio |
| **A26 Topología descentralizada** | HdA sale de un **monolito con una BD compartida** que bloquea a los equipos (enunciado p.4). BD por servicio = cada contexto evoluciona, escala y se despliega solo (ESC-01 pico en Siniestros no satura a Pagos; MOD-03 servicios nuevos sin migrar datos). Favorece **escalabilidad y modificabilidad** | Consistencia eventual y sin joins entre servicios; se resuelve con la saga (consistencia por compensación) y eventos con carga de estado | **Centralizada**: la más simple (ACID, joins), pero repite el problema del monolito y concentra el pico en un solo punto. **Híbrida**: compartir BD entre algunos rompe los límites de los contextos acotados |
| **A26 Tecnologías de BD y Optimización de Costos** | **Topología Descentralizada**: cada microservicio tiene su propia BD física exclusiva (instancia de Cloud SQL) para escalar independiente (ESC-01), sincronizando datos vía eventos en Pulsar. Para **optimizar costos** sin perder ACID local (Saga Log), se elige **Postgres relacional** en todos con tiers ajustados al PoC. Se usa **CRUD** para estado (Trabajo, Pago) y **Event Sourcing** solo donde el historial es core (Reputación). | Pagar una instancia Cloud SQL dedicada por servicio eleva los costos base vs tener una BD monolítica, pero se asume para mantener puros los contextos acotados. | **NoSQL (Mongo)**: se descarta por añadir costo operativo sin ganancia (los agregados son altamente relacionales). **Serverless Nativo (Firestore/Spanner)**: descartado por riesgo de sobrecosto impredecible en picos agresivos (ESC-01) y *vendor lock-in*. **Caché (Redis)**: descartado por ahora para ahorrar infraestructura; Cloud Run y Cloud SQL soportan los picos actuales sin el sobrecosto de un nodo Redis. **ES en todo**: complejidad sin retorno. |
| **A23 Escenarios** | Uno por atributo y **relevante para el negocio**: ESC-01 = pico 4x de siniestros por clima (70 % del volumen es B2B2C); MOD-02 = entrar a Brasil con su moneda y pasarela sin tocar Colombia (expansión global); DISP-02 = granizada con ráfaga de novedades contra el CRM de los 100 agentes. DISP-02 vive **dentro de la saga** (novedad → reasignación o compensación) | DISP-03 no es el oficial de disponibilidad | DISP-03: se mantiene implementado (paso 0) pero queda fuera del camino de la saga |
| **A28 Retrocompatibilidad** | HdA tiene **9 servicios que evolucionan por separado** y, con la expansión, crecerá el número de equipos y de partners que consumen las APIs (enunciado p.4: hoy los equipos se bloquean entre sí). Si un cambio de un servicio obligara a desplegar a todos a la vez, se repetiría el problema del monolito (despliegues de 3-4 horas). Con contratos retrocompatibles, cada servicio se despliega solo. Favorece **modificabilidad** (MOD-01/02/03: partners y países nuevos sin tocar el core) y **disponibilidad** (un despliegue no rompe a los consumidores que aún no migraron) | Convivencia temporal de dos versiones (tópicos `…v1` y `…v2`, rutas `/v1` y `/v2`) y campos que no se pueden borrar hasta migrar a todos; disciplina de expand/contract en las migraciones | **Versiones simultáneas obligatorias (big bang)**: despliegue coordinado de todos los servicios, con ventana de riesgo. **Solo convención sin chequeo**: nadie lo hace cumplir; por eso hay Schema Registry, oasdiff y prueba de arquitectura |
| **A29 Estilos de Comunicación (Síncrono vs Asíncrono)** | Para desacoplar equipos, la **comunicación entre servicios** es **asíncrona vía eventos/comandos (Pulsar)**, salvo el acceso de clientes que entra **síncrono por el BFF (REST)**. Para mantener cohesión interna, la **comunicación entre módulos** del *mismo* servicio es **síncrona en memoria** (un módulo invoca el Application Service del otro) y los **eventos de dominio** se despachan vía un *Dispatcher* local. Favorece **rendimiento** (sin salto de red interno) y **modificabilidad** (contratos explícitos AsyncAPI vs OpenAPI). | Mayor complejidad cognitiva (el desarrollador debe entender cuándo usar in-memory dispatch vs Pulsar message broker). | **Todo Síncrono (gRPC/REST entre servicios)**: alto acoplamiento temporal, cascada de fallos (afecta disponibilidad). **Todo Asíncrono (incluso dentro del módulo)**: latencia innecesaria y sobrecarga de red para operaciones que viven en la misma BD/máquina. |

Los escenarios ya se probaron sueltos en las Entregas 3-4 (`implementacion/RESULTADOS-*.md`): la Entrega 5
los **vuelve a correr dentro de los journeys**, con los mismos umbrales, y compara contra esas corridas.

## La saga y el Saga Log en los 5 journeys

Todos los journeys pasan por la misma Saga del Trabajo, y cada uno deja en el Saga Log un recorrido distinto que
se muestra con `consultas-saga-log.sql`:

| Journey | Recorrido de la saga | Estado final en `saga_instancia` | Qué muestra el Saga Log |
|---|---|---|---|
| **JRN-01** Marketplace con la certificadora caída | Pasos 1-6 completos (el proveedor recién reprocesado aparece en elegibles) | `COMPLETADA` | Transacción **exitosa** de punta a punta |
| **JRN-02** Pico 4x de siniestros (ESC-01) | Pasos 1-3, sin retención (siniestro), 5, 6 con `FacturarAPartner` | `COMPLETADA` (miles de sagas) | Sagas por minuto, duración por paso y pasos expirados bajo el pico |
| **JRN-03** Novedades con CRM limitado (DISP-02) | Rama no-show: `LiberarFranja` y vuelta al paso 2; rama siniestro: `SolicitarAprobacionNovedad` → `DecisionPartner` | `COMPLETADA` tras reasignar | **Compensación parcial** (franja liberada y reasignación) y espera de la aprobación del partner |
| **JRN-04** Pago en Brasil y disputa (MOD-02) | Pasos 1-6 con `ReglaBrasil` + MercadoPago; luego disputa → `CompensarPago` | `COMPENSADA` | **Compensación total**: retenido → liberado → compensado, montos iguales |
| **JRN-05** Suscripción mensual | Primer ciclo pasos 1-6; ciclos siguientes entran con proveedor fijo y franja ya reservada | `COMPLETADA` por ciclo | Varias sagas del mismo proveedor y franja; rechazo de otra reserva de la misma franja |
| **Caso de fallo del video** (dentro de JRN-01) | Pasarela en modo falla: `RetenerPago` → `PagoRetencionFallida` | `COMPENSADA` | `COMPENSACION_ENVIADA` `LiberarFranja` y Trabajo `CANCELADO` |

## Los escenarios que se implementan en cada journey

Cada JRN hereda los umbrales de su escenario (`escenarios_calidad.md`) y suma medidas de journey
(15-…md §11). Los 3 oficiales son JRN-02, JRN-03 y JRN-04; JRN-01 y JRN-05 prueban DISP-03 y MOD-03 (sin regresión).

| JRN | Escenario | Estímulo (cómo se inyecta) | Medidas (umbral heredado + journey) | Evidencia en GCP |
|---|---|---|---|---|
| JRN-01 | DISP-03 | Certificadora `caido` (`POST /_control/config` del mock) mientras un proveedor se registra por el BFF; luego reproceso de la DLQ | Verificación ≥ 99,9 % disponible; 100 % de fallidas trazables en DLQ y reprocesables < 24 h; 0 trabajos asignados a proveedores no verificados; saga `COMPLETADA` | Query por `proveedor_id` (intentos, DLQ, reproceso) + query por `correlation_id` del trabajo |
| JRN-02 | **ESC-01** | k6 con 4x de siniestros por el BFF (API de Siniestros, SP6) + Marketplace con carga normal; línea base con el atajo (A15) | Aceptación p95 < 2 s; ≥ 99,9 % aceptadas; < 5 % de variación en Marketplace; por consumidor de `trabajos.finalizado`: lag ≤ 120 s, drenado ≤ 15 min, p95 < 2 s, 0 perdidos; 0 trabajos sin elegibles; 0 dobles reservas | Grafana: p95 / req/s por servicio, backlog por suscripción de Pulsar, sagas por minuto y duración por paso (Saga Log) |
| JRN-03 | **DISP-02** | Durante JRN-02, ráfaga de novedades (incluye no-shows) con `mocks-crm` limitando la tasa | ≥ 99,9 % sin pérdida; ≥ 99 % webhooks < 15 min y 100 % < 1 h; GT ≥ 99,9 % disponible; 100 % de no-shows reasignados; 0 resoluciones de siniestro sin `DecisionPartner(APROBADA)` | Query de novedades por estado (PENDIENTE/ENTREGADA/AGOTADA) y 429 del CRM; Saga Log con la rama de reasignación |
| JRN-04 | **MOD-02** | Trabajo en región BR pagado con MercadoPago; luego disputa | 0 cambios en Colombia/Stripe/core (diff + suite); región y moneda tomadas del Trabajo; retenido = liberado = compensado; estados de GT y Pagos iguales | Query de Pagos con `patron=Strategy/Adapter`; Saga Log `COMPENSADA` |
| JRN-05 | MOD-03 | Suscripción mensual (lunes mañana) y otro cliente pidiendo la misma franja | 0 cambios en GT para el consumidor nuevo; mismo proveedor todo el mes; franja rechazada para el segundo cliente | Query por `suscripcion_id`; `FranjaRechazada` en el Saga Log |
| — | Saga (ítems 2 y 3) | Pasarela en modo falla durante un JRN-01 | Saga `COMPENSADA` con `LiberarFranja` y Trabajo `CANCELADO` | `consultas-saga-log.sql` en Cloud SQL (cliente psql/DBeaver) y panel del Saga Log en Grafana |

## Observabilidad en GCP: ver cada servicio y todo el detalle de punta a punta

Objetivo: que en Cloud Logging y en Grafana se vea **cada servicio desplegado** y, para cualquier trabajo, el
recorrido completo con sus conceptos de DDD.

- **Campos obligatorios en cada línea de log** (se extiende `logging_utils.py`, que ya pone `dominio`,
  `subdominio`, `tipo_subdominio`, `bounded_context`, `capa` y `tipo_mensaje`): `servicio`, **`modulo`**,
  **`agregado`**, `correlation_id`, `saga_id`, `paso_saga`, y **`tipo_comunicacion`** =
  `intra_modulo` | `entre_modulos_sync` | `entre_modulos_async` | `entre_servicios_comando` |
  `entre_servicios_evento` | `rest_bff` | `externo`. `tipo_mensaje` distingue `comando`, `consulta`,
  `evento_de_dominio`, `evento_de_integracion`, `compensacion`.
- **`implementacion/QUERIES-GCP-JOURNEYS.md`** (nuevo, reemplaza en E5 a `QUERIES-GCP-POR-ESCENARIO.md`):
  consultas de Logs Explorer listas para copiar, **por journey** (JRN-01..05, por `correlation_id` y `saga_id`)
  y **por concepto**: un bounded context, un módulo, comunicación entre módulos, comandos entre servicios,
  eventos de dominio vs de integración, compensaciones, externos. Más MQL de Cloud Monitoring por servicio.
- **Grafana** (`observabilidad/`): dashboard "HdA E5" con variable de servicio (p95, req/s, 5xx e instancias de
  cada uno de los 9 servicios); panel de logs del journey filtrado por `correlation_id`; panel por
  `tipo_comunicacion` y `tipo_mensaje`; **panel del Saga Log** (datasource Postgres de Grafana contra la BD de
  GT: sagas por estado, línea de tiempo de una saga, compensaciones); backlog por suscripción de Pulsar (métricas
  del broker en `:8080/metrics`, datasource Prometheus o panel de logs de `mensaje_recibido`).
- **Swagger de cada servicio** (`<url>/docs`) y del BFF, listado con URLs en `ESTADO-IMPLEMENTACION.md`.

Se construye en la fase 0 (campos de log + plantilla) y la fase 4 (queries y dashboards contra el despliegue real).

## La Saga del Trabajo (una sola saga; cada JRN es un recorrido de ella)

Coordinador en GT·Motor de Workflow. Comandos en `persistent://hda/<servicio-destino>/comandos`, respuestas
como eventos en el namespace del servicio que responde. Servicios en la saga: GT, Proveedores, Pagos, y el canal
del origen (Marketplace, Siniestros o Suscripciones) → ≥ 4.

| Paso | Comando (GT → servicio) | Respuesta ok / falla | Compensación |
|---|---|---|---|
| 1 | local `CrearTrabajo` (desde `SolicitudDiagnosticada` / `SiniestroAprobado` / `CicloSuscripcion`) | saga `INICIADA` | — |
| 2 | Proveedores `PublicarElegibles` | `ElegiblesPublicados` → canal; canal publica `ProveedorSeleccionado` | — |
| 3 | Proveedores `ReservarFranja` | `FranjaReservada` / `FranjaRechazada` (vuelve a 2) | `LiberarFranja` |
| 4 | Pagos `RetenerPago` (mkt / suscripción) | `PagoRetenido` / `PagoRetencionFallida` | falla → `LiberarFranja` + Trabajo `CANCELADO` (**caso con compensación del video**) |
| 5 | local `IniciarWorkflow` → `EN_CURSO`; proveedor completa vía BFF → `FINALIZADO` | — | — |
| 6 | Pagos `LiberarPago` · o Siniestros `FacturarAPartner` | `PagoLiberado` → `PAGADO` / `FacturaEmitida` | — |
| — | Evento `TrabajoFinalizado` (fan-out, fuera de la saga): Reputación, Scoring, Suscripciones, Proveedores | — | — |
| Alt | Novedad disputa → Pagos `CompensarPago` | `PagoCompensado` → `CANCELADO` | (es la compensación) |
| Alt | Novedad no-show → `LiberarFranja` y vuelta al paso 2 con `excluidos` | — | — |
| Alt | Siniestro: Siniestros `SolicitarAprobacionNovedad` | `DecisionPartner` | aplica la resolución solo si APROBADA |

Cada paso tiene un **plazo**; si vence sin respuesta, el coordinador marca el paso `EXPIRADO` y compensa.
Los comandos llevan `id_comando` (idempotencia en el receptor) y `saga_id` + `correlation_id` (= `trabajo_id`).

**Saga Log (BD de GT):**
- `saga_instancia(saga_id, trabajo_id, origen, estado, paso_actual, iniciada_en, actualizada_en)`
- `saga_log(id, saga_id, secuencia, paso, tipo [COMANDO_ENVIADO | EVENTO_RECIBIDO | COMPENSACION_ENVIADA | PASO_EXPIRADO | SAGA_COMPLETADA | SAGA_COMPENSADA], servicio, mensaje, id_mensaje, payload jsonb, ocurrido_en)`: append-only
- `implementacion/gestion-de-trabajos/sql/consultas-saga-log.sql`: consultas listas para el video (línea de tiempo de una saga, sagas compensadas, pasos expirados, duración por paso)
- `GET /sagas/{id}` en GT (consulta CQS) y `GET /v1/sagas/{id}` en el BFF

## Fases

Cada tarea cumple la **definición de terminado** de `CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md` §9: pruebas
unitarias, de integración y de contrato; CI; Terraform en el job; scripts de despliegue; AsyncAPI; Postman;
`ESTADO-IMPLEMENTACION.md`.

### Fase 0: Contratos y base común (primero, lo necesitan todos)
1. Escribir A21-A27 en `15-arquitectura-entrega-5.md`, quitar D1 y la excepción de Pub/Sub de A2; nueva
   §3.4 con **las fichas de justificación** de arriba; la tabla **"La saga y el Saga Log en los 5 journeys"**
   en §11; ajustar el catálogo §7 a **comandos + eventos** (columna nueva: comando/evento, integración o carga
   de estado y su porqué); nueva §12 "Respuesta a las observaciones de la Entrega 4" (dónde está en el código
   cada punto). Copiar este plan a `contexto/16-plan-entrega-5.md` y enlazarlo desde `AGENTS.md`.
2. Patrón de mensajería con esquema reutilizable por servicio: `infrastructure/messaging/esquemas.py` (clases
   `Record`), publicador y consumidor genéricos que ponen las propiedades de §3 (`id_evento`, `correlation_id`,
   `causation_id`). Se parte de `gestion-de-trabajos/app/infrastructure/messaging/publicador_pulsar.py` y del
   consumidor de `reputacion/app/infrastructure/messaging/consumidor_pulsar.py`.
3. Política de compatibilidad BACKWARD por namespace y namespace `hda/bff` en
   `pulsar-infra/gcp/templates/startup.sh.tpl` y `scripts/pulsar-namespaces-local.sh`.
4. `asyncapi/hda-asyncapi.yaml` con **todos** los canales (comandos y eventos), esquema, productor,
   consumidores y tipo; HTML generado para el documento.
5. Worker estándar (`app/worker/main.py` con `/salud`, CONVENCIONES §5) como plantilla.
6. Extender `logging_utils.py` (plantilla en `gestion-de-trabajos/app/common/logging_utils.py`) con los campos de
   observabilidad (`servicio`, `modulo`, `agregado`, `correlation_id`, `saga_id`, `paso_saga`,
   `tipo_comunicacion`) y registrarlos en CONVENCIONES §2.
7. Reglas de retrocompatibilidad en CONVENCIONES §3 (tabla "Contratos, documentación y retrocompatibilidad"),
   job de CI con **oasdiff** para los `openapi.json` y prueba de arquitectura de imports en la plantilla de servicio.

### Fase 1: Servicios existentes
- **Gestión de Trabajos:** migrar a layout por módulos (`ciclo_vida`, `workflow` = **coordinador de saga +
  Saga Log**, `novedades` (agregado propio, A17), `integraciones_externas` = throttler actual de
  `infrastructure/adapters/throttler_crm.py` + circuit breaker + webhook del CRM); máquina de estados de 15-…md §6;
  `POST /trabajos` detrás de `HABILITAR_ATAJO_CARGA` (A15); worker Pulsar.
- **Proveedores:** módulos `registro` (agregado `Proveedor`), `verificacion` (se amplía a técnicos/empresa y
  **cola en Pulsar**, A24), `elegibilidad` (reusar `domain/verificacion/servicio_elegibilidad.py` como punto de
  partida), `agenda` (`AgendaTecnico`, reserva atómica); comandos `PublicarElegibles`, `ReservarFranja`,
  `LiberarFranja`; arreglar el namespace de `TOPIC_TRABAJOS_FINALIZADO`; prefijo `proveedores-poc` (A20).
- **Pagos:** módulos `liberacion_compensacion` y `pasarelas` (reusar `ReglaRegional` y los adapters Stripe y
  MercadoPago); comandos `RetenerPago`, `LiberarPago`, `CompensarPago` y sus eventos; estados RETENIDO → LIBERADO
  / COMPENSADO / FALLIDO; mock de pasarela con modo de falla para el caso de compensación.
- **Reputación:** trabajos calificables, reputación compuesta (A10), publicar `ReputacionPublicada`, consumir
  `ScoringActualizado`; su worker por fin desplegado.

### Fase 2: Servicios nuevos (plantilla `reputacion/` + CONVENCIONES §1)
- **Marketplace** (diagnóstico, cotización con franja, selección) · **Siniestros** (partner, reglas, aprobación de
  pasos y de novedades, facturación) · **Suscripciones** (ciclos, continuidad, reserva recurrente) · **Scoring**
  (`PerfilCrediticio`).
- **BFF** (`implementacion/bff/`): REST `/v1` por actor (dueño, proveedor, partner, cliente de suscripción,
  operador), sin BD propia, llamadas síncronas con timeout a las APIs de los servicios, propaga `X-Correlation-Id`,
  expone la consulta de sagas; OpenAPI en `/docs`.
- Stacks Terraform de los 5 (patrón `reputacion/infra` + `infra-modules/cloud-run-service`), agregados a
  `scripts/desplegar-todo.sh`, `scripts/destruir-todo.sh` y a la matriz del CI.

### Fase 3: Journey local de punta a punta
- `implementacion/journey/`: docker-compose con los 9 servicios + Pulsar + mocks; suite pytest que recorre
  JRN-01..05 **por el BFF** y verifica el estado final por `correlation_id` y en el Saga Log.
- Colección Postman "Journey E5" **solo vía BFF** (caso exitoso y caso con compensación) + environment.

### Fase 4: GCP y experimentos
- `PROJECT=… scripts/desplegar-todo.sh` (primera corrida real de los scripts: actualizar ESTADO §3).
- Medir los 3 escenarios oficiales dentro del journey: **ESC-01** (k6 contra Siniestros vía BFF + corrida con el
  atajo como línea base), **DISP-02** (ráfaga de novedades con el CRM limitado durante el pico), **MOD-02**
  (pago en BR con MercadoPago sin tocar el core). `experimento-runner` produce datos crudos y
  `validador-hipotesis` da el veredicto H1/H0.
- Observabilidad contra el despliegue real: `QUERIES-GCP-JOURNEYS.md` probado consulta por consulta, dashboard
  "HdA E5" en Grafana (servicios, journey, `tipo_comunicacion`, Saga Log por Postgres, backlog de Pulsar), URLs
  y Swagger de los 9 servicios en `ESTADO-IMPLEMENTACION.md`.
- Guardar la evidencia en el repo (capturas, exportes de k6/Newman, salidas SQL) y correr `scripts/destruir-todo.sh`.
- El sistema **no queda encendido**: se redespliega a demanda para la sustentación con `RUNBOOK-SUSTENTACION.md`
  (hueco 2); la URL del BFF es la misma en cada redespliegue.

### Fase 5: Documento, refinamiento y video
- Documento final: resultados cuantitativos y cualitativos + conclusiones por escenario; **topología de datos**
  (qué y para qué); **modelo de datos por servicio** (qué y por qué); **tipos de eventos** y su porqué;
  **versionamiento de esquemas y de API**; AsyncAPI; justificación de GCP.
- Refinar el mapa de contextos TO-BE (`03-…cml`, validarlo y regenerar su imagen) y las 4 vistas, **justificando
  cada cambio con los resultados**; aplicar `diagramas/entrega-5/CORRECCIONES.md` (se suman BFF y coordinador).
- Video: un tramo por escenario + la saga (exitosa y compensada) mostrada con `consultas-saga-log.sql` +
  explicación de eventos y esquemas (incluye un cambio incompatible rechazado por el registry).
- `ACTIVIDADES.md` con lo que hizo realmente cada integrante.

## Contratos, documentación y retrocompatibilidad (síncrono, asíncrono, módulos y datos)

Un contrato por cada frontera, documentado **y** protegido por una prueba o chequeo automático:

| Frontera | Documentación | Versionamiento | Regla de retrocompatibilidad | Cómo se hace cumplir |
|---|---|---|---|---|
| **Asíncrono entre servicios** (comandos y eventos en Pulsar) | **AsyncAPI** (`asyncapi/hda-asyncapi.yaml`): cada canal con productor, consumidores, esquema, tipo (comando / integración con carga de estado / delgado) y versión; HTML generado (`asyncapi/html/`) enlazado desde el documento | Schema Registry de Pulsar; `version_esquema` en las propiedades; cambio que rompe → tópico `…v2` | **BACKWARD**: solo campos nuevos con valor por defecto; no se borra ni renombra un campo ni se cambia su tipo; los consumidores ignoran campos desconocidos (*tolerant reader*); `…v1` y `…v2` conviven hasta que migre el último consumidor | Pulsar rechaza el esquema incompatible; pruebas de contrato contra AsyncAPI (§9 de CONVENCIONES); en el video, un cambio incompatible rechazado |
| **Síncrono: BFF** (actores → sistema) | **OpenAPI/Swagger** en `<bff>/docs` y `openapi.json` exportado a `bff/openapi/` en el repo; colección Postman generada a partir de él | Ruta `/v1/…`; una versión nueva `/v2` convive con la anterior y se anuncia la deprecación con el header `Deprecation` | Dentro de `/v1`: solo se agregan endpoints, campos opcionales de entrada y campos de salida; nunca se quita un campo ni se cambia un código de respuesta | CI con **oasdiff** (`oasdiff breaking`) que compara el `openapi.json` del PR contra `main` y **falla si hay un cambio que rompe** |
| **Síncrono: API de cada servicio** (BFF → servicio) | OpenAPI en `<servicio>/docs` y `openapi.json` exportado a `<servicio>/openapi/`; URLs en `ESTADO-IMPLEMENTACION.md` | Ruta `/v1/…` en todos los servicios (los endpoints actuales sin prefijo se mantienen como alias hasta migrar la colección de la Entrega 4) | Las mismas del BFF | El mismo chequeo oasdiff por servicio; el BFF tiene pruebas de contrato contra el `openapi.json` de cada servicio que consume |
| **Entre módulos del mismo servicio** | Interfaz pública del módulo = sus **comandos, consultas y eventos de dominio** en `application/` (DTOs); documentada en el README del servicio con un diagrama de módulos | No se versiona: se cambia en el mismo PR que sus usuarios (mismo servicio, mismo despliegue) | Ningún módulo importa `domain/` ni `infrastructure/` de otro; si una firma cambia, se actualizan todos sus usuarios en el mismo PR | Prueba de arquitectura por servicio (`tests/unit/test_arquitectura.py`) que revisa los imports prohibidos entre módulos y del dominio hacia afuera |
| **Datos** (BD por servicio) | **Topología descentralizada** justificada frente a centralizada e híbrida (A26, §3.4) y **modelo de datos por servicio** (tablas o event store, qué agregado guarda cada una, CRUD o ES y por qué) en el documento | Migraciones versionadas por servicio (`alembic`, o scripts `sql/NNN_*.sql` si el servicio no usa alembic) | Migraciones **expand/contract**: primero se agrega la columna o tabla nueva, se migra el código y después se quita la vieja; nunca un cambio destructivo en la misma versión | La suite de integración corre las migraciones desde cero contra el Postgres del compose |

Tareas: fase 0 (reglas en CONVENCIONES §3 y el chequeo oasdiff y la prueba de arquitectura en la plantilla de
servicio); en cada servicio de las fases 1-2 (exportar su `openapi.json`, sus migraciones y su entrada en AsyncAPI);
fase 5 (sección "Contratos y evolución" del documento con esta tabla, AsyncAPI en HTML y enlaces a cada Swagger).

## Cobertura de la rúbrica: 5 huecos cerrados (agregados el 2026-09-21)

| # | Hueco | Tarea | Fase |
|---|---|---|---|
| 1 | Consultar el Saga Log con un **cliente de BD** en GCP | `implementacion/gestion-de-trabajos/sql/README.md`: conexión a la Cloud SQL de GT con **Cloud SQL Auth Proxy** (`cloud-sql-proxy <connection_name>` + psql/DBeaver) y, como alternativa, `gcloud sql connect`; probarlo contra el despliegue real antes de grabar | 4 |
| 2 | **Link del BFF vivo para el tutor**, con redespliegue **a demanda** | (a) Documentar la URL **determinista** del BFF (`https://<servicio>-<número-de-proyecto>.<región>.run.app`, no cambia entre redespliegues en el mismo proyecto) como el link oficial. (b) `implementacion/RUNBOOK-SUSTENTACION.md`: redesplegar con `desplegar-todo.sh` al menos 40 min antes, humo con Newman "Journey E5", datos de demo cargados por script, y `destruir-todo.sh` al terminar. (c) Medir cuánto tarda el despliegue completo y dejarlo escrito. (d) En el README y el documento: "el sistema se levanta a demanda para la sustentación", con el link y la colección | 4 |
| 3 | **H1/H0 por escenario dentro del journey**, escritas antes de medir | Plan de experimento por JRN-02, JRN-03 y JRN-04 (H1, H0, variables, casos, umbrales, amenazas a la validez) en `implementacion/journey/PLAN-EXPERIMENTOS.md`, siguiendo el formato de `proveedores/plan.md`. Lo revisa `validador-hipotesis` antes de correr | 3 |
| 4 | **Indicar los cambios** en el mapa de contextos y las vistas | Agregar BFF y coordinador de sagas a `03-contextos-acotados-TO-BE.cml` y a las 4 `.puml`; marcar en cada diagrama lo **nuevo o cambiado en E5** (color + leyenda); `contexto/17-refinamiento-arquitectura.md` con la tabla de cambios (Entrega 1/2 → Entrega 5: qué cambió, por qué, **qué resultado lo motivó**) | 5 |
| 5 | **DDD visible en el documento**, no solo en el código | Por servicio: diagrama de capas cebolla (dominio ← aplicación ← infraestructura/API), puertos y adaptadores (inversión de dependencias), agregados con entidades y objetos valor, y los módulos con su comunicación. Verificado por `rubrica-auditor` contra el código (imports del dominio limpios, repositorios como puertos) | 5 |

## Reparto de roles

| Integrante | Rol | Qué hace | Qué sustenta |
|---|---|---|---|
| Jhoan | Implementación e integración | Implementa en su local con agentes las fases 0-3 (los 9 servicios) siguiendo la definición de terminado; despliegue en GCP, scripts, CI, runbook de sustentación y link del BFF (hueco 2), Postman, ESC-01, Grafana | Implementación, despliegue, BFF, ESC-01 |
| Frans | Saga y experimentos | Revisa y prueba el coordinador y el Saga Log; hipótesis H1/H0 (hueco 3); SQL del Saga Log y conexión con cliente (hueco 1); corre y documenta DISP-02 y el caso de compensación del video | Saga, orquestación, disponibilidad |
| Daniel | Contratos, arquitectura y documento | AsyncAPI y revisión de Swagger; refinamiento del mapa de contextos y las vistas con la tabla de cambios (hueco 4); DDD por servicio y topología de datos (hueco 5); corre MOD-02 | DDD, esquemas y versionamiento, topología, modificabilidad |

Los tres: revisan y aprueban los PRs de su área, graban su tramo del video y describen en `ACTIVIDADES.md` lo
que hizo cada uno. Todos preparan la sustentación de todo (el 70 % de la nota).

## Archivos críticos

- Diseño: `contexto/15-arquitectura-entrega-5.md`, `contexto/0{4,5,6,7}-vista-*.puml`, `contexto/03-contextos-acotados-TO-BE.cml`
- Cómo construir y desplegar: `implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`, `implementacion/ESTADO-IMPLEMENTACION.md`, `implementacion/scripts/*.sh`, `.github/workflows/pr-quality-gate.yml`
- Código base a reutilizar: `gestion-de-trabajos/app/infrastructure/messaging/publicador_pulsar.py`, `gestion-de-trabajos/app/infrastructure/adapters/throttler_crm.py`, `proveedores/app/common/pulsar_topology.py`, `proveedores/app/domain/verificacion/servicio_elegibilidad.py`, `pagos/app/domain/pagos/regla_regional.py`, `pagos/app/infrastructure/adapters/pasarela_*.py`, `reputacion/app/infrastructure/persistence/event_store_sqlalchemy.py`, `infra-modules/cloud-run-service/`
- Contratos: `asyncapi/hda-asyncapi.yaml`, `postman/*.json`

## Verificación

1. Por servicio: `pytest tests/unit tests/integracion` en verde; `ruff check` y `ruff format --check`; CI verde en su PR.
2. Contratos síncronos: `/docs` de cada servicio y del BFF responde; `oasdiff breaking` pasa contra `main`; un
   cambio que quita un campo de `/v1` hace fallar el CI. Prueba de arquitectura de imports en verde en cada servicio.
3. Contrato asíncrono: publicar en Pulsar local un mensaje con cada esquema del catálogo y ver la reacción; `pulsar-admin schemas get <tópico>` muestra el esquema; un cambio incompatible es rechazado.
4. Sin regresión: los tests actuales (GT 21, Pagos 19, Reputación 9, Proveedores 17) y CP-1..CP-7 de DISP-03 siguen pasando.
5. Journey local: `docker compose -f journey/docker-compose.yml up` + suite JRN-01..05 por el BFF; en el Saga Log (`consultas-saga-log.sql`) una saga `SAGA_COMPLETADA` y otra `SAGA_COMPENSADA` con sus pasos.
6. Observabilidad: en Logs Explorer, `jsonPayload.correlation_id="<trabajo>"` devuelve el recorrido por los 9
   servicios con `bounded_context`, `modulo`, `tipo_mensaje` y `tipo_comunicacion` en cada línea; cada consulta de
   `QUERIES-GCP-JOURNEYS.md` devuelve resultados; el dashboard "HdA E5" muestra los 9 servicios y el Saga Log.
7. Sustentación: con todo apagado, `RUNBOOK-SUSTENTACION.md` levanta el sistema en el tiempo medido, la URL
   documentada del BFF responde y Newman "Journey E5" pasa; una consulta del Saga Log funciona desde DBeaver/psql
   por el Cloud SQL Auth Proxy.
8. GCP: `scripts/desplegar-todo.sh` → Newman "Journey E5" contra la URL del BFF → k6 ESC-01, ráfaga DISP-02, prueba MOD-02 → veredicto de `validador-hipotesis` → `scripts/destruir-todo.sh` → `scripts/verificar-nada-facturando.sh` en 0.

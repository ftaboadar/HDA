# Consultas de GCP para trazar los journeys de la Entrega 5

Reemplaza en la Entrega 5 a [`QUERIES-GCP-POR-ESCENARIO.md`](QUERIES-GCP-POR-ESCENARIO.md) (que sigue
valiendo como referencia de los 4 escenarios sueltos de la Entrega 4). Implementa
[`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md) §13.

> ## ⚠ Estado: BORRADOR SIN PROBAR (2026-09-21)
>
> **Nada está desplegado en GCP** (`ESTADO-IMPLEMENTACION.md` §1) y la Etapa 1 de la implementación
> sigue abierta. Todas las consultas de este archivo se escribieron **contra los contratos** (campos de
> log de `gestion-de-trabajos/app/common/logging_utils.py`, tópicos y suscripciones de
> `asyncapi/hda-asyncapi.yaml`, tablas del Saga Log de 15-…md §7.1) y **ninguna se ejecutó todavía**
> contra un despliegue real. Cada bloque lleva la marca `probada 2026-09-21`.
>
> **Qué hacer cuando exista el despliegue (paso 2.3 de la guía):** correr cada consulta, pegar una
> muestra real de salida debajo (como hace el archivo de la Entrega 4 con DISP-03), cambiar la marca a
> `probada <fecha>` y anotar en §9 cualquier campo que haya faltado.
>
> Las consultas que dependen de un campo que **todavía nadie emite** están marcadas
> `⛔ requiere campo pendiente` y listadas en §9.

Proyecto: `<PROJECT>` (hoy el del equipo es `hogaralpes`; sustituir en cada consulta) ·
Región: `southamerica-east1`.

---

## 1. Dónde se pega cada cosa

| Tipo de consulta | Dónde | Link |
|---|---|---|
| `resource.type="cloud_run_revision" …` | **Logs Explorer** | `https://console.cloud.google.com/logs/query?project=<PROJECT>` |
| `fetch …` (MQL) | **Metrics Explorer** → `< >` → `MQL` | `https://console.cloud.google.com/monitoring/metrics-explorer?project=<PROJECT>` |
| `histogram_quantile(…)` (PromQL) | **Metrics Explorer** → `< >` → `PromQL` | mismo link |
| `SELECT …` (Saga Log) | psql/DBeaver contra la Cloud SQL de GT | ver `gestion-de-trabajos/sql/README.md` (paso 2.4) |
| `bin/pulsar-admin …` | SSH por IAP a la VM de Pulsar | ver §7.4 |
| Todo lo anterior, junto | **Grafana**, dashboard **"HdA E5"** | `observabilidad/` → `terraform output grafana_url` |

---

## 2. Nombres: carpeta, `jsonPayload.servicio` y servicio de Cloud Run

`jsonPayload.servicio` es el **nombre de la carpeta** y es el mismo en la API y en el worker; el nombre
del servicio de Cloud Run (distinto para cada uno) va en `jsonPayload.servicio_cloud_run` y en
`resource.labels.service_name`. **Para trazar negocio se filtra por `jsonPayload.servicio`; para métricas
de infraestructura, por `resource.labels.service_name`.**

| Servicio (carpeta = `jsonPayload.servicio`) | Cloud Run API | Cloud Run worker | Estado del stack |
|---|---|---|---|
| `gestion-de-trabajos` | `gestion-trabajos-poc-api` | `gestion-trabajos-poc-worker` | existe (worker nuevo en E5) |
| `proveedores` | `proveedores-poc-api` | `proveedores-poc-worker` | hoy desplegado como `disp03-poc-*`; A20 lo renombra |
| `pagos` | `pagos-poc-api` | `pagos-poc-worker` | existe (worker nuevo en E5) |
| `reputacion` | `reputacion-poc-api` | `reputacion-poc-worker` | existe (worker nuevo en E5) |
| `marketplace` | `marketplace-poc-api` | `marketplace-poc-worker` | **stack por crear** |
| `siniestros` | `siniestros-poc-api` | `siniestros-poc-worker` | **stack por crear** |
| `suscripciones` | `suscripciones-poc-api` | `suscripciones-poc-worker` | **stack por crear** |
| `scoring` | `scoring-poc-api` | `scoring-poc-worker` | **stack por crear** |
| `bff` | `bff-poc-api` | — (no consume Pulsar) | **stack por crear** |

Mocks (no son de los 9): `mocks-pagos-poc-mock-stripe`, `mocks-pagos-poc-mock-mercadopago`,
`mocks-crm-poc-mock-crm`, `disp03-poc-mock-{policia,rues,certificadora}`.

> Los nombres de los 5 stacks por crear salen de la convención `<entorno>-<service_name>` con
> `entorno = <servicio>-poc` (CONVENCIONES §6) y `service_name ∈ {api, worker}` (§5). **Confirmarlos con
> `gcloud run services list` después del despliegue**; si alguno cambia, corregir esta tabla, la variable
> `servicio` del dashboard y la §6 de este archivo.

---

## 3. Campos de log que usan estas consultas

Puestos por `logging_utils.log_evento(...)` (plantilla en `gestion-de-trabajos/app/common/logging_utils.py`).

| Campo | Valores | De dónde sale |
|---|---|---|
| `servicio` | las 9 carpetas de §2 | constante `SERVICIO` del módulo |
| `dominio`, `subdominio`, `tipo_subdominio`, `bounded_context` | `CONTEXTO_DDD` de cada servicio | constante por servicio |
| `capa` | `api`, `application`, `domain`, `infrastructure`, `worker`, `mocks`, `common` | primer segmento del nombre del logger |
| `modulo`, `agregado` | `ciclo_vida`, `workflow`, `agenda`, `Trabajo`, `Pago`… | lo pasa quien llama a `log_evento` |
| `correlation_id` | `trabajo_id` (paso 0: `proveedor_id`) | `contexto_journey(...)` en la entrada |
| `saga_id`, `paso_saga` | uuid de la saga / nombre del paso | `contexto_journey(...)` |
| `tipo_comunicacion` | `intra_modulo`, `entre_modulos_sync`, `entre_modulos_async`, `entre_servicios_comando`, `entre_servicios_evento`, `rest_bff`, `externo` | lo pasa quien llama (valor fuera de la lista = error) |
| `tipo_mensaje` | `comando`, `consulta`, `evento_de_dominio`, `evento_de_integracion`, `mensajeria`, `compensacion`, `aplicacion` | **se infiere del prefijo de `evento`** salvo que se pase explícito |
| `evento` | nombre del evento de log | primer argumento de `log_evento` |
| `severity`, `trace_id` | nativos de Cloud Logging | del `JsonFormatter` |

**Inferencia de `tipo_mensaje` (importante para no escribir consultas falsas):**
`evento_dominio_*` → `evento_de_dominio` · `evento_integracion_*` → `evento_de_integracion` ·
`comando_*` → `comando` · `consulta_*` → `consulta` · `compensacion_*` → `compensacion` ·
`mensaje_*` → `mensajeria` · cualquier otro → `aplicacion`.

> Consecuencia: **un comando de saga que sale por Pulsar se loguea como `mensaje_publicado`, o sea
> `tipo_mensaje="mensajeria"`, no `"comando"`.** Para separar comando de evento en el bus hay que usar
> `tipo_comunicacion` (`entre_servicios_comando` vs `entre_servicios_evento`) o el `topico`. Todas las
> consultas de §5 lo hacen así.

Eventos de mensajería que emite el seedwork (`app/seedwork/infraestructura/pulsar/mensajeria.py`):

| `evento` | Campos propios |
|---|---|
| `mensaje_publicado` | `canal`, `topico`, `tipo_evento`, `message_id`, `id_evento`, `causation_id`, `correlation_id`, `version_esquema`, `tipo_comunicacion`, `duracion_publicacion_ms` |
| `mensaje_recibido` | `canal`, `topico`, `suscripcion`, `tipo_evento`, `message_id`, `id_evento`, `causation_id`, `reentregas`, `tipo_comunicacion` |
| `mensaje_fallido` | `topico`, `tipo_evento`, `id_evento`, `reentregas`, `va_a_dlq`, `error` |
| `mensaje_duplicado_ignorado` | `topico`, `tipo_evento`, `id_evento` |
| `mensaje_sin_manejador` | `topico`, `tipo_evento`, `id_evento` |
| `consumidor_iniciado` | `topico`, `suscripcion`, `topico_dlq`, `tipos` |

---

## 4. Por journey

Todas usan `correlation_id` = `trabajo_id`. Se obtiene del `POST` al BFF (header/campo `X-Correlation-Id`
o `trabajo_id` de la respuesta) o del `GET /v1/sagas/{id}`.

### 4.0 La consulta estrella: el journey completo, los 9 servicios `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
```

Ordenar **ascendente** por tiempo. Debe verse el recorrido entre servicios: `marketplace` →
`gestion-de-trabajos` → `proveedores` → canal → `pagos` → fan-out (`reputacion`, `scoring`,
`suscripciones`, `siniestros`).

En terminal, ya formateada (esta es la forma pensada para el video):

```bash
gcloud logging read '
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
' --project <PROJECT> --order=asc --freshness=1h \
  --format="table[no-heading](timestamp.date('%H:%M:%S'), jsonPayload.servicio, jsonPayload.modulo, jsonPayload.tipo_comunicacion, jsonPayload.evento, jsonPayload.paso_saga)"
```

Verificación de la medida (d) de JRN-01 ("100 % del journey visible con un solo `correlation_id`"):
la lista de `jsonPayload.servicio` distintos que devuelve esa consulta debe contener los servicios que
el journey toca:

```bash
gcloud logging read 'resource.type="cloud_run_revision" jsonPayload.correlation_id="PEGAR_TRABAJO_ID"' \
  --project <PROJECT> --freshness=1h --format="value(jsonPayload.servicio)" | sort -u
```

### 4.1 La saga de ese trabajo, paso a paso `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.saga_id="PEGAR_SAGA_ID"
```

Solo los mensajes que mueven la saga (comandos del coordinador y sus respuestas):

```
resource.type="cloud_run_revision"
jsonPayload.saga_id="PEGAR_SAGA_ID"
jsonPayload.tipo_comunicacion=("entre_servicios_comando" OR "entre_servicios_evento")
jsonPayload.evento=("mensaje_publicado" OR "mensaje_recibido")
```

La fuente de verdad de la saga **no** son los logs sino el Saga Log en la BD de GT (§8).

### 4.2 JRN-01 — Marketplace de punta a punta con la certificadora caída `probada 2026-09-21`

Paso 0 (registro y verificación del proveedor; el `correlation_id` aquí es el `proveedor_id`):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.correlation_id="PEGAR_PROVEEDOR_ID"
```

Las verificaciones que agotaron reintentos y su reproceso (heredado de DISP-03, A24: la cola de
Verificación pasa de Pub/Sub a Pulsar; si el equipo deja Pub/Sub, usar además §6.6):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.evento=~"verificacion_intento_fallido|verificacion_reintentos_agotados|verificacion_reencolada_desde_dlq|mensaje_fallido"
```

Medida (a) "0 trabajos asignados a un proveedor con verificación pendiente o en DLQ": el
`proveedor_id` no debe aparecer en ningún `ElegiblesPublicados` anterior al reproceso.

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.evento="mensaje_publicado"
jsonPayload.tipo_evento="ElegiblesPublicados"
```
> El cuerpo del evento no va en el log; para ver si el proveedor está en la lista hay que abrir el
> mensaje con `pulsar-admin` (§7.4) o consultar `GET /v1/trabajos/{id}/elegibles` en el BFF.
> ⛔ requiere campo pendiente si se quiere resolver solo con logs: ver §9 (7).

### 4.3 JRN-02 — Pico 4x de siniestros (ESC-01) `probada 2026-09-21`

Aceptaciones por el canal de siniestros durante el pico:

```
resource.type="cloud_run_revision"
jsonPayload.servicio="siniestros"
jsonPayload.evento=~"siniestro_aprobado|mensaje_publicado"
jsonPayload.tipo_evento="SiniestroAprobado"
```

Los **4 consumidores** de `trabajos.finalizado` (medida (a) del journey):

```
resource.type="cloud_run_revision"
jsonPayload.evento="mensaje_recibido"
jsonPayload.topico="persistent://hda/gestion-trabajos/trabajos.finalizado"
```
Agrupar por `jsonPayload.suscripcion`: deben aparecer las 4 (`reputacion-`, `scoring-`,
`suscripciones-`, `proveedores-trabajos.finalizado`).

```bash
gcloud logging read '
resource.type="cloud_run_revision" jsonPayload.evento="mensaje_recibido"
jsonPayload.topico="persistent://hda/gestion-trabajos/trabajos.finalizado"
' --project <PROJECT> --freshness=1h --format="value(jsonPayload.suscripcion)" | sort | uniq -c
```

Lag por consumidor (medida heredada: ≤ 120 s): se calcula cruzando `message_id` entre la publicación y
cada recepción — el `message_id` de Pulsar es el mismo en los dos lados.

```
resource.type="cloud_run_revision"
jsonPayload.message_id="PEGAR_MESSAGE_ID"
```
> **Limitación:** hacerlo mensaje a mensaje no escala a una corrida de carga. Para el veredicto de
> ESC-01 el lag se mide con `pulsar-admin topics stats` (§7.4, campos `msgBacklog` y
> `lastConsumedTimestamp` por suscripción), y los logs quedan como evidencia cualitativa.
> ⛔ Para un lag por log haría falta el campo `latencia_entrega_ms` en `mensaje_recibido`: §9 (3).

Mensajes perdidos (medida "0 % perdidos") y duplicados absorbidos por idempotencia:

```
resource.type="cloud_run_revision"
jsonPayload.evento=("mensaje_fallido" OR "mensaje_duplicado_ignorado" OR "mensaje_sin_manejador")
```

Medida (b) "0 trabajos sin elegibles": lista vacía publicada por Proveedores.

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.modulo="elegibilidad"
jsonPayload.evento=~"elegibles_.*vacia|sin_elegibles|fallback_elegibles"
```
> ⛔ requiere campo pendiente: el nombre exacto del evento lo fija quien implemente A12 en
> `proveedores/elegibilidad`. Ver §9 (5).

Medida (c) "0 dobles reservas de la misma franja" (A14):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.modulo="agenda"
jsonPayload.evento=~"reserva_rechazada_franja_ocupada|reserva_confirmada"
```

### 4.4 JRN-03 — Novedades en ráfaga con el CRM limitado (DISP-02) `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.servicio="gestion-de-trabajos"
jsonPayload.modulo=("novedades" OR "integraciones_externas")
```

El CRM visto de los dos lados (el throttler de GT y el mock):

```
resource.type="cloud_run_revision"
(jsonPayload.servicio="gestion-de-trabajos" AND jsonPayload.tipo_comunicacion="externo")
OR resource.labels.service_name="mocks-crm-poc-mock-crm"
```

Novedades por estado y 429 del CRM (heredado de la Entrega 4, sigue valiendo):

```
resource.type="cloud_run_revision"
jsonPayload.evento=~"crm_respuesta_recibida|crm_webhook_rechazado_429|crm_webhook_aceptado|novedad_reintento_programado|novedad_entregada"
```

Medida (a) "100 % de los no-shows terminan reasignados": la rama de compensación parcial
(`LiberarFranja` + vuelta al paso 2).

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
(jsonPayload.tipo_mensaje="compensacion" OR jsonPayload.tipo_evento="LiberarFranja")
```

Medida (b) "0 resoluciones aplicadas sin `DecisionPartner(APROBADA)`" (A11): por cada
`novedad_resuelta` de un trabajo de siniestro debe existir antes un `mensaje_recibido` con
`tipo_evento="DecisionPartner"` del mismo `correlation_id`.

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
(jsonPayload.tipo_evento="DecisionPartner" OR jsonPayload.evento=~"novedad_resuelta|evento_integracion_novedad_resuelta")
```

### 4.5 JRN-04 — Pago en Brasil y disputa (MOD-02) `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.servicio="pagos"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
```

Strategy regional y Adapter de pasarela (misma consulta de la Entrega 4, con los campos nuevos):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="pagos"
jsonPayload.evento=~"regla_regional_aplicada|pasarela_seleccionada|pasarela_cobro_solicitado|pasarela_cobro_respuesta"
```

Ciclo completo del dinero (retener → liberar → compensar), que es lo que prueba la medida (d)
"monto compensado = monto retenido":

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
jsonPayload.tipo_evento=("RetenerPago" OR "PagoRetenido" OR "LiberarPago" OR "PagoLiberado" OR "CompensarPago" OR "PagoCompensado" OR "PagoRetencionFallida" OR "PagoFallido")
```

### 4.6 JRN-05 — Suscripción mensual (MOD-03) `probada 2026-09-21`

Por `suscripcion_id` (es `origen_id`, no el `correlation_id`; cada ciclo tiene su propio trabajo):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="suscripciones"
jsonPayload.suscripcion_id="PEGAR_SUSCRIPCION_ID"
```
> ⛔ requiere campo pendiente: `suscripcion_id` debe ir como campo de `log_evento` en Suscripciones.
> §9 (6).

Consumo de `trabajos.finalizado` sin tocar GT (evidencia de MOD-03):

```
resource.type="cloud_run_revision"
jsonPayload.servicio="suscripciones"
jsonPayload.evento="mensaje_recibido"
jsonPayload.suscripcion="suscripciones-trabajos.finalizado"
```

Medida (c) "franja ocupada rechazada para el segundo cliente":

```
resource.type="cloud_run_revision"
jsonPayload.servicio="proveedores"
jsonPayload.evento="mensaje_publicado"
jsonPayload.tipo_evento="AgendaRechazada"
```

### 4.7 Caso de saga compensada (el del video) `probada 2026-09-21`

Pasarela en modo falla: `RetenerPago` → `PagoRetencionFallida` → `LiberarFranja` → Trabajo `CANCELADO`.

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
(jsonPayload.tipo_mensaje="compensacion"
 OR jsonPayload.tipo_evento=("PagoRetencionFallida" OR "LiberarFranja" OR "CompensarPago" OR "AgendaLiberada")
 OR jsonPayload.evento=~"^compensacion_")
```

Todas las compensaciones del proyecto en una ventana (para contar cuántas sagas compensaron):

```
resource.type="cloud_run_revision"
(jsonPayload.tipo_mensaje="compensacion" OR jsonPayload.tipo_evento=("LiberarFranja" OR "CompensarPago"))
```

---

## 5. Por concepto

### 5.1 Un bounded context completo `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.bounded_context="ContextoGestionDeTrabajos"
```
Valores: `ContextoGestionDeTrabajos`, `ContextoProveedores`, `ContextoPagos`, `ContextoReputacion`,
`ContextoMarketplace`, `ContextoSiniestros`, `ContextoSuscripciones`, `ContextoScoring`
(confirmar el literal en el `CONTEXTO_DDD` de cada servicio al implementarlo).

Solo el núcleo del dominio:

```
resource.type="cloud_run_revision"
jsonPayload.tipo_subdominio="CORE_DOMAIN"
```

### 5.2 Un módulo `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.servicio="gestion-de-trabajos"
jsonPayload.modulo="workflow"
```
Módulos por servicio (CONVENCIONES §1): GT `ciclo_vida|workflow|novedades|integraciones_externas` ·
Proveedores `registro|verificacion|elegibilidad|agenda` · Pagos `liberacion_compensacion|pasarelas` ·
Reputación `calificacion` · Marketplace `diagnostico|publicacion_cotizacion` ·
Siniestros `orquestacion_partner|facturacion` · Suscripciones `ciclo_suscripcion` · Scoring `calculo_score`.

Un módulo y su agregado, por capa (evidencia de DDD en el video):

```
resource.type="cloud_run_revision"
jsonPayload.modulo="agenda"
jsonPayload.agregado="AgendaTecnico"
jsonPayload.capa=("application" OR "domain")
```

### 5.3 Comunicación **entre módulos** del mismo servicio (15-…md §8) `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.servicio="gestion-de-trabajos"
jsonPayload.tipo_comunicacion=("entre_modulos_sync" OR "entre_modulos_async")
```
`entre_modulos_sync` = un módulo llama un comando/consulta del `application/` del otro;
`entre_modulos_async` = evento de dominio por el dispatcher en memoria. Nunca cruza Pulsar.

Solo intra-módulo (lo que pasa dentro de un módulo, para contrastar):

```
resource.type="cloud_run_revision"
jsonPayload.tipo_comunicacion="intra_modulo"
```

### 5.4 Comandos **entre servicios** (la saga, A22) `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.tipo_comunicacion="entre_servicios_comando"
```

Por tópico de comandos (§7.1 del 15 y AsyncAPI):

```
resource.type="cloud_run_revision"
jsonPayload.topico=~"persistent://hda/(proveedores|pagos|siniestros)/comandos"
```

Un comando concreto, del envío a su recepción:

```
resource.type="cloud_run_revision"
jsonPayload.tipo_evento="ReservarFranja"
jsonPayload.evento=("mensaje_publicado" OR "mensaje_recibido")
```
Tipos válidos: Proveedores `PublicarElegibles|ReservarFranja|LiberarFranja` ·
Pagos `RetenerPago|LiberarPago|CompensarPago` · Siniestros `FacturarAPartner|SolicitarAprobacionNovedad`.

### 5.5 Eventos **de dominio** vs **de integración** `probada 2026-09-21`

De dominio (dentro de un servicio, nunca salen al bus):

```
resource.type="cloud_run_revision"
jsonPayload.tipo_mensaje="evento_de_dominio"
```

De integración (salen a Pulsar). Dos formas, según dónde se loguean:

```
resource.type="cloud_run_revision"
(jsonPayload.tipo_mensaje="evento_de_integracion"
 OR (jsonPayload.evento="mensaje_publicado" AND jsonPayload.tipo_comunicacion="entre_servicios_evento"))
```

La traducción dominio → integración de un mismo trabajo (regla 3 del §8: solo la capa de aplicación
traduce, y después de persistir):

```
resource.type="cloud_run_revision"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
jsonPayload.tipo_mensaje=("evento_de_dominio" OR "evento_de_integracion" OR "mensajeria")
```

### 5.6 Compensaciones `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.tipo_mensaje="compensacion"
```
(se infiere sola para cualquier evento de log que empiece por `compensacion_`; ver §3).

Con los comandos de compensación que viajan por el bus:

```
resource.type="cloud_run_revision"
(jsonPayload.tipo_mensaje="compensacion" OR jsonPayload.tipo_evento=("LiberarFranja" OR "CompensarPago"))
```

### 5.7 Llamadas a sistemas **externos** (ACL, circuit breaker, throttler) `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.tipo_comunicacion="externo"
```

Por servicio y su externo: Pagos → Stripe/MercadoPago, GT → CRM/Twilio/S3, Proveedores → Policía/RUES/Certificadora.

```
resource.type="cloud_run_revision"
jsonPayload.tipo_comunicacion="externo"
jsonPayload.servicio="pagos"
```

El mismo tráfico visto desde el mock (el otro lado del adaptador):

```
resource.type="cloud_run_revision"
resource.labels.service_name=~"(mocks-pagos-poc|mocks-crm-poc|disp03-poc)-mock-.*"
```

### 5.8 REST por el BFF `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.tipo_comunicacion="rest_bff"
```

Todo lo que entró por el BFF para un journey:

```
resource.type="cloud_run_revision"
jsonPayload.servicio="bff"
jsonPayload.correlation_id="PEGAR_TRABAJO_ID"
```

### 5.9 Mensajería: publicación ↔ recepción del mismo mensaje `probada 2026-09-21`

```
resource.type="cloud_run_revision"
jsonPayload.message_id="PEGAR_MESSAGE_ID"
```
En Pulsar el `message_id` tiene forma `(ledger,entry,partition,batch)`. Por idempotencia conviene el
`id_evento` (uuid de las propiedades), que sobrevive a una reentrega:

```
resource.type="cloud_run_revision"
jsonPayload.id_evento="PEGAR_ID_EVENTO"
```

Cadena de causalidad (qué mensaje provocó cuál):

```
resource.type="cloud_run_revision"
jsonPayload.causation_id="PEGAR_ID_EVENTO"
```

Mensajes camino a la DLQ:

```
resource.type="cloud_run_revision"
jsonPayload.evento="mensaje_fallido"
jsonPayload.va_a_dlq=true
```

### 5.10 Errores y trazas `probada 2026-09-21`

```
resource.type="cloud_run_revision"
severity>=ERROR
```

```
resource.type="cloud_run_revision"
jsonPayload.trace_id="PEGAR_TRACE_ID"
```

---

## 6. Cloud Monitoring por servicio (MQL y PromQL)

`$SERVICIO` = prefijo de Cloud Run de §2 (ej. `gestion-trabajos-poc`). Todas incluyen **api y worker**
del mismo servicio, y agrupan por `service_name` para verlos separados.

### 6.1 Latencia p95 `probada 2026-09-21`

MQL:
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter resource.service_name =~ '^$SERVICIO-(api|worker)$'
| align delta(1m)
| every 1m
| group_by [resource.service_name], [p95: percentile(value.request_latencies, 95)]
```

PromQL (mismo dato; útil si el equipo prefiere Grafana con sintaxis Prometheus):
```
histogram_quantile(0.95, sum by (service_name, le) (
  rate(run_googleapis_com:request_latencies_bucket{monitored_resource="cloud_run_revision", service_name=~"$SERVICIO-(api|worker)"}[1m])
))
```
> Cloud Monitoring acepta PromQL sobre métricas del sistema traduciendo el nombre
> (`run.googleapis.com/request_latencies` → `run_googleapis_com:request_latencies`, sufijo `_bucket`
> para la distribución). `probada 2026-09-21` contra este proyecto.

Umbral que evalúa: ESC-01 / JRN-02, aceptación p95 < 2 s (2000 ms) en el pico.

### 6.2 Throughput (req/s) `probada 2026-09-21`

```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name =~ '^$SERVICIO-(api|worker)$'
| align rate(1m)
| every 1m
| group_by [resource.service_name, metric.response_code_class], [req_s: aggregate(value.request_count)]
```

PromQL:
```
sum by (service_name, response_code_class) (
  rate(run_googleapis_com:request_count{monitored_resource="cloud_run_revision", service_name=~"$SERVICIO-(api|worker)"}[1m])
)
```

### 6.3 Tasa de 5xx `probada 2026-09-21`

```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name =~ '^$SERVICIO-(api|worker)$' && metric.response_code_class == '5xx'
| align rate(1m)
| every 1m
| group_by [resource.service_name], [err_s: aggregate(value.request_count)]
```

Porcentaje (el que se compara contra "≥ 99,9 % aceptadas"), con `ratio` de MQL:

```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name =~ '^$SERVICIO-(api|worker)$'
| align rate(1m)
| every 1m
| group_by [resource.service_name, metric.response_code_class], [c: aggregate(value.request_count)]
| ratio_of_sum_by [resource.service_name]
```
> `ratio_of_sum_by` no está probado en este proyecto; si falla, usar dos consultas (5xx y total) y el
> panel "5xx (%)" del dashboard, que hace la división en Grafana (`A / B`).

### 6.4 Instancias (auto-escalamiento) `probada 2026-09-21`

```
fetch cloud_run_revision
| metric 'run.googleapis.com/container/instance_count'
| filter resource.service_name =~ '^$SERVICIO-(api|worker)$'
| align mean(1m)
| every 1m
| group_by [resource.service_name, metric.state], [instancias: mean(value.instance_count)]
```
`state` = `active` / `idle`. El worker debe mostrar siempre ≥ 1 (CONVENCIONES §5: `min_instance_count = 1`,
`cpu_idle = false`).

### 6.5 Los 9 servicios en una sola gráfica `probada 2026-09-21`

```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name =~ '^(gestion-trabajos|proveedores|pagos|reputacion|marketplace|siniestros|suscripciones|scoring|bff)-poc-(api|worker)$'
| align rate(1m)
| every 1m
| group_by [resource.service_name], [req_s: aggregate(value.request_count)]
```

### 6.6 Cloud SQL por servicio `probada 2026-09-21`

```
fetch cloudsql_database
| metric 'cloudsql.googleapis.com/database/postgresql/num_backends'
| filter resource.database_id =~ '<PROJECT>:.*-poc-.*'
| align mean(1m)
| every 1m
| group_by [resource.database_id], [conexiones: mean(value.num_backends)]
```
Es la métrica que aisló el cuello de botella de ESC-01 en la Entrega 4 (pool vs. tier vs.
`max_instance_count`); cruzarla con §6.2.

### 6.7 Pub/Sub — solo si Verificación se queda en Pub/Sub `probada 2026-09-21`

A24 dice que **todo** pasa a Pulsar; mientras la cola de Verificación siga en Pub/Sub, su backlog y su
DLQ se ven así:

```
fetch pubsub_subscription
| metric 'pubsub.googleapis.com/subscription/num_undelivered_messages'
| filter resource.subscription_id =~ '.*verificacion-(solicitudes-push|fallidas).*'
| align mean(1m)
| every 1m
| group_by [resource.subscription_id], [sin_entregar: mean(value.num_undelivered_messages)]
```

### 6.8 Backlog de Pulsar `⛔ no hay métrica en Cloud Monitoring`

La VM de Pulsar **no** manda métricas del broker a Cloud Monitoring (no tiene Ops Agent ni un
Prometheus que haga scraping de `:8080/metrics`). Hay tres caminos, en orden de esfuerzo:

1. **`pulsar-admin` por SSH** (§7.4) — es la fuente autoritativa de `msgBacklog` por suscripción.
2. **Proxy por logs**: contar `mensaje_publicado` vs `mensaje_recibido` por tópico. Lo hace el
   dashboard "HdA E5" con las métricas basadas en logs que crea `observabilidad/logging-metrics.tf`:

   ```
   fetch cloud_run_revision
   | { metric 'logging.googleapis.com/user/hda_mensajes_publicados'
     ; metric 'logging.googleapis.com/user/hda_mensajes_recibidos' }
   | align rate(1m)
   | every 1m
   | group_by [metric.topico], [msg_s: aggregate(value)]
   ```
   > La resta publicados − recibidos (backlog acumulado) necesita un `join` de MQL; el dashboard
   > muestra las dos series superpuestas, que para el video es más legible.
3. Desplegar un Prometheus (o el colector de Managed Service for Prometheus) que scrapee el broker —
   **fuera de alcance de la Entrega 5**: es una VM o un GKE más, con su costo, para una métrica que
   `pulsar-admin` ya da.

---

## 7. Comandos fuera de la consola

### 7.1 URLs de todo lo desplegado

```bash
gcloud run services list --region southamerica-east1 --project <PROJECT> --format="table(metadata.name,status.url)"
```

### 7.2 Salud de los 9 servicios

```bash
for s in gestion-trabajos proveedores pagos reputacion marketplace siniestros suscripciones scoring bff; do
  url=$(gcloud run services describe ${s}-poc-api --region southamerica-east1 --project <PROJECT> --format='value(status.url)' 2>/dev/null)
  [ -n "$url" ] && printf '%-16s %s %s\n' "$s" "$(curl -s -o /dev/null -w '%{http_code}' "$url/salud")" "$url"
done
```

### 7.3 Seguir un journey en vivo

```bash
gcloud logging tail 'resource.type="cloud_run_revision" jsonPayload.correlation_id="PEGAR_TRABAJO_ID"' \
  --project <PROJECT> --format="value(jsonPayload.servicio, jsonPayload.evento, jsonPayload.paso_saga)"
```
> `gcloud logging tail` requiere el componente `gcloud beta`/`pubsub` instalado; si falla, usar
> `gcloud logging read` con `--freshness=2m` en un bucle.

### 7.4 Pulsar: backlog, esquemas y contenido de la DLQ

```bash
VM=$(cd pulsar-infra/gcp && terraform output -raw vm_name)
ZONA=$(cd pulsar-infra/gcp && terraform output -raw vm_zone)
SSH="gcloud compute ssh $VM --zone $ZONA --tunnel-through-iap --project <PROJECT> --command"

# Backlog y último consumo por suscripción (lag de ESC-01 / JRN-02)
$SSH 'sudo docker exec hda-pulsar-broker bin/pulsar-admin topics stats persistent://hda/gestion-trabajos/trabajos.finalizado'

# Todos los tópicos de un namespace
$SSH 'sudo docker exec hda-pulsar-broker bin/pulsar-admin topics list hda/proveedores'

# Esquema registrado (A21, evidencia del video)
$SSH 'sudo docker exec hda-pulsar-broker bin/pulsar-admin schemas get persistent://hda/pagos/pago.retenido'

# Contenido de una DLQ (<topico>-<suscripcion>-DLQ, CONVENCIONES §3)
$SSH 'sudo docker exec hda-pulsar-broker bin/pulsar-admin topics peek-messages -s lectura-dlq -n 10 \
  persistent://hda/proveedores/comandos-proveedores-comandos-DLQ'
```

---

## 8. Saga Log (Cloud SQL de GT)

Las consultas completas están en `gestion-de-trabajos/sql/consultas-saga-log.sql` y la conexión por
Cloud SQL Auth Proxy en `gestion-de-trabajos/sql/README.md` (paso 2.4). Estas son las tres que también
usa el dashboard:

Línea de tiempo de una saga `probada 2026-09-21`
```sql
SELECT l.secuencia, l.ocurrido_en, l.paso, l.tipo, l.servicio, l.mensaje, l.id_mensaje
FROM saga_log l
WHERE l.saga_id = 'PEGAR_SAGA_ID'
ORDER BY l.secuencia;
```

Sagas por estado `probada 2026-09-21`
```sql
SELECT estado, count(*) AS sagas
FROM saga_instancia
GROUP BY estado
ORDER BY sagas DESC;
```

Sagas compensadas, con el trabajo y el paso donde se cayeron `probada 2026-09-21`
```sql
SELECT i.saga_id, i.trabajo_id, i.origen, i.paso_actual, i.actualizada_en,
       (SELECT string_agg(DISTINCT l.mensaje, ', ')
          FROM saga_log l
         WHERE l.saga_id = i.saga_id AND l.tipo = 'COMPENSACION_ENVIADA') AS compensaciones
FROM saga_instancia i
WHERE i.estado = 'COMPENSADA'
ORDER BY i.actualizada_en DESC;
```

De la saga al log de GCP (el puente entre las dos pestañas del video):

```sql
SELECT 'jsonPayload.correlation_id="' || trabajo_id || '" OR jsonPayload.saga_id="' || saga_id || '"' AS filtro_logs_explorer
FROM saga_instancia WHERE saga_id = 'PEGAR_SAGA_ID';
```

---

## 9. Campos que faltan para que algunas consultas funcionen

Estado al 2026-09-21, contra el código que hay en la rama. Cada punto es una consulta de arriba que
**no devolverá nada** hasta que quien implemente ese servicio agregue el campo.

| # | Falta | Consulta afectada | Quién lo arregla |
|---|---|---|---|
| 1 | `mensaje_publicado` y `mensaje_recibido` **no llevan `modulo` ni `agregado`** (el seedwork no los recibe) | §5.2 "por módulo" no incluye la mensajería de ese módulo | seedwork de mensajería (pasar `modulo` al construir `PublicadorPulsar`/`ConsumidorPulsar`) |
| 2 | `tipo_comunicacion` de los comandos: el `PublicadorPulsar` usa por defecto `entre_servicios_evento` | §5.4 (comandos) solo funciona si el coordinador publica con `tipo_comunicacion="entre_servicios_comando"` y el `ConsumidorPulsar` de los tópicos `…/comandos` se construye con ese mismo valor | GT·workflow (coordinador) y los consumidores de `comandos` |
| 3 | No hay `latencia_entrega_ms` en `mensaje_recibido` (tiempo entre publicación y consumo) | lag por consumidor de JRN-02 medido con logs; hoy solo se puede con `pulsar-admin` | seedwork (restar `publish_timestamp` del mensaje Pulsar) |
| 4 | `paso_saga` **no lo pone el `ConsumidorPulsar`** (solo `correlation_id` y `saga_id`, y el `saga_id` lo lee del **cuerpo**, no de las propiedades) | la columna `paso_saga` de §4.0 saldrá vacía en los servicios que no lo pongan a mano | seedwork + cada manejador de comando |
| 5 | Nombre del evento de "lista de elegibles vacía" (A12) sin definir | §4.3 medida (b) | proveedores·elegibilidad |
| 6 | `suscripcion_id`, `siniestro_id`, `solicitud_id` no son campos estándar de log | §4.6 y el filtro por canal de origen | marketplace, siniestros, suscripciones |
| 7 | El **cuerpo** de un evento no se loguea (solo sus metadatos) | comprobar "el proveedor X está en `ElegiblesPublicados`" solo con logs (§4.2) | decisión de diseño: se resuelve con `pulsar-admin peek-messages` o con el API del BFF; **no** conviene loguear cuerpos completos bajo carga (costo de Cloud Logging) |
| 8 | `origen` (`MARKETPLACE`/`SINIESTRO`/`SUSCRIPCION`) no está en los logs de GT | separar JRN-02 (siniestros) de JRN-01 (marketplace) en una misma corrida | GT·ciclo_vida: agregarlo a `log_evento` del trabajo creado |
| 9 | Pulsar no publica métricas a Cloud Monitoring | §6.8 | decisión de alcance (ver las 3 opciones allí) |

> Nada de esto cambia un escenario ni un umbral de `escenarios_calidad.md`: son campos de observabilidad.
> Si al correr el experimento una medida **no se puede observar**, eso se reporta como amenaza a la
> validez en `PLAN-EXPERIMENTOS.md`, no se ajusta el umbral.

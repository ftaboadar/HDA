# Queries de GCP para trazar cada escenario de punta a punta

Proyecto: **`hogaralpes`** · Región: **`southamerica-east1`**

Acompaña a la colección de Postman `postman/HdA-Escenarios.postman_collection.json`: primero se
genera el tráfico con Postman, luego se traza con estos queries.

## Dónde se pega cada cosa

| Tipo de query | Dónde | Link directo |
|---|---|---|
| Los que empiezan con `resource.type=...` | **Logs Explorer** | `https://console.cloud.google.com/logs/query?project=hogaralpes` |
| Los que empiezan con `fetch ...` (MQL) | **Metrics Explorer** → botón `MQL` | `https://console.cloud.google.com/monitoring/metrics-explorer?project=hogaralpes` |
| Los `gcloud ...` | Tu terminal | — |
| Todo lo anterior, junto | **Grafana** (panel "Logs de negocio" + variable `Filtro de traza`) | `https://observabilidad-poc-grafana-kgt57ziq4a-rj.a.run.app` |

---

## Mapa de componentes desplegados (para saber qué se está trazando)

```
                    ┌─────────────────────────┐ ── publica ──► Pulsar (VM) tópico trabajos.finalizado
 POST /trabajos ───►│ gestion-trabajos-poc-api│
 POST /novedades ──►│  + Cloud SQL            │ ── webhooks (throttler, 429/Retry-After) ──►
                    └─────────────────────────┘                    mocks-crm-poc-mock-crm  (DISP-02)

                    ┌─────────────────────────┐
 POST /pagos ──────►│      pagos-poc-api      │ ──HTTP /v1/charges────► mocks-pagos-poc-mock-stripe
 (trae los datos    │ Strategy + Adapter      │ ──HTTP /v1/payments───► mocks-pagos-poc-mock-mercadopago
  del trabajo)      │  + Cloud SQL            │                                                    (MOD-02)
                    └─────────────────────────┘

                    ┌─────────────────────────┐   Pub/Sub    ┌────────────────────┐
 POST /verificac. ─►│     disp03-poc-api      │──solicitudes►│  disp03-poc-worker │
                    │      + Cloud SQL        │              └─────────┬──────────┘
                    └─────────────────────────┘                        │ HTTP
                                                                       ▼
                                          disp03-poc-mock-{policia,rues,certificadora}   (DISP-03)

 POST /calificaciones ──► reputacion-poc-api + Cloud SQL (event sourcing)
```

---

# ESC-01 — Escalabilidad (pico 4x)

**Qué se quiere ver:** que el pico entra por Gestión de Trabajos, se acepta rápido, y el otro
dominio (DISP-03) no se degrada.

### 1. Todas las aceptaciones del pico (Logs Explorer)
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.evento="trabajo_creado"
```

### 2. Latencia de aceptación p95 durante el pico (Metrics Explorer, MQL)
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter resource.service_name == 'gestion-trabajos-poc-api'
| align delta(1m)
| every 1m
| group_by [], [p95: percentile(value.request_latencies, 95)]
```

### 3. Throughput alcanzado en el pico (MQL)
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name == 'gestion-trabajos-poc-api'
| align rate(1m)
| every 1m
| group_by [metric.response_code_class], [req_s: aggregate(value.request_count)]
```

### 4. Auto-escalado: cuántas instancias levantó Cloud Run (MQL)
```
fetch cloud_run_revision
| metric 'run.googleapis.com/container/instance_count'
| filter resource.service_name == 'gestion-trabajos-poc-api'
| align mean(1m)
| every 1m
| group_by [metric.state], [instancias: mean(value.instance_count)]
```

### 5. "< 5% de variación en otros dominios": comparar los dos dominios en la misma gráfica (MQL)
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter (resource.service_name == 'gestion-trabajos-poc-api' || resource.service_name == 'disp03-poc-api')
| align delta(1m)
| every 1m
| group_by [resource.service_name], [p95: percentile(value.request_latencies, 95)]
```

### 6. Cuello de botella de Cloud SQL durante el pico (MQL)
```
fetch cloudsql_database
| metric 'cloudsql.googleapis.com/database/postgresql/num_backends'
| filter resource.database_id == 'hogaralpes:gestion-trabajos-poc-gestion-trabajos'
| align mean(1m)
| every 1m
```
> Este es el query que queda pendiente de la sesión anterior: ESC-01 daba p95 de 9.7s y 11.9% de
> fallo contra `hda-projectt` y la causa raíz residual (pool de conexiones vs. tier de Cloud SQL vs.
> `max_instance_count`) nunca se aisló. Cruzar esta métrica con la #3 es cómo se aísla.

### 7. Errores 5xx bajo carga (Logs Explorer)
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
severity>=ERROR
```

---

# DISP-03 — Disponibilidad ante falla de certificadora

**Qué se quiere ver:** el camino completo de UNA verificación cruzando API → Pub/Sub → worker →
mock externo → DLQ → reproceso.

### 1. Traza completa de una verificación (el query estrella)
```
resource.type="cloud_run_revision"
resource.labels.service_name=("disp03-poc-api" OR "disp03-poc-worker")
jsonPayload.verificacion_id="PEGAR_ID_AQUI"
```
Ordenar ascendente por tiempo. Verás la secuencia:
`verificacion_aceptada` → `verificacion_intento_exitoso`/`_fallido` (×N reintentos) →
`evento_dominio_intento_registrado` → `evento_dominio_verificacion_completada` o
`verificacion_reintentos_agotados` → `verificacion_procesada_push`.

En terminal, con la traza ya formateada:
```bash
gcloud logging read '
resource.type="cloud_run_revision"
resource.labels.service_name=("disp03-poc-api" OR "disp03-poc-worker")
jsonPayload.verificacion_id="PEGAR_ID_AQUI"
' --project hogaralpes --order=asc --freshness=30m \
  --format="table[no-heading](timestamp.date('%H:%M:%S'), jsonPayload.evento, jsonPayload.intento, jsonPayload.duracion_ms)"
```

**Salida real de ese comando** (corrida del 2026-09-18, certificadora en `caido` y luego reprocesada
— es exactamente el flujo que ejecuta la carpeta DISP-03 de la colección de Postman):

```
12:37:53  verificacion_aceptada                          <- API acepta en 202, no espera al externo
12:37:54  verificacion_intento_fallido           1
12:37:55  verificacion_intento_fallido           2
12:37:56  verificacion_intento_fallido           3
12:37:59  verificacion_intento_fallido           4       <- backoff exponencial visible en los timestamps
12:37:59  verificacion_reintentos_agotados               <- motivo: HTTP 503 del mock certificadora
12:37:59  evento_dominio_intento_registrado      (x4)
12:37:59  evento_dominio_verificacion_agoto_reintentos   <- el agregado enruta a DLQ
12:37:59  verificacion_procesada_push                    <- 200 a Pub/Sub (no reintenta lo ya resuelto)
12:38:02  verificacion_reencolada_desde_dlq              <- POST /dlq/{id}/reprocesar
12:38:03  verificacion_intento_exitoso           1  189  <- con el externo ya restaurado
12:38:03  evento_dominio_verificacion_completada
12:38:03  verificacion_procesada_push
```

### 2. Los reintentos con backoff (la táctica bajo prueba)
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-worker"
jsonPayload.evento="verificacion_intento_fallido"
```
El campo `jsonPayload.intento` va 1, 2, 3… y los timestamps muestran el backoff exponencial.

### 3. Las que agotaron reintentos y cayeron a la DLQ
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-worker"
jsonPayload.evento="verificacion_reintentos_agotados"
```

### 4. AISLAMIENTO — que policía/RUES no se afectaron mientras la certificadora estaba caída
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-worker"
jsonPayload.evento="verificacion_intento_exitoso"
jsonPayload.tipo_verificador=("policia" OR "rues")
```
Si hay entradas aquí con timestamps DENTRO de la ventana de caída de la certificadora, el
aislamiento por tipo de verificador está funcionando.

### 5. El reproceso desde la DLQ
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-api"
jsonPayload.evento="verificacion_reencolada_desde_dlq"
```

### 6. Pub/Sub — backlog de la suscripción durante la caída (MQL)
```
fetch pubsub_subscription
| metric 'pubsub.googleapis.com/subscription/num_undelivered_messages'
| filter resource.subscription_id == 'disp03-poc-verificacion-solicitudes-push'
| align mean(1m)
| every 1m
```

### 7. Pub/Sub — edad del mensaje más viejo sin ack (indicador de atasco) (MQL)
```
fetch pubsub_subscription
| metric 'pubsub.googleapis.com/subscription/oldest_unacked_message_age'
| filter resource.subscription_id == 'disp03-poc-verificacion-solicitudes-push'
| align mean(1m)
| every 1m
```

### 8. Entregas de Pub/Sub al worker (nivel HTTP, lo genera Cloud Run solo)
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-worker"
logName="projects/hogaralpes/logs/run.googleapis.com%2Frequests"
```

### 9. El mock externo respondiendo caído (el estímulo, visto desde el otro lado)
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-mock-certificadora"
logName="projects/hogaralpes/logs/run.googleapis.com%2Frequests"
httpRequest.status>=500
```

---

# DISP-02 — Disponibilidad ante CRM saturado (throttler)

**Qué se quiere ver:** `POST /novedades` responde 202 de inmediato y el Throttler (token bucket +
reintentos con backoff) entrega los webhooks al CRM respetando su rate limiting (429 + `Retry-After`),
sin perder ninguna novedad y sin degradar a Gestión de Trabajos.

### 1. Traza completa de una novedad (query estrella)
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.novedad_id="PEGAR_NOVEDAD_ID"
```
Secuencia: `novedad_publicada` → (`novedad_reintento_programado` × N si el CRM respondió 429) → `novedad_entregada`
(o `novedad_agotada` si se acabaron los reintentos: queda persistida, no se pierde).

### 2. Los reintentos por rate limiting del CRM
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.evento="novedad_reintento_programado"
```
`jsonPayload.origen_espera="retry_after_crm"` = el throttler respetó el `Retry-After` que mandó el CRM;
`espera_s` es cuánto esperó.

### 3. Novedades que agotaron los reintentos (no perdidas: quedan en estado AGOTADA)
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.evento="novedad_agotada"
```

### 4. El lado del CRM: cuántos 429 emitió
```
resource.type="cloud_run_revision"
resource.labels.service_name="mocks-crm-poc-mock-crm"
logName="projects/hogaralpes/logs/run.googleapis.com%2Frequests"
httpRequest.status=429
```

### 5. "Disponibilidad de Gestión de Trabajos independiente del CRM" (MQL)
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter resource.service_name == 'gestion-trabajos-poc-api'
| align delta(1m)
| every 1m
| group_by [], [p95: percentile(value.request_latencies, 95)]
```
La latencia de `POST /novedades` debe mantenerse plana aunque el CRM esté devolviendo 429.

### 6. Reproducir el estímulo a mano (límite bajo en el CRM)
```bash
curl -X POST https://mocks-crm-poc-mock-crm-kgt57ziq4a-rj.a.run.app/_control/config \
  -H "Content-Type: application/json" -d '{"limite_rps": 2}'      # restaurar con 50
```

---

# MOD-02 — Modificabilidad (Strategy regional + Adapter de pasarela)

**Qué se quiere ver:** el mismo `POST /pagos` cobrando dos regiones, cada una con su Strategy
(`ReglaColombia`/`ReglaBrasil`) y su Adapter (`PasarelaStripe` → centavos enteros /
`PasarelaMercadoPago` → unidades), sin cambios de código entre una y otra. `POST /pagos` recibe los
datos del trabajo en el body (Pagos es un microservicio independiente, no consume eventos).

### 1. Traza completa de un pago (query estrella)
```
resource.type="cloud_run_revision"
resource.labels.service_name="pagos-poc-api"
jsonPayload.pago_id="PEGAR_PAGO_ID"
```
Salida real (pago CO por Stripe y luego compensado):
```
13:00:02  application.dispatcher_eventos_dominio  evento_dominio_pago_despachado
13:00:02  application.commands.pagar_trabajo      pago_procesado          stripe  EXITOSO
13:00:02  api.main                                pago_creado
13:00:05  application.commands.compensar          pago_compensado
13:00:05  api.main                                pago_compensado_via_api
```

### 2. De trabajo a pago, cruzando los dos servicios
```
resource.type="cloud_run_revision"
resource.labels.service_name=("gestion-trabajos-poc-api" OR "pagos-poc-api")
jsonPayload.trabajo_id="PEGAR_TRABAJO_ID"
```

### 3. Qué pasarela usó cada pago (Strategy/Adapter elegidos)
```
resource.type="cloud_run_revision"
resource.labels.service_name="pagos-poc-api"
jsonPayload.evento="pago_procesado"
```
`jsonPayload.pasarela` y `jsonPayload.estado` en cada línea.

### 4. Pagos fallidos y su motivo
```
resource.type="cloud_run_revision"
resource.labels.service_name="pagos-poc-api"
severity>=ERROR
```

### 5. Llamadas HTTP que recibió cada pasarela (el Adapter visto desde el otro lado)
```
resource.type="cloud_run_revision"
resource.labels.service_name=("mocks-pagos-poc-mock-stripe" OR "mocks-pagos-poc-mock-mercadopago")
logName="projects/hogaralpes/logs/run.googleapis.com%2Frequests"
```
Stripe recibe `POST /v1/charges`, MercadoPago `POST /v1/payments`.

### 6. CO y BR sobre la MISMA revisión (evidencia de "0 redespliegues")
Mismo query del punto 3 → en Logs Explorer mirar `resource.labels.revision_name`: una sola revisión
para ambas regiones.

### 7. La evidencia de "0 líneas modificadas en el core" es un diff, no un log
```bash
git log --oneline -- experimento-arquitectura/implementacion/pagos/app/infrastructure/adapters/
git diff <commit_antes>..<commit_despues> -- experimento-arquitectura/implementacion/pagos/app/domain/
```

---

# Queries transversales (útiles para cualquier escenario)

### Todo el detalle de negocio, de todos los servicios, ordenado
```
resource.type="cloud_run_revision"
jsonPayload.evento:*
```

### Solo errores, en todo el proyecto
```
resource.type="cloud_run_revision"
severity>=ERROR
```

### Seguir un id concreto sin saber en qué servicio está
```
resource.type="cloud_run_revision"
(jsonPayload.verificacion_id="PEGAR_ID" OR jsonPayload.trabajo_id="PEGAR_ID" OR jsonPayload.pago_id="PEGAR_ID")
```

### Salud de la VM de Pulsar (no tiene agente de logs — solo métricas de infraestructura) (MQL)
```
fetch gce_instance
| metric 'compute.googleapis.com/instance/cpu/utilization'
| filter resource.instance_id != ''
| align mean(1m)
| every 1m
```
> **Limitación conocida:** los contenedores de Pulsar (broker/bookie/zookeeper) **no** envían sus
> logs a Cloud Logging — la VM no tiene Ops Agent instalado. Para ver actividad real del broker:
> ```bash
> gcloud compute ssh pulsar-poc-vm --zone southamerica-east1-a --tunnel-through-iap --project hogaralpes \
>   --command "sudo docker exec hda-pulsar-broker bin/pulsar-admin topics stats persistent://hda/gestion-trabajos/trabajos.finalizado"
> ```

---

# Lo mismo, dentro de Grafana

El dashboard **HdA — Cloud Run** ahora incluye el datasource `Google Cloud Logging`, así que no hace
falta salir a la consola de GCP para ver el detalle de logs:

1. Abre `https://observabilidad-poc-grafana-kgt57ziq4a-rj.a.run.app` (usuario `admin`; contraseña:
   `gcloud secrets versions access latest --secret observabilidad-poc-grafana-admin-password --project hogaralpes`).
2. Panel **"Logs de negocio — todos los servicios"**: muestra cada `log_evento` estructurado con
   todos sus campos (click en una línea → *Log details* despliega `evento`, `verificacion_id`,
   `intento`, `duracion_ms`, `motivo_falla`…).
3. Para trazar un flujo concreto, usa la variable de arriba **"Filtro de traza (opcional)"** y pega
   una línea de filtro, por ejemplo:
   ```
   jsonPayload.verificacion_id="13b3695d-605c-40ae-9b74-5f5f75279c40"
   ```
4. Panel **"Logs de ERROR"**: severity ≥ ERROR de todos los servicios, incluyendo trazas de
   excepción de Python.

---

## Campos nuevos en los logs (detalle por escenario y por concepto DDD)

Cada log de negocio trae ahora, además de `evento` y los ids: `severity` (nativo de GCP), `servicio`, `revision`, `capa`
(api/application/domain/infrastructure/worker), `dominio`, `subdominio`, `tipo_subdominio`, `bounded_context`, `tipo_mensaje`
y `trace_id`. Ver [MENSAJERIA-Y-DATOS.md](MENSAJERIA-Y-DATOS.md) para el significado de cada uno.

### A. Todos los logs de UNA petición, entre capas (el trace)
```
resource.type="cloud_run_revision"
jsonPayload.trace_id="<TRACE_ID>"
```
El `trace_id` está en cualquier log de la petición (`http_request_completada`, `trabajo_creado`…). También correlaciona con el log de
petición de Cloud Run: `trace="projects/hogaralpes/traces/<TRACE_ID>"`. Hacia pasarelas y verificadores el trace se propaga, así que el mock
lo comparte.

### B. Por concepto DDD
```
jsonPayload.bounded_context="ContextoPagos"            # un contexto
jsonPayload.tipo_subdominio="CORE_DOMAIN"              # solo subdominios núcleo
jsonPayload.tipo_mensaje="evento_de_dominio"           # comando | evento_de_dominio | evento_de_integracion | mensajeria
jsonPayload.capa="infrastructure" jsonPayload.tipo_mensaje="mensajeria"   # solo adaptadores de mensajería
```

### C. ESC-01 — dónde se va el tiempo de un POST /trabajos
```
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.evento=~"http_request_completada|comando_crear_trabajo_ejecutado|mensaje_publicado"
```
Campos: `duracion_persistencia_ms` (INSERT en Cloud SQL) vs `duracion_despacho_ms` (registro elegible + publicación Pulsar),
`requests_concurrentes` (contra `max_instance_request_concurrency`=15), `pool_db_en_uso`/`pool_db_tamano`/`pool_db_overflow`.
En la prueba de humo, ~380 ms de ~405 ms eran la publicación a Pulsar; la base tomó ~24 ms.

### D. Mensajería: publicación ↔ recepción del MISMO mensaje
```
jsonPayload.message_id="<MESSAGE_ID>"
```
`mensaje_publicado` (disp03-poc-api) y `mensaje_recibido` (disp03-poc-worker) comparten `message_id`; el segundo agrega `suscripcion`,
`intento_entrega_pubsub`, `encoding_transporte=base64`. Todo evento: `formato_serializacion`, `version_esquema`, `tamano_bytes`, `topico`.
En Pulsar el `message_id` tiene forma `(ledger,entry,-1,-1)`.

### E. DISP-02 — el CRM visto de ambos lados
```
jsonPayload.evento=~"crm_respuesta_recibida|crm_webhook_rechazado_429|crm_webhook_aceptado|novedad_reintento_programado"
```
Lado gestión: `status_http`, `retry_after_s`, `espera_token_bucket_ms`, `cola_pendiente`. Lado CRM: `requests_en_ventana` vs `limite_rps`.
`novedad_entregada.latencia_extremo_a_extremo_ms` = tiempo desde que se aceptó (202) hasta la entrega real.
Para provocar 429 con poco tráfico usa el paso 4 (ráfaga de 8) del folder DISP-02 en Postman.

### F. MOD-02 — Strategy y Adapter en acción
```
resource.labels.service_name="pagos-poc-api"
jsonPayload.evento=~"regla_regional_aplicada|pasarela_seleccionada|pasarela_cobro_solicitado|pasarela_cobro_respuesta"
```
Compara `pasarela_cobro_solicitado.monto_enviado` (20000, `centavos_entero`, Stripe) con el de MercadoPago (200, `unidades_decimal`) para el mismo
`monto_dominio` = "200.00".

### G. DISP-03 — intento y verificador externo
`verificacion_intento_*` trae `intento`/`max_intentos`/`adaptador`/`nivel_reintento`; `verificador_externo_respuesta` trae `status_http` y
`duracion_ms`; el mock registra `mock_verificacion_recibida` con `modo_inyectado` (ok/caido) y `latencia_inyectada_ms`.

> En una corrida real de ESC-01 desplegar gestion-de-trabajos y pagos con `-var log_detalle=minimo` para apagar los logs de trazado fino.

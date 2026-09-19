# Guía de demostración — los 4 escenarios de punta a punta (Postman/Newman → GCP → Grafana)

Para correr y grabar la demo: **ESC-01, DISP-03, DISP-02, MOD-02**, cada uno con (1) qué correr,
(2) qué mostrar en la consola de GCP y con qué query, (3) qué mostrar en Grafana, (4) qué código enseñar y
(5) un guion para el video. Todo fue ensayado con Newman contra el proyecto `hogaralpes` (región `southamerica-east1`)
y las salidas de ejemplo son reales.

> **Alcance honesto (decirlo en el video):** esta demo es una **prueba de humo con tráfico mínimo** para ver el
> mecanismo y su traza completa. Las cifras de carga real (p95 con 500+ req/s, ráfaga de 2.000 novedades…) son de
> corridas anteriores medidas con k6/pytest y están en `RESULTADOS-ESCALABILIDAD-GCP.md`, `RESULTADOS-DISP02.md`,
> `proveedores/RESULTADOS-DISP03.md` y `RESULTADOS-MOD02.md`. La demo no las reemplaza.

---

## 0. Antes de empezar (checklist de 5 minutos)

```bash
gcloud auth login && gcloud config set project hogaralpes      # cuenta con acceso al proyecto
npm i -g newman                                                  # una vez (Node 18+)
cd experimento-arquitectura/implementacion/postman
```

1. **Calentar los servicios** (Cloud Run arranca en frío y una verificación puede demorarse): corre una vez
   `newman run HdA-Escenarios.postman_collection.json -e HdA-GCP.postman_environment.json` y espera que termine. En la
   grabación usa la segunda corrida.
2. **Ventana de tiempo:** anota la hora antes de cada escenario (`date -u +%FT%TZ`) para filtrar logs.
3. **Grafana:** abre el dashboard **"HdA — Cloud Run: p95 / throughput / tasa de error"**, rango `Last 15 minutes`, refresco 10 s.
4. **Pestañas abiertas:** Logs Explorer, Cloud Run, Pub/Sub, Grafana, Postman (o terminal con Newman) y el editor con el código.

### Dónde sale cada URL / credencial

| Qué | Cómo obtenerlo |
|---|---|
| URLs de todos los servicios | `gcloud run services list --region southamerica-east1 --project hogaralpes --format="value(metadata.name,status.url)"` (también están en `HdA-GCP.postman_environment.json`) |
| Swagger de cada API (para mostrar los endpoints) | `<url>/docs` — funciona en gestión-trabajos, pagos y disp03 |
| Usuario de Grafana | `admin` |
| Contraseña de Grafana | `gcloud secrets versions access latest --secret=observabilidad-poc-grafana-admin-password --project hogaralpes` |
| URL de Grafana | `https://observabilidad-poc-grafana-kgt57ziq4a-rj.a.run.app` |

| Servicio (Cloud Run) | Rol |
|---|---|
| `gestion-trabajos-poc-api` | Gestión de Trabajos: `POST /trabajos` (ESC-01), `POST /novedades` (DISP-02) |
| `disp03-poc-api` / `disp03-poc-worker` | Servicio **Proveedores** (carpeta `proveedores/`): API que acepta y worker que procesa la verificación (escenario DISP-03). El prefijo `disp03-poc` es el nombre histórico de los recursos desplegados |
| `disp03-poc-mock-{policia,rues,certificadora}` | Sistemas externos simulados (se les inyecta la falla) |
| `mocks-crm-poc-mock-crm` | CRM externo simulado con rate limit (DISP-02) |
| `pagos-poc-api` + `mocks-pagos-poc-mock-{stripe,mercadopago}` | Pagos y pasarelas (MOD-02) |
| `observabilidad-poc-grafana` | Grafana |

### Enlaces de la consola de GCP (proyecto `hogaralpes`)

- Logs Explorer: `https://console.cloud.google.com/logs/query?project=hogaralpes`
- Cloud Run: `https://console.cloud.google.com/run?project=hogaralpes`
- Pub/Sub (tópicos): `https://console.cloud.google.com/cloudpubsub/topic/list?project=hogaralpes`
- Cloud SQL: `https://console.cloud.google.com/sql/instances?project=hogaralpes`
- Metrics Explorer: `https://console.cloud.google.com/monitoring/metrics-explorer?project=hogaralpes`
- VM de Pulsar: `https://console.cloud.google.com/compute/instances?project=hogaralpes`

**Cómo usar Logs Explorer:** pega la query en el editor, ajusta el rango arriba a la derecha (`Last 30 minutes`), `Run query`.
Las líneas de una query se combinan con AND. En cada log abre el desplegable para ver el `jsonPayload` completo.

---

## 1. Cómo correr las colecciones

### Opción A — Postman (interfaz, la mejor para el video)
1. `Import` → los 3 archivos de `implementacion/postman/`: `HdA-Escenarios.postman_collection.json`,
   `HdA-GCP.postman_collection.json` (endpoints por servicio) y `HdA-GCP.postman_environment.json`.
2. Arriba a la derecha elige el environment **HdA - GCP (hogaralpes)**.
3. Clic derecho en la carpeta del escenario → `Run folder` → en el Runner:
   - **ESC-01:** Iterations `20`, Delay `150 ms`.
   - **DISP-03:** Iterations `1`, Delay **`10000 ms`** (los pasos piden esperar reintentos de 5–30 s).
   - **DISP-02** y **MOD-02:** Iterations `1`, sin delay.
4. Ver los `Test Results` en verde y, en ESC-01, la `Console` (View → Show Postman Console) con el reporte final.

### Opción B — Newman (terminal, las mismas colecciones)
```bash
cd experimento-arquitectura/implementacion/postman
C=HdA-Escenarios.postman_collection.json ; E=HdA-GCP.postman_environment.json

newman run $C -e $E --folder "ESC-01 — Escalabilidad (pico 4x)" -n 20 --delay-request 150
newman run $C -e $E --folder "DISP-03 — Disponibilidad ante falla de certificadora" --delay-request 10000
newman run $C -e $E --folder "DISP-02 — Disponibilidad ante CRM saturado (throttler)"
newman run $C -e $E --folder "MOD-02 — Modificabilidad (Strategy regional + Adapter de pasarela)"
```
Resultado del ensayo: ESC-01 **62/62** aserciones (20 iteraciones), DISP-03 **11/11**, DISP-02 **5/5**, MOD-02 **12/12**.
Si DISP-03 falla una aserción justo después de un despliegue, es un arranque en frío: repítelo (con `--delay-request 10000` pasa).

---

## 2. ESC-01 — Escalabilidad (pico de 4x en `trabajos.finalizado`)

**Qué se demuestra:** `POST /trabajos` acepta trabajo con latencia < 2 s (≥ 99,9 % aceptadas) mientras otro dominio
(`POST /verificaciones`) sigue sano, y el evento `TrabajoFinalizado` sale a Apache Pulsar.

### Correr
```bash
date -u +%FT%TZ            # anota la hora
newman run $C -e $E --folder "ESC-01 — Escalabilidad (pico 4x)" -n 20 --delay-request 150
```
Salida esperada (real): `Solicitudes totales: 20 · Aceptadas (201): 20 (100.00%) · p95 aceptación: 321 ms · p95 otro dominio: 650 ms`.
Cada iteración hace: `POST /trabajos` (201), `POST /verificaciones` en otro dominio (202) y, al final, el reporte de umbrales.

### Mostrar en GCP — Logs Explorer
**1) Los trabajos aceptados, cada uno con su latencia y la ocupación de la instancia:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gestion-trabajos-poc-api"
jsonPayload.evento="http_request_completada"
jsonPayload.ruta="/trabajos"
```
Campos a señalar: `duracion_ms` (latencia real), `requests_concurrentes` (vs. `max_instance_request_concurrency`=15),
`pool_db_en_uso` / `pool_db_tamano` (pool de conexiones a Cloud SQL), `status` 201.

**2) La traza completa de UN trabajo, por capas** (copia un `trace_id` del log anterior):
```
resource.type="cloud_run_revision"
jsonPayload.trace_id="<TRACE_ID>"
```
Lo que se ve, en orden (real):

| # | `evento` | `tipo_mensaje` · `capa` | Detalle |
|---|---|---|---|
| 1 | `evento_dominio_trabajo_finalizado_emitido` | evento_de_dominio · application | el agregado `Trabajo` emite `TrabajoFinalizado` |
| 2 | `registro_trabajo_elegible_guardado` | aplicacion · application | reacción intra-servicio |
| 3 | `mensaje_publicado` | mensajeria · infrastructure | `canal=pulsar`, `topico=persistent://hda/gestion-trabajos/trabajos.finalizado`, `message_id=(3241,14,-1,-1)`, `formato_serializacion=json`, `version_esquema=1`, `tamano_bytes=191` |
| 4 | `evento_integracion_trabajo_finalizado_publicado` | evento_de_integracion · application | traducción dominio → integración |
| 5 | `comando_crear_trabajo_ejecutado` | comando · application | `duracion_persistencia_ms=23.7` · `duracion_despacho_ms=378.9` · `duracion_total_ms=402.6` |
| 6 | `http_request_completada` | aplicacion · api | `status=201`, `duracion_ms=405.7` |

**Hallazgo para contar:** de ~405 ms, ~380 ms son publicar a Pulsar y ~24 ms la base de datos. El cuello no es Cloud SQL.

**3) Todos los eventos con su contexto DDD** (para explicar contextos y subdominios):
```
resource.type="cloud_run_revision"
jsonPayload.bounded_context="ContextoGestionDeTrabajos"
jsonPayload.tipo_mensaje=~"comando|evento_de_dominio|evento_de_integracion|mensajeria"
```
Cada línea trae `dominio=MarketplaceDeServicios`, `subdominio=GestionDeTrabajos`, `tipo_subdominio=CORE_DOMAIN`.

**Otras consolas:** Cloud Run → `gestion-trabajos-poc-api` → *Metrics* (request count, latencia p95, instancias). En Cloud Run → *Revisions* muestra
`min 1 / max 9`, `concurrency 15`, `2 vCPU`. Métricas de instancias / Cloud SQL: `QUERIES-GCP-POR-ESCENARIO.md` (sección ESC-01, MQL 2–6).

### Mostrar en Grafana
- Panel **"Tráfico (req/s) — todos los servicios"**: sube la línea de `gestion-trabajos-poc-api` y `disp03-poc-api` durante el run.
- Variable **Servicio Cloud Run = `gestion-trabajos-poc-api`** → paneles *Latencia p95*, *Throughput*, *Tasa de error 5xx*.
- Panel de logs **"ESC-01 — flujo POST /trabajos (comando → evento de dominio → evento de integración → Pulsar)"**: mismo detalle de la tabla anterior.
- Para seguir un trabajo: variable **Filtro de traza** = `jsonPayload.trace_id="<TRACE_ID>"`.

### Código a enseñar
- Endpoint: [gestion-de-trabajos/app/api/main.py:180](gestion-de-trabajos/app/api/main.py#L180) (`POST /trabajos`) y el middleware de telemetría en [:85](gestion-de-trabajos/app/api/main.py#L85).
- Comando (CQS, retorna solo el id): [crear_trabajo.py:45](gestion-de-trabajos/app/application/commands/crear_trabajo.py#L45).
- Dominio → integración: [dispatcher_eventos_dominio.py:50](gestion-de-trabajos/app/application/dispatcher_eventos_dominio.py#L50).
- Publicación en Pulsar (JSON + propiedades de versión): [publicador_pulsar.py:90](gestion-de-trabajos/app/infrastructure/messaging/publicador_pulsar.py#L90).
- Dimensionamiento (concurrencia 15 = pool 10 + overflow 5, 2 vCPU): [infra/service.tf:67](gestion-de-trabajos/infra/service.tf#L67).

### Guion del video (~3 min)
1. "ESC-01: el pico de 4x de trabajos finalizados no debe degradar la aceptación ni a otros dominios." Muestra el Swagger de `POST /trabajos`.
2. Corre Newman/Runner. Señala p95 y 100 % aceptadas.
3. En Logs Explorer pega la query 1 y luego la 2: recorre la tabla de la traza (comando → evento de dominio → evento de integración → Pulsar).
4. Di el hallazgo (380 ms en Pulsar, 24 ms en base de datos) y que el desglose sale del propio log.
5. Grafana: tráfico y latencia. **Cierra con el límite:** "esto es humo; el pico real (500+ req/s, p95 ≈ 5,4 s con 0 % de fallo tras subir a 2 vCPU) está medido en `RESULTADOS-ESCALABILIDAD-GCP.md`, corridas 9–10". Con 1 vCPU no cumplía el umbral de 2 s: ese hallazgo está declarado ahí.

---

## 3. DISP-03 — Disponibilidad ante falla de un sistema externo (certificadora caída)

**Qué se demuestra:** la API acepta (202) aunque la certificadora esté caída; el worker reintenta con backoff, agota y manda a la DLQ;
policía y RUES no se afectan; el reproceso desde la DLQ completa la verificación. Cola = Cloud Pub/Sub.

### Correr
```bash
date -u +%FT%TZ
newman run $C -e $E --folder "DISP-03 — Disponibilidad ante falla de certificadora" --delay-request 10000
```
Pasos de la carpeta: (1) certificadora en modo OK → (2) verificación sana → (3) confirma `COMPLETADA` → (4) **estímulo: certificadora `caido`** →
(5) verificación contra certificadora caída → (6) **aislamiento**: otro verificador sigue aceptando → (7) ver la DLQ → (8) restaurar, reprocesar, confirmar `COMPLETADA`.

### Mostrar en GCP — Logs Explorer
**1) La traza de la verificación que cayó a la DLQ** (toma el `verificacion_id` con `jsonPayload.evento="verificacion_reintentos_agotados"`):
```
resource.type="cloud_run_revision"
jsonPayload.verificacion_id="<VERIFICACION_ID>"
```
Lo que se ve (real, con tiempos):

| Hora | Servicio | `evento` | Detalle |
|---|---|---|---|
| :15.075 | disp03-poc-api | `verificacion_aceptada` | comando `IniciarVerificacion`, estado PENDIENTE, 202 inmediato |
| :15.2 | disp03-poc-worker | `mensaje_recibido` | `suscripcion=…-solicitudes-push`, `intento_entrega_pubsub=1`, mismo `message_id` que el publicado, `encoding_transporte=base64` |
| :15.259 | worker | `verificacion_intento_fallido` | `intento 1/4`, `adaptador=AdaptadorCertificadora` |
| :16.327 | worker | `verificacion_intento_fallido` | `intento 2/4` (backoff ~1 s) |
| :18.133 | worker | `verificacion_intento_fallido` | `intento 3/4` (backoff ~2 s) |
| :20.257 | worker | `verificacion_intento_fallido` + `verificacion_reintentos_agotados` | `intento 4/4`, `motivo_falla: HTTP 503 de …certificadora` |
| :20.3 | worker | `evento_dominio_verificacion_agoto_reintentos` | evento de dominio → se publica a la DLQ (`mensaje_publicado`, `topico=disp03-poc-verificacion-fallidas`) |
| :48.338 | api | `verificacion_reencolada_desde_dlq` | el reproceso manual (`POST /dlq/{id}/reprocesar`) |
| :48.629 | worker | `verificacion_intento_exitoso` → `evento_dominio_verificacion_completada` | ya con la certificadora restaurada; queda `COMPLETADA` |

**2) El mismo mensaje visto en el publicador y en el suscriptor** (topología Pub/Sub, `message_id` idéntico en `mensaje_publicado` y `mensaje_recibido`):
```
resource.type="cloud_run_revision"
jsonPayload.tipo_mensaje="mensajeria"
resource.labels.service_name=~"disp03-poc-(api|worker)"
```
**3) El estímulo visto del otro lado (el mock diciendo que está caído):**
```
resource.type="cloud_run_revision"
resource.labels.service_name="disp03-poc-mock-certificadora"
jsonPayload.evento="mock_verificacion_recibida"
jsonPayload.modo_inyectado="caido"
```
**4) Aislamiento:** compara `resource.labels.service_name="disp03-poc-mock-policia"` (todas 200, `modo_inyectado=ok`) con la certificadora (503).

**Otras consolas:** Pub/Sub → tópicos `disp03-poc-verificacion-solicitudes`, `…-fallidas` (DLQ) y `…-eventos-integracion`; la suscripción `…-solicitudes-push`
(ack deadline 30 s, retry 1–20 s, dead-letter tras 5 entregas). Cloud Run → `disp03-poc-worker` → Logs y *Metrics* (503 hacia el mock no aparecen aquí; los 503 salen en el mock).
Métricas de backlog/edad del mensaje: `QUERIES-GCP-POR-ESCENARIO.md` (DISP-03, MQL 6–7).

### Mostrar en Grafana
- Panel de logs **"DISP-03 — cola: solicitud → Pub/Sub → worker → reintentos → DLQ (api + worker + mocks)"** con la misma secuencia.
- Panel de tráfico: se ven `disp03-poc-worker` y `disp03-poc-mock-certificadora` con actividad; en *Tasa de error 5xx* con `Servicio = disp03-poc-mock-certificadora` sube el 5xx del estímulo.
- Filtro de traza = `jsonPayload.verificacion_id="<VERIFICACION_ID>"`.

### Código a enseñar
- Reintento con backoff exponencial y jitter (tenacity): [proveedores/app/worker/core.py:63](proveedores/app/worker/core.py#L63).
- Consumidor push, idempotencia ante redelivery de Pub/Sub: [push_handler.py:100](proveedores/app/worker/push_handler.py#L100).
- Publicación a Pub/Sub con atributos de versión: [proveedores/app/common/publicador.py](proveedores/app/common/publicador.py) (`PublicadorPubSub._publicar`).
- Topología: [proveedores/infra/pubsub.tf:63](proveedores/infra/pubsub.tf#L63) (`dead_letter_policy`, 5 entregas).
- Reproceso: [reprocesar_desde_dlq.py:16](proveedores/app/application/commands/reprocesar_desde_dlq.py#L16).

### Guion del video (~4 min)
1. "DISP-03: si un externo falla, aceptamos igual, reintentamos con backoff y, si se agota, queda en una DLQ recuperable."
2. Corre la carpeta (o el Runner). Señala la aserción "API sigue aceptando con el externo caído" y "Otro verificador acepta normal".
3. Logs Explorer, query 1: recorre la tabla (4 intentos con espera creciente, agotamiento, DLQ, reproceso).
4. Query 3: "el mock respondió 503 en modo `caido`". Query 4 para el aislamiento.
5. Pub/Sub en la consola: tópicos y la política de dead-letter. Explica *at-least-once* y por qué el worker es idempotente.
6. Límite: 11/13 verificaciones mecánicas en GCP real, 2 bugs que solo aparecieron en GCP (ver `proveedores/RESULTADOS-DISP03.md`).

---

## 4. DISP-02 — Disponibilidad ante CRM saturado (Sidecar/Throttler)

**Qué se demuestra:** Gestión de Trabajos acepta novedades (202) sin esperar al CRM; el throttler dosifica con token bucket, respeta
`Retry-After` ante el 429 y no pierde ninguna novedad.

### Correr
```bash
date -u +%FT%TZ
newman run $C -e $E --folder "DISP-02 — Disponibilidad ante CRM saturado (throttler)"
```
Pasos: (1) límite del CRM a **2 rps** → (2) crea un trabajo → (3) `POST /novedades` (202) → (4) **ráfaga de 8 novedades en paralelo** → (5) consulta el estado → (6) restaura el límite (50).
El 429 aparece en la ráfaga; las 8 novedades acaban `ENTREGADA` unos segundos después (el throttler reintenta en segundo plano; si consultas enseguida verás `PENDIENTE` con `intentos` = 1).

### Mostrar en GCP — Logs Explorer
**1) El ciclo de UNA novedad** (toma un `novedad_id` de `jsonPayload.evento="novedad_reintento_programado"`):
```
resource.type="cloud_run_revision"
jsonPayload.novedad_id="<NOVEDAD_ID>"
```
Real:

| Hora | Servicio | `evento` | Detalle |
|---|---|---|---|
| :58.576 | gestion-trabajos-poc-api | `mensaje_novedad_encolada` | `canal=cola_en_memoria_asyncio`, `cola_pendiente` |
| :58.577 | gestion-trabajos-poc-api | `novedad_publicada` | 202, agregado `Novedad` |
| :58.655 | **mocks-crm** | `crm_webhook_rechazado_429` (WARNING) | `requests_en_ventana=2`, `limite_rps=2`, `retry_after_s=1` |
| :58.660 | gestion-trabajos-poc-api | `crm_respuesta_recibida` (WARNING) | `status_http=429`, `retry_after_s=1`, `intento=1` |
| :58.671 | gestion-trabajos-poc-api | `novedad_reintento_programado` | `espera_s=1`, `origen_espera=retry_after_crm` |
| +13 s | mocks-crm / gestión | `crm_webhook_aceptado` → `crm_respuesta_recibida` (200) → `novedad_entregada` | `intentos=2`, `latencia_extremo_a_extremo_ms` |

Se ve el mismo hecho desde **los dos lados** del CRM (cliente y servidor).

**2) Cuántos 429 y cuántas entregas hubo (resumen):**
```
resource.type="cloud_run_revision"
jsonPayload.evento=~"crm_webhook_rechazado_429|crm_webhook_aceptado|novedad_entregada|novedad_agotada"
```
**3) Solo los rechazos:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="mocks-crm-poc-mock-crm"
severity>=WARNING
```
**4) El estado final por API:** `GET <gestion>/novedades/<NOVEDAD_ID>` → `"estado":"ENTREGADA","intentos":2` (paso 5 de Postman).

**Otras consolas:** Cloud Run → `mocks-crm-poc-mock-crm` → *Metrics*: request count con la mezcla 200/429 por `response_code_class` (usa `Group by: response_code`).

### Mostrar en Grafana
- Panel de logs **"DISP-02 — throttler: novedad → cola → token bucket → CRM (429 / reintento / entrega)"**.
- Panel de tráfico: aparece `mocks-crm-poc-mock-crm`. Con `Servicio = mocks-crm-poc-mock-crm` en *Tasa de error 5xx* no se ve el 429 (es 4xx): para eso está el panel de logs.

### Código a enseñar
- Token bucket: [throttler.py:62](gestion-de-trabajos/app/infrastructure/messaging/throttler.py#L62); reintento con `Retry-After` o backoff: [throttler.py:184](gestion-de-trabajos/app/infrastructure/messaging/throttler.py#L184).
- Adaptador HTTP hacia el CRM (429 → `Retry-After`): [throttler_crm.py:33](gestion-de-trabajos/app/infrastructure/adapters/throttler_crm.py#L33).
- Mock del CRM (ventana deslizante de 1 s): [mocks-crm/app/main.py:100](mocks-crm/app/main.py#L100).
- Decisión y riesgos documentados: `contexto/escenarios_calidad.md` (columna DISP-02) y el diagrama C&C `06-vista-cyc.puml` (conector `ACL Agentes (throttler + reintento)`).

### Guion del video (~3 min)
1. "DISP-02: el CRM externo limita la tasa; nuestro sistema no puede caerse ni perder novedades por eso."
2. Corre la carpeta. Muestra que el 202 sale en pocos cientos de ms **aunque el CRM esté al límite**.
3. Logs Explorer, query 1: recorre la tabla (cola → 429 → `Retry-After` → reintento → entregada) y remarca "los dos lados".
4. Dile a Postman/`curl` el `GET /novedades/{id}` → `ENTREGADA`.
5. Límites honestos: bucket y cola **en memoria por instancia** (con N instancias la tasa es N × límite); sin DLQ propia para `AGOTADA`; el mock solo modela rate limiting, no caída total. Cifras de carga: 2.000/2.000 entregadas en ≈126 s (`RESULTADOS-DISP02.md`).

---

## 5. MOD-02 — Modificabilidad (Strategy regional + Adapter de pasarela)

**Qué se demuestra:** el mismo endpoint cobra en Colombia (COP vía Stripe) y en Brasil (BRL vía MercadoPago) sin `if` por país;
las diferencias (región/moneda y contrato de cada pasarela) las absorben Strategy y Adapter.

### Correr
```bash
date -u +%FT%TZ
newman run $C -e $E --folder "MOD-02 — Modificabilidad (Strategy regional + Adapter de pasarela)"
```
8 pasos: trabajo CO → trabajo BR → cobro CO (Stripe, COP, referencia `ch_*`) → cobro BR (MercadoPago, BRL, referencia numérica) → compensación → segunda compensación rechazada (409).

### Mostrar en GCP — Logs Explorer
**1) El cobro de un pago, decisión por decisión:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="pagos-poc-api"
jsonPayload.evento=~"comando_pagar_trabajo_recibido|regla_regional_aplicada|pasarela_seleccionada|pasarela_cobro_solicitado|pasarela_cobro_respuesta|pago_procesado"
```
Real, lado a lado:

| Paso | Colombia | Brasil |
|---|---|---|
| `regla_regional_aplicada` (patrón **Strategy**) | `regla=ReglaColombia`, `moneda=COP` | `regla=ReglaBrasil`, `moneda=BRL` |
| `pasarela_seleccionada` (patrón **Adapter**) | `adaptador=PasarelaStripe` | `adaptador=PasarelaMercadoPago` |
| `pasarela_cobro_solicitado` | `endpoint=/v1/charges`, **`monto_enviado=20000`**, `unidad_monto=centavos_entero` | `endpoint=/v1/payments`, **`monto_enviado=200`**, `unidad_monto=unidades_decimal` |
| (mismo `monto_dominio`) | `"200.00"` | `"200.00"` |
| `pasarela_cobro_respuesta` | `status_http=200`, `referencia_externa=ch_…` | `status_http=200`, `referencia_externa=96324304` |
| `pago_procesado` | `estado=EXITOSO`, `duracion_total_ms≈1900` | `estado=EXITOSO` |

El punto clave: **el dominio razona en unidades (200.00) y el Adapter de Stripe traduce a centavos (20000)** — eso es lo que MOD-02 quiere ver.

**2) Compensación (paso de Saga) y su invariante:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="pagos-poc-api"
jsonPayload.evento=~"pago_compensado|evento_dominio_pago_despachado"
```
El segundo intento de compensar devuelve 409 (invariante del agregado `Pago`), visible en Cloud Run → `pagos-poc-api` → *Metrics* como una respuesta 4xx.

**3) Las pasarelas recibiendo la llamada** (nivel HTTP): en Logs Explorer `resource.labels.service_name=~"mocks-pagos-poc-mock-(stripe|mercadopago)"`.

**Otras consolas:** Cloud Run → *Services* muestra que **Colombia y Brasil corren en la MISMA revisión** de `pagos-poc-api` (cero redespliegues por país).

### Mostrar en Grafana
- Panel de logs **"MOD-02 — pagos: regla regional (Strategy) → pasarela (Adapter) → cobro → compensación"**.
- Panel de tráfico: `pagos-poc-api`, `mocks-pagos-poc-mock-stripe` y `…-mercadopago`.
- Filtro de traza = `jsonPayload.pago_id="<PAGO_ID>"`.

### Código a enseñar
- Orquestación (sin `if` por país): [pagar_trabajo.py:50](pagos/app/application/commands/pagar_trabajo.py#L50) — las reglas y pasarelas se resuelven por diccionario.
- Puerto: [pasarela_de_pago.py:28](pagos/app/application/ports/pasarela_de_pago.py#L28).
- Strategies: [regla_colombia.py:16](pagos/app/infrastructure/adapters/regla_colombia.py#L16), [regla_brasil.py:15](pagos/app/infrastructure/adapters/regla_brasil.py#L15).
- Adapters: [pasarela_stripe.py](pagos/app/infrastructure/adapters/pasarela_stripe.py) (centavos enteros) y [pasarela_mercadopago.py](pagos/app/infrastructure/adapters/pasarela_mercadopago.py) (unidades decimales).
- Evidencia de modificabilidad (0 líneas modificadas en `ReglaColombia`/`PasarelaStripe` al agregar Brasil): `RESULTADOS-MOD02.md`, sección "Control de versiones".

### Guion del video (~3 min)
1. "MOD-02: agregar un país o una pasarela no debe tocar el código de los que ya existen."
2. Corre la carpeta. Muestra CO=COP/Stripe y BR=BRL/MercadoPago desde el **mismo** `POST /pagos`.
3. Logs Explorer, query 1: tabla lado a lado (Strategy, Adapter y la conversión 200.00 → 20000).
4. Código: `pagar_trabajo.py` sin condicionales por país; las dos reglas y los dos adapters.
5. Cierra con `RESULTADOS-MOD02.md`: el diff de agregar Brasil no toca lo existente.

---

## 6. Guion global del video (~15 min)

| Min | Bloque |
|---|---|
| 0–1 | Contexto: 4 escenarios, PoC en GCP `hogaralpes`, arquitectura (Cloud Run, Cloud SQL, Pub/Sub, Pulsar). `MENSAJERIA-Y-DATOS.md` como mapa de contextos y tópicos. |
| 1–4 | **ESC-01** (sección 2) |
| 4–8 | **DISP-03** (sección 3) |
| 8–11 | **DISP-02** (sección 4) |
| 11–14 | **MOD-02** (sección 5) |
| 14–15 | Cierre: qué se probó aquí (humo con traza completa) vs. dónde están las cifras de carga (documentos de resultados); límites y pendientes declarados. |

Conceptos que la demo deja ver en los logs y que se pueden nombrar cuando el profesor pregunte:

| Concepto | Dónde se ve |
|---|---|
| Contexto acotado / subdominio / dominio | campos `bounded_context`, `subdominio`, `tipo_subdominio` (CORE/GENERIC), `dominio` en cada log |
| Comando / consulta (CQS) | `tipo_mensaje=comando`; el comando retorna solo el id |
| Evento de dominio vs. de integración | `tipo_mensaje=evento_de_dominio` vs. `evento_de_integracion` (misma traza en ESC-01) |
| Pub/Sub, suscriptor, consumidor push | `mensaje_publicado` / `mensaje_recibido` con `suscripcion`, `intento_entrega_pubsub` (DISP-03) |
| Pulsar, tópico, `message_id` | `mensaje_publicado` en ESC-01 (`canal=pulsar`) |
| Formato del mensaje y versión | `formato_serializacion=json`, `version_esquema=1`, `tamano_bytes`; por qué JSON y no Avro: `MENSAJERIA-Y-DATOS.md` §4 |
| Contrato asíncrono | [asyncapi/hda-asyncapi.yaml](asyncapi/hda-asyncapi.yaml) |
| Hexagonal | campo `capa` (api / application / infrastructure) |

---

## 7. Qué está y qué no está probado (para no sobrevender)

| Evidencia | Qué prueba | Dónde |
|---|---|---|
| Pruebas unitarias (66) | dominio, comandos, adapters (gestión 21, pagos 19, DISP-03 17, reputación 9) | `pytest tests/unit` en cada servicio |
| Esta demo (Newman contra GCP) | el mecanismo funciona de punta a punta y es trazable en logs | secciones 2–5 |
| Carga real de ESC-01 (k6, `hda-projectt`) | p95 y tasa de fallo bajo pico 4x | `RESULTADOS-ESCALABILIDAD-GCP.md` (corridas 9–10: p95 ≈ 5,2–5,5 s, 0 % fallo, 551 req/s; el umbral de 2 s **no** se cumplió con 1 vCPU y quedó como hallazgo) |
| DISP-03 local vs. GCP | 13/13 local, 11/13 en GCP, 2 bugs propios de GCP | `proveedores/RESULTADOS-DISP03.md` |
| DISP-02 ráfaga de 2.000 | 2000/2000 entregadas, 0 perdidas, ≈126 s | `RESULTADOS-DISP02.md` |
| MOD-02 | 0 líneas modificadas en Colombia/Stripe al agregar Brasil/MercadoPago | `RESULTADOS-MOD02.md` |

Pendientes declarados: consumidores Pulsar de Reputación y Proveedores no están desplegados en Cloud Run (loop de consumo sin HTTP);
el namespace `hda/trabajos` de DISP-03 no coincide con `hda/gestion-trabajos` de Gestión; Reputación sin logs estructurados; ESC-01 con umbral de 2 s sin cumplir en la corrida real.

---

## 8. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| DISP-03: aserción "Estado terminal COMPLETADA" falla | el worker aún reintenta o arrancó en frío; usa `--delay-request 10000` y calienta antes |
| `403 Forbidden` al llamar un servicio | se recreó el servicio y se perdió el permiso público: `terraform apply` en ese stack lo restaura |
| Un servicio sirve una imagen vieja | Cloud Run fija el digest por revisión: compara `status.imageDigest` con el `:latest` del Artifact Registry; `terraform apply -replace=<servicio>` |
| Despliegue de gestión-trabajos queda "failed to become healthy" | cuota de CPU de la región (20 vCPU): baja `min_instance_count`/`max_instance_count` |
| Grafana te saca al login / sin datos | tarda ~30 s tras un cambio de dashboard; el panel de logs necesita el plugin de Cloud Logging y `logging.viewer` en su cuenta de servicio |
| Los logs no aparecen | ajusta el rango de tiempo del Logs Explorer; puede tardar unos segundos en ingerirse |
| No aparecen logs de Pulsar | la VM de Pulsar no envía logs: usa SSH (IAP) y `pulsar-admin topics stats persistent://hda/gestion-trabajos/trabajos.finalizado` |

---

## 9. Costos y apagado

Con la demo dejan facturando en el proyecto: `gestion-trabajos-poc-api` (min 1 instancia, 2 vCPU), `disp03-poc-api`, `disp03-poc-worker`,
`mocks-crm-poc-mock-crm` y Grafana (1 instancia cada uno), 4 instancias de Cloud SQL y la VM de Pulsar (e2-standard-4).
Al terminar el video, apaga en orden inverso según `DESPLIEGUE-GCP-INTEGRAL.md`.
Para una corrida real de ESC-01 usa `-var log_detalle=minimo` en gestión y pagos (menos logs por request) y sube `min_instance_count` (requiere más cuota de CPU).

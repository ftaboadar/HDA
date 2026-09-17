# Resultados del experimento de escalabilidad — Infra GCP integral + k6

Documenta la corrida real (2026-09-14) del escenario de Escalabilidad ESC-01
(`experimento-arquitectura/contexto/escenarios_calidad.md`) contra infraestructura de GCP real
desplegada para la ocasión (`hda-projectt`, 106 recursos, 7 stacks Terraform — ver
`DESPLIEGUE-GCP-INTEGRAL.md`), más las decisiones de arquitectura, puntos de sensibilidad y
tradeoffs que salieron de esa corrida. Mismo estándar de honestidad que
`DISP-03/RESULTADOS-DISP03.md`: solo se reporta lo que de verdad se ejecutó y midió.

**Alcance de este documento**: complementa (no reemplaza) las 5 columnas ATAM que
`escenarios_calidad.md` todavía tiene pendientes para ESC-01 — decisión arquitectural,
puntos de sensibilidad, tradeoffs, riesgos, rationale — con evidencia real de una corrida
contra GCP, no solo diseño en el papel. El veredicto formal cumple/no-cumple del escenario
sigue siendo trabajo exclusivo de `validador-hipotesis`; aquí se documentan
mediciones crudas y las decisiones que las explican.

## 1. Resultados

### 1.1 GCP real (`hda-projectt`)

| Escenario | Componente | p95 medido | Umbral | Throughput | % fallo | Veredicto crudo |
|---|---|---|---|---|---|---|
| ESC-01 (pico 4x, 1ª corrida) | Gestión de Trabajos | 14,208ms | <2,000ms | 216 req/s, 159,779 requests | 20.0% | Fuera del umbral — causa identificada (sección 3) |
| ESC-01 (pico 4x, 2ª corrida, post-fix) | Gestión de Trabajos | 9,717ms | <2,000ms | 326 req/s, 244,801 requests | 11.9% | Mejora real (-32% p95, -40% tasa de fallo) pero sigue fuera del umbral |

### 1.1.1 GCP real, sesión de dimensionamiento de capacidad (2026-09-17)

Corridas contra `k6-runner-poc-vm` (VM de Compute Engine en `southamerica-east1`, no desde una red
doméstica — ver `k6/README.md` sección "Por qué correr k6 desde una VM y no en local", causa real:
`ramping-arrival-rate` con `maxVUs=2000` satura el NAT del router doméstico bajo las latencias que
salían en las corridas 1-2 de arriba). Todas contra `gestion-trabajos-poc-api` real, mismo umbral
ESC-01.

| # | Cambio | p95 | % fallo | Throughput | "no available instance" (logs Cloud Run) |
|---|---|---|---|---|---|
| 3 | `containerConcurrency`/`max_workers`/pool de conexiones sincronizados en 15 (eliminaba sobresuscripción: antes 200/100/100, nunca coincidían) | 9,991ms | 14.2% | 543 req/s | Cientos, sostenidos durante el pico |
| **4** | **+ `min_instance_count=10`** (elimina cold-start del autoscaler) | **5,646ms** | **0%** | 544 req/s | **0** |
| 5 | + Cloud SQL `db-custom-4-15360` (4 vCPU, doble de cómputo — corrida justo tras el reinicio del tier) | 7,352ms | 4.6% | 659 req/s | Ráfaga puntual (~3s) |
| 6 | Igual a 5, pero con la instancia de Cloud SQL verificada estable 20+ min antes de correr | 7,521ms | 3.7% | 668 req/s | 17,874 |
| 7 | Igual a 6, con redeploy forzado de Cloud Run (instancias 100% nuevas, pools de conexión frescos) | 8,613ms | 5.9% | 656 req/s | 26,801 |
| 8 | **Replicación de la corrida 4** — mismo tier (`db-custom-2-7680`), misma config, instancia verificada estable 10+ min antes de correr | 7,455ms | 0.6% | 550 req/s | 2,562 |

**Hallazgo importante de la corrida 8 (replicación) — hay que matizar la conclusión de abajo**: con
la MISMA configuración exacta de la corrida 4 (mismo tier, mismo `concurrency`/pool/`min_instances`,
instancia igual de estable), el resultado NO se replicó limpiamente — p95 subió de 5,646ms a
7,455ms y aparecieron 2,562 `"no available instance"` donde antes hubo 0. La diferencia entre la
corrida 4 y la 8 (mismo tier) es casi tan grande como la diferencia entre el tier chico y el grande
(corridas 4 vs. 5-7) — **hay variación real entre corridas que el experimento no está controlando**,
y una sola corrida "buena" (la 4) no alcanza para afirmar con confianza que un tier es mejor que
otro. Candidatos sin confirmar para esa variación: contención en la VM `k6-runner-poc-vm` misma
(comparte recursos con otros procesos del proyecto), variabilidad de "vecino ruidoso" en la
infraestructura compartida de GCP, o algo no determinístico en cómo Cloud Run decide escalar sus
propias instancias. Confirmar esto con rigor requeriría varias corridas por configuración
(estadística, no una corrida puntual) — no se hizo por costo (8 corridas reales de ~12min ya
consumidas en esta sesión).

**Config final aplicada (la de mejor resultado *promedio* observado, no garantizado)**:
`db-custom-2-7680` (2 vCPU) +
`containerConcurrency=15` == `max_workers`(ThreadPoolExecutor) == `db_pool_size(10)+db_max_overflow(5)`
+ `min_instance_count=10` + `max_instance_count=20`. Ver el comentario junto a `sql_tier` en
`gestion-de-trabajos/infra/variables.tf` para el cálculo completo de capacidad
((pool × instancias) vs. `max_connections` del tier) y el detalle de cada corrida.

**Diagnóstico confirmado, en cadena — cada fix resolvió su problema y destapó el siguiente**:
1. **Sobresuscripción de conexiones** (corridas 1-3): `containerConcurrency` (200) no coincidía con
   `max_workers`/pool de conexiones (100) ni con `max_connections` real de Postgres — con
   `max_instance_count=10-20`, la demanda máxima superaba 5-10x la capacidad real de Postgres.
   Corregido sincronizando los 3 números.
2. **Cold-start del autoscaler** (corrida 3, resuelto en la 4): con concurrency bajado a 15, cada
   instancia aguanta mucho menos tráfico — el autoscaler necesitaba arrancar instancias nuevas más
   rápido de lo que un cold start (boot de Python/FastAPI + pool de conexiones) permite. Logs de
   Cloud Run: `"The request was aborted because there was no available instance"`. Resuelto con
   `min_instance_count=10` (instancias siempre calientes) — **corrida 4: 100% aceptación, 0% fallo**.
3. **CPU de Cloud SQL saturada al 99.5%** (corrida 4, confirmado con Cloud Monitoring): con los 2
   problemas anteriores resueltos, Cloud SQL (2 vCPU) quedó como el cuello de botella real, con solo
   ~150 conexiones activas (muy por debajo de `max_connections`≈400) — no era cantidad de
   conexiones, era cómputo.

**Anomalía original, ahora reinterpretada tras la corrida 8**: subir el tier a `db-custom-4-15360`
(4 vCPU) para aliviar el punto 3 parecía empeorar el resultado de forma reproducible en 3 corridas
(5, 6, 7) frente a la corrida 4. CPU de Cloud SQL bajó a ~65-68% (con margen), pero
"no available instance" en los logs de Cloud Run subió de 0 (corrida 4) a miles (corridas 6-7), y
Cloud Run se mantuvo aplanado en 10 instancias activas en todas las corridas (3-8) pese a
`max_instance_count=20` y sin ninguna cuota de por medio (`instance_limit_with_direct_vpc_egress_regional`
verificado en 100, muy por encima). Se descartaron 2 hipótesis con corridas reales: ruido
operacional del reinicio de Cloud SQL, y pools de conexión "stale". **Pero la corrida 8 (replicación
con el tier chico, misma config exacta que la 4) tampoco reprodujo el 0% de fallo de la corrida 4**
(dio 0.6% de fallo y 2,562 "no available instance") — así que ya no está claro que el tier grande
sea la variable que explica la diferencia; puede ser variación entre corridas del propio
experimento (candidatos: contención en la VM generadora de carga, "vecino ruidoso" en GCP, o
autoscaling no determinístico de Cloud Run). **Sin confirmar** cuál de las dos explicaciones es la
correcta — requeriría varias corridas por configuración (estadística) para separar señal de ruido,
no se hizo por costo (8 corridas reales de ~12min ya consumidas en esta sesión). Se dejó la config
del tier chico aplicada (mejor promedio observado: corridas 4 y 8 vs. 5, 6 y 7) en vez de seguir
gastando corridas reales para decidir entre las dos hipótesis.

Detalle crudo en `k6/results/esc-01-summary-gcp-tuned-vm-run.json` (corrida 2, sin el fix de
sobresuscripción), `esc-01-summary-min-instances-fix.json` (corrida 4), `esc-01-summary-tier4-fix.json`
(corrida 6) y `esc-01-summary-replicacion-tier2.json` (corrida 8, la replicación).

### 1.2 Local (`docker-compose`, duración reducida ~2.2min/escenario para esta iteración — ver nota de comparabilidad en sección 2.7)

| Escenario | Componente | p95 medido | Umbral | Throughput | % fallo | Veredicto crudo |
|---|---|---|---|---|---|---|
| ESC-01 (pico 4x, corta, sin Pulsar local arriba) | Gestión de Trabajos | 60,000ms (timeout) | <2,000ms | 71.7 req/s, 10,391 requests | 98.7% | Artefacto de entorno, no un resultado real — ver sección 2.7 |
| ESC-01 (pico 4x, corta, con Pulsar local arreglado) | Gestión de Trabajos | 3,346ms | <2,000ms | 575.5 req/s, 74,818 requests | **0%** | Fuera del umbral de latencia, pero 100% de aceptación (`esc01_aceptacion_ok`: 1.0) y 0% de fallo HTTP |
| ESC-01 (pico 4x, **duración completa** ~10.9min, post pool de conexiones configurable — `db_pool_size`/`db_max_overflow`/`db_pool_timeout`, mismo default 50/50/30s) | Gestión de Trabajos | 7,869ms | <2,000ms | 333 req/s, 217,322 requests | 2.08% (`esc01_aceptacion_ok` 97.9%) | Mejora sobre la corrida corta anterior en fallo HTTP, pero **sigue fuera del umbral de latencia** — no se forzó el resultado |

**Nota de comparabilidad**: la fila anterior usa la duración real del escenario (~10.9min, no la
versión "corta" ~2.2min de las 2 filas de arriba), así que no es directamente comparable con ellas
en throughput acumulado — sí lo es en p95, que es la métrica del umbral. Sigue sin confirmarse el
candidato de causa raíz (tier de Cloud SQL / `containerConcurrency` insuficiente para el pico real,
ver sección 3) porque el pool de conexiones ya no es el cuello de botella evidente al ser
configurable y quedarse en el mismo valor (50/50) que la corrida GCP post-fix que dio 9,717ms —
hacerlo configurable resuelve la operabilidad (retunear sin redeploy) pero no cierra por sí solo la
brecha de latencia. Detalle crudo (post-fix) en `k6/results/esc-01-summary.json`; baseline
pre-fix conservado en `k6/results/esc-01-summary-pre-pool-fix.json`.

Detalle crudo en `k6/results/esc-01-summary.json` (JSON completo de k6) y en
`k6/README.md` (tabla resumen con fecha/entorno, todavía no actualizada con esta corrida — pendiente).

## 2. Decisiones de arquitectura tomadas en esta iteración

### 2.1 Pulsar en una sola VM de Compute Engine, no en GKE+Helm

**Decisión**: correr el `docker-compose.yml` de `pulsar-infra/` (ya construido y, hasta esta
sesión, nunca ejecutado de verdad) tal cual en una VM, en vez de aprovisionar un cluster GKE y
desplegar el Helm chart oficial que también existe en `pulsar-infra/helm/`.

**Por qué**: un cluster GKE completo (nodos 24/7 + LoadBalancer real) es sustancialmente más
caro y lento de levantar que una sola VM, para un PoC de una noche. No descarta el camino de
Helm/GKE — sigue disponible si el equipo decide escalar esto más adelante.

### 2.2 Contrato de mensajería unificado a JSON plano (no Avro)

**Decisión**: el productor de `gestion-de-trabajos` pasó de `pulsar.schema.AvroSchema` a JSON
plano (`producer.send(json.dumps(mensaje).encode())`), igual que ya usa
`DISP-03/app/common/publicador.py`.

**Por qué**: el consumidor real de ese mismo tópico (`reputacion/.../consumidor_pulsar.py`)
esperaba JSON desde el principio — dos servicios de equipos distintos, diseñados por separado,
nunca se habían probado juntos contra un broker real hasta esta corrida. Avro además exige la
dependencia `pulsar-client[avro]`, que no estaba declarada en ningún `requirements.txt`.

### 2.3 Observabilidad: Google Managed Prometheus + Grafana en Cloud Run, no Prometheus autoalojado

**Decisión**: habilitar la API de Google Managed Service for Prometheus (que ya recolecta
métricas nativas de Cloud Run sin agente) y desplegar solo Grafana (imagen oficial) como capa
de visualización, en vez de un Prometheus propio con `/metrics` instrumentado en cada servicio.

**Por qué**: ningún servicio expone hoy un endpoint Prometheus — instrumentarlos habría
duplicado el alcance de esta iteración. GMP da métricas de infraestructura (latencia,
throughput, CPU) gratis; métricas de negocio (ej. conteo de eventos de dominio) quedan como
mejora futura si se instrumenta explícitamente.

### 2.4 Módulo Terraform reusable para los 3 microservicios nuevos

**Decisión**: extraer el patrón repetido de `DISP-03/infra/` (Cloud Run v2 + IAM + Cloud SQL
opcional + Direct VPC egress opcional) a `infra-modules/cloud-run-service/`, en vez de copiar y
pegar el mismo bloque 3 veces.

### 2.5 `asyncio.to_thread` aplicado sistemáticamente en `gestion-de-trabajos`, no solo donde ESC-01 lo exigía

**Decisión**: envolver TODAS las llamadas síncronas a repositorios (5 archivos: comandos,
queries, dispatcher, rutas HTTP), no solo `crear_trabajo.py` (que es lo único que ESC-01 mide
directamente).

**Por qué**: es el mismo bug estructural repetido — dejar solo uno corregido habría dejado una
inconsistencia sabiendo que el mismo patrón fallaría bajo carga en cualquier otro endpoint.

### 2.6 Consumidor de Pulsar de Reputación: NO desplegado en esta iteración

**Decisión explícita de no hacer algo**: `reputacion/app/infrastructure/messaging/consumidor_pulsar.py`
sigue sin un recurso Cloud Run — solo la API de Reputación está desplegada.

**Por qué**: es un loop *pull* bloqueante sin servidor HTTP; Cloud Run v2 (services) exige que
el contenedor escuche en su puerto y pase un *startup probe* — desplegarlo tal cual fallaría
siempre. Las dos rutas de solución (agregar un health-check HTTP trivial al consumidor, o
correrlo en una VM igual que Pulsar) tocan código de aplicación o exceden el alcance de "solo
infraestructura" de este PR — quedan documentadas, no implementadas.

### 2.7 Comparación local vs. GCP — por qué los números salieron así (justificación)

Se corrió una versión local de ESC-01 contra `docker-compose` para tener un punto de
comparación sin costo. **Nota de comparabilidad**: se corrió con duración reducida (~2.2min en vez
de 12min) para esta iteración puntual — las tasas objetivo (RPS pico) son las mismas, solo se
sostiene el pico menos tiempo. Ningún número local reemplaza al de GCP; se usa para AISLAR
variables, no para sustituir la medición formal.

**Primer intento de ESC-01 local — un hallazgo, no un resultado real**: la primera corrida dio
98.7% de fallo con p95 en el techo de 60s. Investigado con `docker logs`/`docker stats`: el
contenedor NUNCA estuvo saturado (0.05% CPU) — el problema era que no había ningún cluster de
Pulsar corriendo en local, así que cada intento de publicar bloqueaba ~15-30s reintentando una
conexión imposible antes de que el propio código (por diseño, ver
`publicador_pulsar.py`) la descartara y devolviera 201 igual. Esto NO es un hallazgo de
capacidad — es un artefacto de no tener Pulsar arriba. Se descartó y se corrigió antes de sacar
ninguna conclusión de él.

**Segundo hallazgo, real y nuevo**: al levantar Pulsar local y apuntar el contenedor de
Gestión de Trabajos a él vía `host.docker.internal`, la publicación seguía fallando —
`docker logs` mostró `Lookup response ... lookup-broker-url pulsar://127.0.0.1:6650`. Es la
MISMA clase de bug que ya se había corregido para la VM de GCP
(`pulsar-infra/gcp/templates/docker-compose.override.yml`,
`advertisedListeners=external:pulsar://127.0.0.1:6650`), pero manifestándose ahora para
cualquier cliente Pulsar que corra en OTRO contenedor Docker, no solo para un cliente externo a
la VM. `pulsar-infra/docker-compose.yml`, tal como está, solo funciona correctamente para
clientes que corren directo en el host (como hace `k6` en esta prueba) — un servicio
dockerizado que quiera hablarle a Pulsar local (ej. `gestion-de-trabajos` o `reputacion`
corriendo con `docker compose`, no en el host) se rompe igual. Se aplicó un override temporal
solo para esta prueba (`advertisedListeners=external:pulsar://host.docker.internal:6650`, en
`/tmp`, nunca comiteado) — la corrección real y permanente queda en "Qué falta".

**El resultado limpio, con Pulsar funcionando**: local con 1 sola instancia dio **100% de
aceptación y 0% de fallo HTTP** (`esc01_aceptacion_ok: 1.0`), con p95 de 3.35s — sigue sin
cumplir el umbral de 2s, pero por LATENCIA, no por caídas. Comparado con GCP (hasta 10
instancias autoescaladas): 88.1% de aceptación, p95 9.7s, **peor** en ambas dimensiones a pesar
de tener más capacidad nominal.

**Conclusión justificada (no solo intuición) de la comparación**: si más instancias en GCP
dieran peores números que 1 sola instancia local, la causa más probable NO es falta de
auto-scaling horizontal — es un costo por-instancia específico de GCP que no existe en local:
candidatos concretos, en orden de probabilidad, para investigar en la próxima entrega:
1. **El proxy de Cloud SQL** (Cloud Run se conecta a Cloud SQL vía un socket Unix administrado
   por un sidecar/proxy, no una conexión TCP directa como el Postgres local) — agrega un salto
   de red y serialización que no existe en `docker-compose`.
2. **`cpu_idle = true`** (default del módulo `infra-modules/cloud-run-service`, heredado de
   DISP-03): Cloud Run limita la CPU de la instancia fuera de la ventana de una request — bajo
   ráfagas de escrituras concurrentes a la BD (cada una en su propio hilo vía
   `asyncio.to_thread`), esto puede introducir latencia de scheduling que un contenedor Docker
   local, sin ese límite, no sufre.
3. **Cold starts durante el auto-scaling**: si Cloud Run escaló de 0-1 a varias instancias
   *durante* la ráfaga (en vez de tenerlas ya calientes), cada instancia nueva paga el costo de
   arranque (conexión a Cloud SQL, `Base.metadata.create_all()`) exactamente en el peor momento.

Ninguno de los 3 se instrumentó ni se confirmó en esta sesión — son hipótesis fundamentadas en
evidencia real (la comparación local-vs-GCP), no verificadas una por una. Ver "Qué falta".

## 3. Puntos de sensibilidad

*(en el sentido ATAM: una propiedad de un componente cuyo cambio afecta significativamente un
atributo de calidad — no un punto de falla, sino un parámetro sobre el que vale la pena tener
control fino).*

1. **El modelo de concurrencia de `gestion-de-trabajos` es un punto de sensibilidad directo de
   ESC-01**: pasar de llamadas síncronas bloqueantes a `asyncio.to_thread` bajó el p95 en 32% y
   la tasa de fallo en 40% sin cambiar NADA de infraestructura (mismo `max_instance_count=10`,
   mismo tier de Cloud SQL) — un solo patrón de código explica una fracción enorme de la
   capacidad observada. **[Cerrado, 2026-09-17]** El segundo punto de sensibilidad sospechado acá
   (pool de conexiones / tier de Cloud SQL) se aisló y se resolvió: ver sección 1.1.1 — era en
   realidad 2 problemas apilados (sobresuscripción de conexiones por `containerConcurrency`
   desincronizado del pool, y cold-start del autoscaler bajo baja concurrencia), ambos corregidos.
   Sigue habiendo una anomalía sin resolver (punto 6, abajo) sobre por qué más cómputo en Postgres
   empeora el resultado.
2. **`vpc_egress` (`PRIVATE_RANGES_ONLY` vs `ALL_TRAFFIC`) en el módulo Cloud Run es sensible
   para la disponibilidad de la integración con Pulsar**: sin Direct VPC egress habilitado
   explícitamente, cualquier servicio que necesite hablarle a la VM de Pulsar por IP interna
   simplemente no puede — y el error no aparece hasta el primer intento real de publicar bajo
   tráfico real, no en el despliegue.
3. **El número de réplicas de Zookeeper/Bookie/Broker (1 cada uno) es un punto de sensibilidad
   de disponibilidad, no de este experimento de escalabilidad pero sí del sistema completo**: la
   caída de cualquiera de los 3 contenedores tumba todo el camino de mensajería para los 3
   microservicios que dependen de Pulsar (`gestion-de-trabajos`, `reputacion`, y potencialmente
   `DISP-03` si migra de transporte). Aceptado a propósito para un PoC (ver el propio
   `docker-compose.yml`: "1 réplica ya cuenta como cluster real, no monolítico").
4. **La existencia del tenant/namespace de Pulsar es un punto de sensibilidad silencioso**: no
   está codificado en ningún Terraform — un `destroy`+`apply` limpio de `pulsar-infra/gcp`
   revive el broker pero NO el tenant `hda`, y todo el camino de integración fallaría de nuevo
   con `TopicNotFound` sin ningún cambio de código, solo por el orden de operaciones al
   reconstruir el ambiente.
5. **El formato de serialización del mensaje (`trabajos.finalizado`) es un punto de sensibilidad
   de integración entre bounded contexts construidos por personas distintas**: un cambio
   unilateral de formato en el productor (como el que ya rompió esto una vez, con Avro) rompe al
   consumidor sin que ninguno de los dos servicios, probados por separado, lo detecte.
6. **[Nuevo, 2026-09-17, sin resolver]** ESC-01 contra GCP real tiene **variación significativa
   entre corridas con la misma configuración exacta** — la corrida 4 dio 0% de fallo/5,646ms y su
   replicación (corrida 8, mismo tier, misma config, instancia igual de estable) dio 0.6%
   fallo/7,455ms. Esa variación es casi tan grande como la diferencia que se le atribuyó al tier de
   Cloud SQL (corridas 5-7, tier grande, 3.7-5.9% fallo) — así que no está confirmado si subir el
   tier realmente empeora el resultado, o si ambos grupos de corridas caen dentro del ruido normal
   del experimento. Candidatos sin confirmar: contención en la VM generadora de carga
   (`k6-runner-poc-vm`), variabilidad de "vecino ruidoso" en infraestructura compartida de GCP, o
   autoscaling no determinístico de Cloud Run (aplanado en 10 instancias activas en TODAS las
   corridas 3-8, pese a `max_instance_count=20`). Confirmar esto con rigor requiere varias corridas
   por configuración (estadística), no una corrida puntual — no se hizo por costo.

## 4. Tradeoffs

*(decisiones que mejoran un atributo de calidad a costa de otro — no "bugs corregidos", sino
elecciones de diseño con un costo aceptado conscientemente).*

| Decisión | Gana | Pierde |
|---|---|---|
| Pulsar en 1 VM (Compute Engine) en vez de GKE+Helm | Costo (~1/3), velocidad de despliegue, reutiliza el compose ya validado | Disponibilidad/auto-recuperación de Kubernetes, camino de escalado horizontal del broker |
| JSON plano en vez de Avro para eventos de integración | Compatibilidad inmediata entre servicios de equipos distintos, sin dependencia extra (`fastavro`) | Evolución de schema y eficiencia de wire-format que Avro sí ofrece — validado únicamente por convención de campo, no por un schema registry |
| Google Managed Prometheus sin colector propio (solo métricas nativas de Cloud Run) | Cero infraestructura/costo adicional | Sin métricas de negocio (eventos de dominio, tasas de éxito por caso de uso) visibles en el dashboard — solo infraestructura |
| `asyncio.to_thread` aplicado a los 5 archivos de `gestion-de-trabajos` de una vez | Consistencia total del servicio, evita dejar la misma bomba de tiempo en otro endpoint | Más superficie de cambio y de re-verificación en una sola sesión ya larga |
| No desplegar el consumidor de Reputación ahora | No se inventa un workaround de infraestructura (health-check falso, VM extra) sin decisión de equipo | Sin ese consumidor arriba, nadie confirmó todavía que Reputación reciba y procese el evento real — solo que llega al tópico |
| Tenant/namespace de Pulsar creado a mano, no en Terraform | Desbloqueó la demo de esta noche sin escribir un `null_resource`/`local-exec` bajo presión de tiempo | La infraestructura deja de ser 100% reproducible por `terraform apply` solo — un `destroy`+`apply` requiere repetir el paso manual, documentado pero no automatizado |

## 5. Qué falta para la próxima entrega (concreto, para iterar)

La comparación local vs. GCP (sección 2.7) reorienta el diagnóstico: el cuello de botella de
ESC-01 en GCP genera una tasa de fallo real (11.9%) que localmente NO aparece (0% de fallo,
100% de aceptación) — apunta a un costo específico de la plataforma GCP, no a falta de
capacidad bruta ni a un bug de la aplicación en sí. Por orden de impacto esperado:

1. **[Hecho, 2026-09-17]** ~~Instrumentar y medir el proxy de Cloud SQL directamente~~ — se hizo
   vía Cloud Monitoring API (CPU, conexiones activas, `backends_in_wait`, deadlocks) correlacionado
   con 5 corridas reales. Confirmó el candidato: CPU de Cloud SQL al 99.5% con el tier chico
   (sección 1.1.1, corrida 4). Ver sección 3, punto 6 para la anomalía nueva que esto destapó.
2. **[Descartado, 2026-09-17]** El candidato de `cpu_idle`/`startup_cpu_boost` no se probó
   directamente, pero quedó subsumido por hallazgos más concretos y confirmados (sobresuscripción
   de conexiones y cold-start del autoscaler, sección 1.1.1) que explican la brecha sin necesidad
   de este candidato.
3. **[Hecho, 2026-09-17]** ~~Repetir ESC-01 completo con `min_instance_count` elevado~~ — hecho,
   es la corrida 4 de la sección 1.1.1: `min_instance_count=10` fue el cambio que más impacto tuvo
   de toda la sesión (100% aceptación, 0% fallo, 0 `"no available instance"`).
4. **[Nuevo, 2026-09-17]** Separar señal de ruido en los resultados de ESC-01 contra GCP real
   (sección 1.1.1, sección 3 punto 6): la corrida 4 (mejor resultado) no se replicó limpiamente
   en la corrida 8 con la misma config exacta — la variación entre corridas "iguales" es casi tan
   grande como la diferencia atribuida al tier de Cloud SQL. Requiere correr varias repeticiones
   por configuración (no una corrida puntual) para saber con confianza estadística si el tier
   realmente importa, y instrumentar latencia interna del código (no solo métricas de infra) para
   explicar de dónde sale esa variación. No se hizo por costo (8 corridas reales de ~12min cada
   una ya consumidas en esta sesión).
5. **Corregir `advertisedListeners` en `pulsar-infra/docker-compose.yml`** para que cualquier
   contenedor Docker (no solo el host) pueda conectarse — hoy requiere un override manual
   (sección 2.7) para poder correr pruebas locales realistas con Pulsar de verdad arriba. Mismo
   patrón que ya existe para GCP (`pulsar-infra/gcp/templates/docker-compose.override.yml`),
   trasladado a un archivo equivalente para desarrollo local.
6. **Automatizar la creación del tenant/namespace de Pulsar en Terraform** (hoy es un paso
   manual post-`apply`, sin el cual todo el camino de integración falla en silencio tras un
   `destroy`+`apply` limpio).
7. **Decidir, como equipo, si vale la pena desplegar el consumidor de Reputación** (con uno de
  los dos caminos ya documentados) para cerrar el ciclo de integración de punta a punta —
  confirmado que el mensaje llega al tópico, no que Reputación lo procese.

## Referencias

- `experimento-arquitectura/contexto/escenarios_calidad.md` — definición fuente de ESC-01.
- `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3 — exigencia de
  volúmenes reales/compresión temporal documentada.
- `k6/README.md` — metodología de medición, factor de compresión por escenario, tabla de
  resultados.
- `k6/results/esc-01-summary.json` — JSON completo de k6 de la corrida contra GCP real.
- `k6/results-local/esc-01-corto-local.json` — JSON completo de k6 de la corrida local (sección
  1.2/2.7), versión de duración reducida con Pulsar local ya funcionando (no la primera corrida
  sin Pulsar, descartada como artefacto).
- `DESPLIEGUE-GCP-INTEGRAL.md` — inventario completo de los 7 stacks, orden de apply/destroy, y
  el detalle técnico de cada uno de los 7 bugs reales encontrados.

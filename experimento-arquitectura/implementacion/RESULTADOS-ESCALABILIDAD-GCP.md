# Resultados del experimento de escalabilidad — Infra GCP integral + k6

Documenta la corrida real (2026-09-14) de los 3 escenarios de Escalabilidad
(`experimento-arquitectura/contexto/escenarios_calidad.md`, ESC-01/02/03) contra
infraestructura de GCP real desplegada para la ocasión (`hda-projectt`, 106 recursos,
7 stacks Terraform — ver `DESPLIEGUE-GCP-INTEGRAL.md`), más las decisiones de arquitectura,
puntos de sensibilidad y tradeoffs que salieron de esa corrida. Mismo estándar de honestidad
que `DISP-03/RESULTADOS-DISP03.md`: solo se reporta lo que de verdad se ejecutó y midió.

**Alcance de este documento**: complementa (no reemplaza) las 5 columnas ATAM que
`escenarios_calidad.md` todavía tiene pendientes para ESC-01/02/03 — decisión arquitectural,
puntos de sensibilidad, tradeoffs, riesgos, rationale — con evidencia real de una corrida
contra GCP, no solo diseño en el papel. El veredicto formal cumple/no-cumple de cada
escenario sigue siendo trabajo exclusivo de `validador-hipotesis`; aquí se documentan
mediciones crudas y las decisiones que las explican.

## 1. Resultados

### 1.1 GCP real (`hda-projectt`)

| Escenario | Componente | p95 medido | Umbral | Throughput | % fallo | Veredicto crudo |
|---|---|---|---|---|---|---|
| ESC-02 (5x un partner) | DISP-03 | 260.4ms (partner pico) / 261.7ms (otros) | <300ms | 44.8 req/s, 14,789 requests | 0% | Dentro del umbral en ambas series; 0% rate-limiting cruzado |
| ESC-01 (pico 4x, 1ª corrida) | Gestión de Trabajos | 14,208ms | <2,000ms | 216 req/s, 159,779 requests | 20.0% | Fuera del umbral — causa identificada (sección 3) |
| ESC-01 (pico 4x, 2ª corrida, post-fix) | Gestión de Trabajos | 9,717ms | <2,000ms | 326 req/s, 244,801 requests | 11.9% | Mejora real (-32% p95, -40% tasa de fallo) pero sigue fuera del umbral |
| ESC-03 (crecimiento 3x) | Gestión de Trabajos + DISP-03 | — | <300ms | — | — | No medido contra GCP: la única corrida post-fix se interrumpió antes de completar los 16 min |

### 1.2 Local (`docker-compose`, duración reducida ~2.2min/escenario para esta iteración — ver nota de comparabilidad en sección 2.7)

| Escenario | Componente | p95 medido | Umbral | Throughput | % fallo | Veredicto crudo |
|---|---|---|---|---|---|---|
| ESC-02 (5x un partner, duración completa 5m30s) | DISP-03 | 6.4ms | <300ms | 48.8 req/s, 9,139 requests | 0% | Dentro del umbral, sin margen de duda |
| ESC-01 (pico 4x, corta, sin Pulsar local arriba) | Gestión de Trabajos | 60,000ms (timeout) | <2,000ms | 71.7 req/s, 10,391 requests | 98.7% | Artefacto de entorno, no un resultado real — ver sección 2.7 |
| ESC-01 (pico 4x, corta, con Pulsar local arreglado) | Gestión de Trabajos | 3,346ms | <2,000ms | 575.5 req/s, 74,818 requests | **0%** | Fuera del umbral de latencia, pero 100% de aceptación (`esc01_aceptacion_ok`: 1.0) y 0% de fallo HTTP |
| ESC-03 (crecimiento 3x, corta, con Pulsar) | Gestión de Trabajos + DISP-03 | 16.7ms (trabajos) / 11.9ms (proveedores) | <300ms | 19.8 req/s, 2,674 requests | 0% | Dentro del umbral en ambas series |

Detalle crudo en `k6/results/esc-0{1,2}-summary.json` (JSON completo de k6) y en
`k6/README.md` (tabla resumen con fecha/entorno).

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

Se corrió una versión local de los 3 escenarios contra `docker-compose` para tener un punto de
comparación sin costo. **Nota de comparabilidad**: ESC-01 y ESC-03 se corrieron con duración
reducida (~2.2min por escenario en vez de 12-16min) para esta iteración puntual — las tasas
objetivo (RPS pico) son las mismas, solo se sostiene el pico menos tiempo. ESC-02 sí se corrió a
duración completa. Ningún número local reemplaza al de GCP; se usan para AISLAR variables, no
para sustituir la medición formal.

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
   capacidad observada. La fracción restante (todavía fuera del umbral) sugiere que hay un
   *segundo* punto de sensibilidad sin aislar todavía (candidato más probable: el pool de
   conexiones de SQLAlchemy hacia Cloud SQL, o el tier `db-custom-1-3840` en sí).
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

1. **Instrumentar y medir el proxy de Cloud SQL directamente** durante una corrida real de
   ESC-01: `gcloud sql operations list` / métricas nativas de Cloud SQL (conexiones activas,
   CPU, latencia de queries) en Cloud Monitoring, correlacionadas en el tiempo con la corrida de
   k6. Es el candidato #1 de la sección 2.7 y el más barato de confirmar o descartar (ya hay
   observabilidad desplegada — `observabilidad/`, Grafana + Cloud Monitoring).
2. **Probar `cpu_idle = false` y/o `startup_cpu_boost` ajustado** en el módulo
   `infra-modules/cloud-run-service` para `gestion-de-trabajos`, y re-correr ESC-01 completo
   contra GCP para ver si cambia el resultado — descarta o confirma el candidato #2.
3. **Repetir ESC-01 completo (12 min, no la versión corta) contra GCP** con `min_instance_count`
   elevado desde el inicio (evita cold starts a mitad de ráfaga, candidato #3) — comparar contra
   el resultado ya documentado con `min_instance_count=0`.
4. **Terminar una corrida de ESC-03 completa (16 min) contra GCP real** — la única corrida
   post-fix de concurrencia se interrumpió antes de terminar; localmente sí pasó limpio
   (sección 1.2), pero eso no reemplaza la medición formal contra GCP.
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

- `experimento-arquitectura/contexto/escenarios_calidad.md` — definición fuente de ESC-01/02/03.
- `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3 — exigencia de
  volúmenes reales/compresión temporal documentada.
- `k6/README.md` — metodología de medición, factor de compresión por escenario, tabla de
  resultados.
- `k6/results/esc-0{1,2}-summary.json` — JSON completo de k6 de las corridas contra GCP real.
- `k6/results-local/*.json` — JSON completo de k6 de las corridas locales (sección 1.2/2.7);
  `esc-01-corto-local.json` y `esc-03-corto-local.json` son las versiones de duración reducida
  con Pulsar local ya funcionando (no la primera corrida sin Pulsar, descartada como artefacto).
- `DESPLIEGUE-GCP-INTEGRAL.md` — inventario completo de los 7 stacks, orden de apply/destroy, y
  el detalle técnico de cada uno de los 7 bugs reales encontrados.

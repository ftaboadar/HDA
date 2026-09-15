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

| Escenario | Componente | p95 medido | Umbral | Throughput | % fallo | Veredicto crudo |
|---|---|---|---|---|---|---|
| ESC-02 (5x un partner) | DISP-03 | 260.4ms (partner pico) / 261.7ms (otros) | <300ms | 44.8 req/s, 14,789 requests | 0% | Dentro del umbral en ambas series; 0% rate-limiting cruzado |
| ESC-01 (pico 4x, 1ª corrida) | Gestión de Trabajos | 14,208ms | <2,000ms | 216 req/s, 159,779 requests | 20.0% | Fuera del umbral — causa identificada (sección 3) |
| ESC-01 (pico 4x, 2ª corrida, post-fix) | Gestión de Trabajos | 9,717ms | <2,000ms | 326 req/s, 244,801 requests | 11.9% | Mejora real (-32% p95, -40% tasa de fallo) pero sigue fuera del umbral |
| ESC-03 (crecimiento 3x) | Gestión de Trabajos + DISP-03 | — | <300ms | — | — | No medido: corrida interrumpida antes de completar los 16 min |

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

## 5. Qué falta (explícito, no oculto)

- Aislar la causa raíz residual de ESC-01 (pool de conexiones a Cloud SQL vs. dimensionamiento
  de Cloud Run vs. tier de la instancia) — el fix de concurrencia ya aplicado no bastó solo.
- Terminar una corrida limpia de ESC-03 contra el código corregido (la única que se intentó se
  interrumpió antes de los 16 minutos).
- Automatizar la creación del tenant/namespace de Pulsar en Terraform (hoy es un paso manual
  post-`apply`, sin el cual todo el camino de integración falla en silencio tras un
  `destroy`+`apply` limpio).
- Decidir, como equipo, si vale la pena desplegar el consumidor de Reputación (con uno de los
  dos caminos ya documentados) para cerrar el ciclo de integración de punta a punta.

## Referencias

- `experimento-arquitectura/contexto/escenarios_calidad.md` — definición fuente de ESC-01/02/03.
- `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3 — exigencia de
  volúmenes reales/compresión temporal documentada.
- `k6/README.md` — metodología de medición, factor de compresión por escenario, tabla de
  resultados.
- `DESPLIEGUE-GCP-INTEGRAL.md` — inventario completo de los 7 stacks, orden de apply/destroy, y
  el detalle técnico de cada uno de los 7 bugs reales encontrados.

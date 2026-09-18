# Guion de sustentación — Entrega 4 (Escalabilidad: GCP real + k6)

Documento de apoyo para la defensa oral. No repite el detalle técnico de los documentos fuente —
los referencia en cada sección para que, si un evaluador pide profundizar, sepas exactamente a
qué archivo/línea ir. Está pensado para leerse en el orden en que se presenta: **qué se construyó
→ cómo se corrió/midió → qué se encontró → qué queda pendiente**.

**Documentos fuente (no duplicados aquí):**
- `RESULTADOS-ESCALABILIDAD-GCP.md` — resultados crudos, decisiones de arquitectura, puntos de
  sensibilidad ATAM, tradeoffs, "qué falta".
- `DESPLIEGUE-GCP-INTEGRAL.md` — inventario de los 7 stacks Terraform, orden de apply/destroy, y
  el detalle técnico de los 7 bugs reales encontrados desplegando.
- `k6/README.md` — metodología de medición, factor de compresión temporal por escenario.
- `experimento-arquitectura/contexto/escenarios_calidad.md` — definición fuente de ESC-01/02/03
  (la tabla de la que salen los umbrales que se están defendiendo).

---

## 0. Una frase para abrir

> "Tomamos los 3 escenarios de Escalabilidad que ya estaban diseñados en el papel, construimos la
> infraestructura real en GCP para los 4 microservicios + el bus de mensajería, y los medimos con
> carga real — no simulada — usando k6. Encontramos 7 bugs que ni el diseño ni `terraform
> validate` podían predecir, corregimos los que pudimos, y dejamos documentado con evidencia
> exactamente qué falta y por qué."

Esto es lo que distingue esta entrega de un ejercicio de diseño: **hay infraestructura viva,
hay números medidos, y hay una causa raíz identificada** para el escenario que no pasa el umbral
— no solo "no cumple".

---

## 1. Qué se implementó en GCP (mapa para mostrar en pantalla)

Abre la consola de GCP o corre esto en vivo para mostrar que es real, no una promesa de diseño:

```bash
gcloud run services list --project=hda-projectt --format="table(metadata.name,status.url,status.conditions[0].status)"
```

Da 10 servicios Cloud Run + 1 VM de Compute Engine, todos `True` (sanos). Explícalo así:

| Capa | Qué hay | Dónde está el código/infra |
|---|---|---|
| **4 microservicios de negocio** | `gestion-de-trabajos` (API), `reputacion` (API), DISP-03 (API + worker + 3 mocks de externos), `mocks-pagos` (Stripe + MercadoPago) | `implementacion/{gestion-de-trabajos,reputacion,DISP-03,mocks-pagos}/` |
| **Mensajería** | 1 VM de Compute Engine corriendo el `docker-compose.yml` de Pulsar (Zookeeper + BookKeeper + Broker) — el mismo compose que ya tenía el equipo, sin reescribirlo, solo llevado a una VM | `implementacion/pulsar-infra/` (compose original) + `pulsar-infra/gcp/` (VM + startup script, nuevo) |
| **Persistencia** | Cloud SQL (Postgres) — una instancia por microservicio con estado (gestión de trabajos, reputación, DISP-03) | `<servicio>/infra/*.tf` |
| **Observabilidad** | Google Managed Prometheus (métricas nativas de Cloud Run/Cloud SQL, sin agente) + Grafana real desplegado en Cloud Run | `implementacion/observabilidad/` |
| **Infra como código** | 7 stacks de Terraform independientes + 1 módulo reusable (`infra-modules/cloud-run-service/`) que evita repetir el patrón Cloud Run+SA+Cloud SQL 3 veces | Ver tabla completa de stacks en `DESPLIEGUE-GCP-INTEGRAL.md`, sección "Stacks nuevos y su relación" |

**Punto clave a verbalizar**: Pulsar es la pieza de mensajería que el equipo tenía diseñada pero
nunca había corrido contra un broker real — esta entrega es la primera vez que se prueba de
punta a punta (`gestion-de-trabajos` publica → Pulsar transporta → `reputación` debería
consumir). Eso es justamente lo que reveló los bugs de integración de la sección 3.

---

## 2. Cómo se estructura el código (dominios, para cuando pregunten "¿y esto es DDD de verdad o
   solo carpetas?")

Usa `gestion-de-trabajos` como ejemplo principal — es el servicio propio, el más completo, y el
que tiene la historia más rica (aggregate + eventos + dispatcher + ACL). Muestra el árbol:

```
gestion-de-trabajos/app/
├── domain/                         ← reglas de negocio puras, sin frameworks
│   ├── seedwork/                   ← base compartida: AggregateRoot, Entity, ValueObject, DomainEvent
│   ├── trabajo/                    ← agregado Trabajo (fábrica, value objects, eventos, puerto de repositorio)
│   └── pagos/                      ← agregado Pago (independiente de Trabajo, ver ACL abajo)
├── application/                    ← casos de uso (comandos/queries), orquestan el dominio
│   ├── commands/                   ← CrearTrabajo, PagarTrabajo, Compensar
│   ├── queries/                    ← ConsultarTrabajo, ConsultarPago (solo lectura, CQS)
│   ├── ports/                      ← interfaces que la aplicación necesita (repos, publicador, pasarela)
│   └── dispatcher_eventos_dominio.py   ← pieza clave, ver abajo
├── infrastructure/                 ← implementaciones concretas de los puertos
│   ├── persistence/                ← SQLAlchemy (Postgres/Cloud SQL)
│   ├── messaging/                  ← publicador Pulsar (JSON)
│   └── adapters/                   ← pasarelas de pago (Stripe/MercadoPago), reglas regionales (CO/BR)
└── api/main.py                     ← FastAPI, solo traduce HTTP ↔ casos de uso
```

**El punto que hay que defender con más cuidado — el dispatcher de eventos de dominio**
(`application/dispatcher_eventos_dominio.py`): el agregado `Trabajo` y el agregado `Pago` viven
en **módulos separados dentro del mismo servicio**, y `Pago` NUNCA depende directamente de
`Trabajo` — no importa su repositorio, no lo consulta. En vez de eso:

1. `Trabajo` registra un evento de dominio (`TrabajoFinalizado`) cuando cambia de estado.
2. El dispatcher recoge esos eventos y decide qué hacer con cada tipo — para
   `TrabajoFinalizado`, puebla un modelo de lectura local propio del módulo de Pagos
   (`RegistroTrabajoElegible`, vía el puerto `IRegistroTrabajosRepository`) y publica el evento de
   integración hacia Pulsar.
3. `Pago` solo lee de ese modelo de lectura local — nunca del agregado `Trabajo` ni de su tabla.

Esto es un **Anti-Corruption Layer interno**: aunque los dos módulos están en el mismo
`docker-compose`/mismo deploy hoy, están desacoplados como si fueran dos bounded contexts
distintos — el mismo patrón que ya usa DISP-03 para el mismo problema (ver su propio
`dispatcher_eventos_dominio.py`). Si mañana `Pago` se separa a su propio microservicio, el cambio
es mover el consumidor de eventos, no reescribir lógica de negocio.

**Los otros 3 servicios, en una frase cada uno** (para no perderte en detalle si preguntan):
- **DISP-03** (Verificación de Proveedores): el más maduro — cola + reintento con backoff +
  Dead Letter Queue + reproceso manual, validado en `RESULTADOS-DISP03.md` contra GCP real en
  una entrega anterior. Es la referencia de patrón de disponibilidad que se reusó aquí.
- **Reputación**: agregado `PerfilReputacion` + `event_store` propio (event sourcing parcial) +
  un consumidor Pulsar que hoy **no está desplegado** (ver limitación en sección 4).
- **Mocks de Pagos**: sin dominio propio — son dobles de prueba (Stripe/MercadoPago) para que
  `gestion-de-trabajos` tenga contra qué hablar sin depender de las pasarelas reales.

---

## 3. Cómo se midió — metodología k6 (para defender que los números no son inventados)

**El argumento de fondo**: los 3 escenarios (ESC-01/02/03) ya estaban definidos en
`escenarios_calidad.md` con umbrales numéricos concretos (p95, % aceptación, auto-scaling). k6 no
inventa esos umbrales — los traduce a un script que genera tráfico real contra las URLs de Cloud
Run y verifica el umbral como `threshold` nativo del framework.

| Escenario | Qué representa | Cómo se comprimió el tiempo (Regla 3: nunca por debajo del volumen real) |
|---|---|---|
| **ESC-01** | Pico de 4x en 48h (evento climático) contra `gestion-de-trabajos` | 48h → 12 min de prueba (factor ~240x); la **tasa** (req/s) no se reduce, solo se sostiene menos tiempo |
| **ESC-02** | 5x de tráfico de un solo partner contra DISP-03 | Sin ventana que comprimir (pico súbito); se usa `tipo_verificador` como proxy de partición por partner (justificado — no hay `partner_id` en la API hoy) |
| **ESC-03** | Crecimiento sostenido 3x en 3 años (`gestion-de-trabajos` + DISP-03 combinados) | 3 años → 16 min (factor ~98.550x); tasa amplificada pero siempre por ENCIMA del piso literal del enunciado |

Detalle completo de la derivación numérica (por qué 289→1157 req/s y no otro número) está en la
cabecera de cada script `.js` y en `k6/README.md` — si preguntan "¿de dónde sale ese número
exacto?", ese es el lugar.

**Dos entornos, a propósito, no por accidente**:
1. **GCP real** (`hda-projectt`) — la medición formal, la que responde si se cumple o no el
   escenario tal como está definido.
2. **Local** (`docker-compose`, duración reducida) — un punto de comparación de costo cero para
   **aislar variables**: si el mismo código se comporta distinto en GCP que en local, la
   diferencia apunta a la plataforma, no a la aplicación. Esto es lo que permitió narrow-down el
   hallazgo de la sección 4.

---

## 4. Qué se encontró (el corazón de la sustentación — lidera con esto, no lo escondas)

### 4.1 Lo que sí cumple

- **ESC-02 contra GCP real: cumple limpio.** p95 260ms (partner en pico) / 262ms (otros
  partners) — ambos bajo el umbral de 300ms, 0% de rate-limiting cruzado, sobre 14,789 requests
  reales. Este es el resultado más sólido de la entrega — muéstralo primero, da credibilidad al
  resto.
- **ESC-03 local: cumple limpio** (16.7ms trabajos / 11.9ms proveedores, ambos bajo 300ms) —
  aunque la corrida formal contra GCP no se completó (ver 4.3).

### 4.2 Lo que no cumple, y por qué eso también es un resultado válido

**ESC-01 contra GCP no pasa el umbral de latencia** (<2s), en dos corridas:

| Corrida | p95 | % fallo | Qué cambió entre una y otra |
|---|---|---|---|
| 1ª (antes del fix) | 14.2s | 20.0% | — |
| 2ª (después del fix) | 9.7s | 11.9% | Se envolvieron 5 archivos con `asyncio.to_thread` (ver 4.2.1) |

**4.2.1 — la causa que sí se encontró y se corrigió**: todas las llamadas a los repositorios
(SQLAlchemy, síncronas) se invocaban directo dentro de handlers `async def` de FastAPI —
bloqueaban el event loop del worker en cada escritura a Cloud SQL. Bajo carga, esto serializaba
efectivamente cada instancia sin importar cuántas réplicas hubiera. Se corrigió envolviendo cada
llamada en `asyncio.to_thread` — mejora real y medida: **-32% p95, -40% tasa de fallo**, con la
misma infraestructura exacta (mismo `max_instance_count`, mismo tier de Cloud SQL). Esto por sí
solo es un hallazgo defendible: un solo patrón de código explica una fracción enorme de la
capacidad observada.

**4.2.2 — la causa que queda abierta, con evidencia, no con una excusa**: el fix mejoró pero no
resolvió. La comparación local-vs-GCP (misma tasa objetivo, mismo código exacto) da:

| | Local (1 instancia) | GCP (hasta 10 instancias autoescaladas) |
|---|---|---|
| % aceptación | 100% | 88.1% |
| p95 | 3.35s | 9.7s |

**Esto es contraintuitivo y por eso es el punto más interesante para defender oralmente**: GCP,
con más capacidad nominal, da peores números que una sola instancia local. La conclusión lógica
(no solo intuición) es que la causa NO es falta de auto-scaling horizontal — es un costo
específico de la plataforma que no existe en `docker-compose`. Los 3 candidatos identificados, en
orden de probabilidad (detalle en `RESULTADOS-ESCALABILIDAD-GCP.md` §2.7):
1. El proxy de Cloud SQL (Cloud Run habla con Cloud SQL vía un socket administrado, no TCP
   directo como en local — un salto de red/serialización extra).
2. `cpu_idle=true` (default heredado del módulo Terraform): Cloud Run limita la CPU fuera de la
   ventana de una request, lo que puede introducir latencia de scheduling bajo ráfagas de
   escritura concurrente que un contenedor Docker local no sufre.
3. Cold starts de instancias nuevas escalando a mitad de la ráfaga (cada una paga conexión a
   Cloud SQL + inicialización de esquema justo en el peor momento).

Ninguno de los 3 se confirmó de forma aislada (falta tiempo, no falta hipótesis) — están
priorizados en la sección "Qué falta" para la próxima iteración, con el comando exacto para
confirmarlos.

**Cómo defender esto ante un evaluador que pregunte "¿entonces no pasó la prueba?"**: la
respuesta correcta es "no pasó el umbral, pero identificamos con evidencia real que la causa es
específica de la plataforma de despliegue, no un defecto de diseño ni de capacidad — y sabemos
exactamente qué instrumentar primero para confirmarlo". Esa es una conclusión de arquitecto, no
un resultado en rojo sin explicación.

### 4.3 Lo que no se llegó a medir (declarado, no escondido)

ESC-03 contra GCP real no completó una corrida limpia (la única corrida post-fix se interrumpió
antes de los 16 minutos por tiempo). Localmente sí pasó limpio, pero eso no sustituye la medición
formal contra GCP — queda como el primer punto de "qué falta".

### 4.4 Los 7 bugs reales encontrados desplegando (para mostrar que "funciona en el diseño" ≠
   "funciona en producción")

Vale la pena nombrar 2-3 en la sustentación como evidencia de trabajo real de infraestructura, no
solo `terraform apply` y ya:

1. **Cloud Run v2 rechazó el formato de subred** que `terraform validate` había aceptado sin
   problema — solo apareció al aplicar de verdad.
2. **Los volúmenes de Docker de Pulsar se creaban `root:root`**, y el proceso del broker corre
   con un usuario sin privilegios — reproducido idéntico en local, así que no era un problema de
   la nube, era un bug del `docker-compose.yml` que nunca se había corrido de verdad antes de
   esta entrega.
3. **El productor de eventos serializaba en Avro; el consumidor esperaba JSON plano** — dos
   servicios construidos por personas distintas, nunca antes probados juntos contra un broker
   real. Este es el ejemplo más claro de por qué "probar contra infraestructura real" no es
   opcional: ningún test unitario de ninguno de los dos servicios por separado podía detectar
   esto.

Lista completa (7 bugs, con la corrección exacta de cada uno) en `DESPLIEGUE-GCP-INTEGRAL.md`,
sección "Estado real tras el despliegue en GCP".

---

## 5. Decisiones de arquitectura a defender si preguntan "¿por qué así y no de otra forma?"

Resumen de una línea cada una — el razonamiento completo está en
`RESULTADOS-ESCALABILIDAD-GCP.md` sección 2:

1. **Pulsar en 1 VM, no en GKE+Helm** — mismo compose ya validado por el equipo, sustancialmente
   más barato y rápido para un PoC de una sesión; no descarta el camino de Helm que ya existe si
   el equipo decide escalarlo después.
2. **JSON plano, no Avro, para eventos de integración** — el consumidor real ya esperaba JSON;
   Avro además exigía una dependencia no declarada en ningún `requirements.txt`.
3. **Google Managed Prometheus, no un Prometheus autoalojado** — da métricas de infraestructura
   gratis sin instrumentar código; instrumentar `/metrics` en 4 servicios habría duplicado el
   alcance de esta iteración.
4. **Módulo Terraform reusable** para los 3 microservicios nuevos, en vez de copiar/pegar 3 veces
   el mismo bloque Cloud Run+SA+Cloud SQL.
5. **`asyncio.to_thread` aplicado a los 5 archivos que tocan un repositorio**, no solo al que
   ESC-01 mide directamente — mismo bug estructural, se corrigió de una vez para no dejar la
   misma bomba de tiempo en otro endpoint.
6. **El consumidor de Pulsar de Reputación NO se desplegó** — es un loop *pull* bloqueante sin
   servidor HTTP; Cloud Run v2 exige que el contenedor escuche un puerto y pase un startup probe.
   Las dos soluciones (health-check trivial, o VM dedicada como Pulsar) quedan documentadas, no
   implementadas — tocar código de aplicación o levantar otra VM excedía el alcance de esta
   sesión de infraestructura.

---

## 6. Qué falta (dilo tú, antes de que te lo pregunten)

Orden de prioridad real, con el porqué de cada uno (lista completa con comandos en
`RESULTADOS-ESCALABILIDAD-GCP.md` sección 5):

1. Instrumentar métricas de Cloud SQL (conexiones activas, CPU) durante una corrida real de
   ESC-01 — es el candidato #1 de la sección 4.2.2 y el más barato de confirmar (la
   observabilidad ya está desplegada).
2. Probar `cpu_idle=false` y re-correr ESC-01 completo — descarta o confirma el candidato #2.
3. Repetir ESC-01 a duración completa (12 min, no la versión corta) con instancias ya calientes
   desde el inicio — descarta o confirma el candidato #3 (cold starts).
4. Completar una corrida de ESC-03 limpia contra GCP (16 min) — la que se interrumpió.
5. Corregir `advertisedListeners` en el compose local para que cualquier contenedor Docker (no
   solo el host) pueda hablarle a Pulsar sin un override manual.
6. Automatizar en Terraform la creación del tenant/namespace de Pulsar — hoy es un paso manual
   que se pierde en cada `destroy`+`apply` limpio.
7. Decidir en equipo si se despliega el consumidor de Reputación (dos rutas ya documentadas) para
   cerrar el ciclo de integración de punta a punta.

---

## 7. Preguntas que probablemente hagan, y la respuesta corta

- **"¿Por qué no usaron Kubernetes/GKE si ya tenían el Helm chart?"** → Costo y velocidad para un
  PoC de una sesión; la decisión está declarada explícitamente como tal, no oculta, y el camino
  GKE sigue disponible sin descartar el trabajo ya hecho (§5.1 de este guion).
- **"¿Los números de la comparación local vs. GCP son justos? ¿No es comparar peras con manzanas
  por el `min_instance_count`?"** → Es exactamente ese contraste el que apunta la causa a la
  plataforma: si local (recursos fijos, sin auto-scaling) da MEJORES números que GCP (con
  auto-scaling activo), el auto-scaling no es el problema — hay un costo por-instancia
  específico de GCP compitiendo con la ganancia de tener más instancias.
- **"¿Por qué Reputación no tiene su consumidor desplegado si ya está construido?"** → Restricción
  real de la plataforma (Cloud Run v2 exige HTTP + startup probe, el consumidor es un loop pull),
  no una omisión — con dos soluciones ya diseñadas y documentadas, pendientes de decisión de
  equipo.
- **"¿Cómo saben que el 88.1%/9.7s de GCP no es simplemente falta de capacidad (subir el
  `max_instance_count` o el tier de Cloud SQL)?"** → No lo saben todavía con certeza — por eso la
  sección "Qué falta" prioriza instrumentar Cloud SQL antes que subir tiers a ciegas; subir
  capacidad sin medir primero sería gastar más sin confirmar la causa.

---

## 8. Cierre sugerido

> "La entrega no es 'todo pasó' — es 'construimos la infraestructura real, medimos con carga
> real, un escenario pasa limpio, otro no pasa pero sabemos por qué con evidencia (no solo
> teoría), y dejamos un plan concreto y priorizado para la siguiente iteración, no una lista
> genérica de mejoras'."

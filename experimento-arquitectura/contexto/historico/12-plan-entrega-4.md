# Plan — Entrega 4 (Transacción larga, no monolítica)

> **⚠ Revisado en Entrega 5 (2026-09-21).** Documento **histórico** de la Entrega 4. Quedaron invalidadas su §0.1 y todo lo que dice que *Pagos es externo / un módulo ACL dentro de Gestión de Trabajos / sin tópico propio*: Gestión de Pagos es un microservicio propio que se integra por eventos Pulsar. La fuente de verdad vigente es [`15-arquitectura-entrega-5.md`](../15-arquitectura-entrega-5.md)

### Hogar de los Alpes · Alineado a la guía "AeroAlpes" del profesor

> **Nota de integración (2026-09-13):** este documento se copió desde un insumo externo
> (`~/Downloads/plan_entrega_parcial.md`) siguiendo la convención de `AGENTS.md` sobre insumos que
> llegan de fuera del repo. Complementa — no reemplaza — `REGLAS-DURAS-rubrica-entrega-3.md`: ese
> documento es la rúbrica de la **Entrega 3** (en curso de cierre, ver su tabla de resumen); este es
> la planificación de la **Entrega 4**, basada en una guía complementaria del profesor que todavía no
> existe como PDF en `contexto/utils/` — si el equipo consigue ese insumo en su forma original, debe
> agregarse ahí y citarse desde aquí, igual que se hizo con `Proyecto-202614-HogarDeLosAlpes.pdf`.
> Ver `13-guia-entrega-4-pasos.md` para el "en qué orden" y "quién hace qué" (ese documento es al
> "cómo" lo que este es al "qué/por qué").
>
> **Decisión de equipo confirmada al integrar este plan**: migrar **todo** el transporte de eventos a
> Apache Pulsar, incluyendo el publicador de Proveedores — aunque ese publicador ya está **validado
> contra GCP real con Pub/Sub** (despliegue del 2026-09-06 contra el proyecto `hda-projectt`, 3 bugs
> de producción corregidos, H1 de DISP-03 validada — ver `implementacion/proveedores/README.md` y los
> commits `ca76f60`..`ef391c5`). Esto implica dos consecuencias explícitas que este documento no
> tenía originalmente y que el equipo debe tener presentes (detalladas en la sección 2 y la sección 3):
> 1. La evidencia de disponibilidad de DISP-03 ya documentada en `escenarios_calidad.md` (fila
>    "Decisión arquitectural"/"Tradeoffs"/"Riesgos") describe explícitamente RabbitMQ/Pub-Sub — queda
>    **desactualizada** en cuanto el publicador migre a Pulsar, y debe volver a validarse (no basta con
>    reescribir el texto: los CP-1..CP-7 deben re-ejecutarse contra el nuevo transporte antes de dar
>    DISP-03 por vigente bajo Pulsar). Es trabajo de `experimento-runner` + `validador-hipotesis`,
>    seguido de `disenador-escenarios` para actualizar el campo en `escenarios_calidad.md`.
> 2. La validación en GCP real ya hecha con Pub/Sub no se pierde como evidencia histórica (Entrega 3
>    la sigue reclamando tal cual, con esa tecnología) — pero para la Entrega 4, el mismo experimento
>    deberá repetirse contra Pulsar antes de reclamar el mismo veredicto con el nuevo broker.
>
> **Corrección posterior (mismo día):** la versión original de este plan (insumo externo) trataba
> **Pagos** como un 4to microservicio propio, con su propia agregación, DB y hexagonal completo. Eso
> contradice el diseño de dominio **ya aprobado y sustentado con el tutor en Entrega 1**: `Pagos` es
> un **`GENERIC_SUBDOMAIN`** explícitamente "delegable a un proveedor de pagos para marketplace (ej.
> Stripe)" (`01-dominios-subdominios.cml`), no tiene `BoundedContext` propio en el Context Map TO-BE
> (`../03-contextos-acotados-TO-BE.cml`), y en la Vista de Módulos (`05-vista-modulo.puml`) está dibujado
> como componente `<<externo>>` — mismo trato que Notificaciones, Gestor Documental o Contabilidad. Los
> tres artefactos son independientes entre sí y coinciden: Pagos se compra, no se construye. Ver
> sección 0.1 para el detalle y la corrección aplicada en todo este documento.

---

## 0. La idea central — tomada literal de la guía del profesor

El profesor no pide 4 microservicios sueltos, cada uno con un escenario distinto sin relación entre sí. Pide identificar **una transacción larga de negocio real**, construir los 2-3 servicios que esa transacción necesita, y usar **esos mismos servicios** para probar los 3 escenarios de calidad (variando cómo se estresan, no qué se construye). El 4to servicio puede ser independiente de la cadena.

**Traducido a Hogar de los Alpes:**

| AeroAlpes | HdA |
|---|---|
| Transacción larga: **Reservar** | Transacción larga: **Crear y completar un Trabajo** |
| Reservas → GDS → Pagos (la cadena que se sagifica en Entrega 5) | **Gestión de Trabajos → Proveedores → (ACL síncrona a Pagos, externo)** |
| 4to servicio fuera de la cadena | **Reputación** |
| BFF (cuenta como 4to servicio, pero en Entrega 5) | BFF (Entrega 5, no esta) |

**Regla explícita de esta entrega, tomada literal de la guía:** los servicios deben poder **oírse** por los tópicos de eventos — pero **no deben reaccionar ni completar la transacción todavía**. Eso es trabajo de la Saga, que es Entrega 5. Esto simplifica el alcance real de lo que hay que construir ahora.

---

## 0.1 Alineación obligatoria con los dominios de Entrega 1 — por qué Pagos NO es un microservicio propio

**Esta es una corrección sobre el insumo original**, no una decisión nueva del equipo: el diseño de
dominio de Entrega 1 (`experimento-arquitectura/contexto/01-dominios-subdominios.cml`,
`../03-contextos-acotados-TO-BE.cml`, `05-vista-modulo.puml`), ya sustentado con el tutor, es explícito y
consistente en los tres artefactos:

| Artefacto | Qué dice de Pagos |
|---|---|
| `01-dominios-subdominios.cml` | `Subdomain Pagos { type = GENERIC_SUBDOMAIN }` — "Subdominio genérico delegable a un proveedor de pagos para marketplace (ej. Stripe)" |
| `../03-contextos-acotados-TO-BE.cml` | `BoundedContext ContextoPagos` está listado junto a Notificaciones, Contabilidad y Gestor Documental bajo el comentario `/* Sistemas Genéricos Externos (Comprados/SaaS) */` — no es un contexto que HdA construya |
| `05-vista-modulo.puml` | `component "Pagos" as PAG <<externo>>` — mismo estilo visual que Notificaciones/Contabilidad/Gestión de Agentes; `GT --> PAG : API REST` (llamada síncrona saliente, como cualquier ACL hacia un SaaS) |

**Consecuencia directa para esta entrega:** no se construye un microservicio `Pagos` con su propia
agregación, base de datos y arquitectura hexagonal completa — eso duplicaría, sin mandato del
enunciado ni del tutor, un sistema que el propio diseño de HdA decidió comprar (tipo Stripe Connect).
Lo que sí hay que construir es el **módulo ACL dentro de Gestión de Trabajos** que ya está descrito en
`escenarios_calidad.md` (fila MOD-02, campo "Artefacto"): *"Módulo de reglas regionales (patrón
Strategy) dentro de Gestión de Trabajos; ... el patrón Adapter en Pasarelas (submódulo de Pagos)"* —
la Strategy `ReglaRegional` y el Adapter `PasarelaDePago` viven como **submódulos de
`infrastructure/`/`application/` de Gestión de Trabajos**, no como un servicio aparte. El "Pagos" con
el que se integra es un mock HTTP síncrono (Stripe/MercadoPago), exactamente la misma categoría que
los mocks de Policía/RUES/CONTE en Proveedores — permitido explícitamente por la Regla dura de
comunicación (sección 3.1: *"Las únicas llamadas HTTP síncronas son hacia sistemas externos
mockeados"*).

Esto reduce la cadena a **3 microservicios propios** (Gestión de Trabajos, Proveedores, Reputación) +
**1 sistema externo mockeado adicional** (Pagos/Stripe/MercadoPago, igual que Policía/RUES/CONTE para
DISP-03). El resto de este documento ya refleja esta corrección — todas las menciones a un
microservicio `Pagos` independiente se eliminaron o se reescribieron como "módulo ACL dentro de
Gestión de Trabajos".

> **Nota pendiente, fuera de alcance de esta corrección:** `escenarios_calidad.md` (MOD-02) cita
> *"ver TP3 en Vista de Módulos"*, pero `05-vista-modulo.puml` no tiene ninguna etiqueta `TP3` —
> el diagrama actual no dibuja el submódulo interno de reglas regionales/pasarelas dentro de
> `GT`. Vale la pena que `disenador-escenarios` cierre esta referencia rota antes de la sustentación
> (agregar `TP3` al diagrama, o quitar la referencia del escenario).

---

## 1. Los 3 microservicios propios + 1 sistema externo — ninguno inventado, ya existían en su propio proyecto

| # | Microservicio / sistema | Ya existía en su documentación | Rol en esta entrega |
|---|---|---|---|
| 1 | **Gestión de Trabajos** (propio) | Núcleo del sistema, en el enunciado y en todos los diagramas desde la Entrega 1 | Publica el comando/evento que arranca la cadena; dueño del módulo ACL de Pagos (sección 0.1) |
| 2 | **Proveedores** (Verificación, propio) | Sección "Verificación de proveedores" del enunciado — ✅ ya implementado (DDD, entrega anterior) | 2do eslabón de la cadena; valida DISP-03 (+DISP-02) |
| 3 | **Reputación** (propio) | Bajo COO ("Calidad y disputas"); ya en la Vista de Información y el C&C | 4to servicio, independiente de la cadena — consumidor adicional para ESC-01 |
| — | **Pagos** (externo, `GENERIC_SUBDOMAIN`, ver 0.1) | `ContextoPagos <<externo>>` desde Entrega 1 — nunca fue un contexto propio | 3er eslabón de la cadena, pero como **mock HTTP síncrono** (Stripe/MercadoPago) consumido vía ACL desde Gestión de Trabajos; valida MOD-02 |

**Los 3 escenarios de calidad, sobre la misma cadena (igual que el ejemplo del profesor):**

| Atributo | Escenario | Cómo se prueba (mismo patrón que AeroAlpes) |
|---|---|---|
| Escalabilidad | **ESC-01** | Aumentar la tasa de llamadas al comando `CrearTrabajo` y validar que Proveedores y Reputación siguen consumiendo el tópico sin degradarse |
| Disponibilidad | **DISP-03** (+ DISP-02 de regalo) | Degradar un broker del cluster de Pulsar, o el sistema externo mockeado de verificación, y validar que el resto sigue funcionando |
| Modificabilidad | **MOD-02** | Agregar `ReglaBrasil`/`MercadoPago` en el módulo ACL de Gestión de Trabajos sin tocar `ReglaColombia`/`Stripe` ni el core del servicio |

> **Nota:** ESC-01, DISP-02/03 y MOD-02 son los mismos IDs ya definidos en `escenarios_calidad.md`
> (Entrega 2/3) — esta entrega no crea escenarios nuevos, reutiliza los 3 ya existentes cambiando
> cómo se estresan y con qué servicios reales se validan, tal como pide la guía del profesor.

---

## 1.1 Qué NO hay que construir todavía — alcance reducido por la guía

La guía es explícita: *"que los servicios pudiesen oírse por medio de los tópicos de eventos, pero por ahora no deben reaccionar o completar una transacción — eso es parte de la siguiente entrega"*. Esto reduce el trabajo real de esta entrega:

- **No hace falta** que Proveedores, al recibir el evento de Gestión de Trabajos, dispare automáticamente todo su flujo de verificación de punta a punta — basta con que el consumidor exista y pueda **recibir y registrar** el evento (skeleton de "oír"), sin necesitar completar la cadena.
- **No hace falta** ningún coordinador de Saga (orquestación o coreografía) — eso es 100% Entrega 5.
- **Sí hace falta**: los tópicos de comando y de eventos de cada servicio, existiendo y siendo usados de verdad (publicar y consumir al menos un mensaje real), aunque la reacción del lado receptor sea mínima.

**Sobre Scoring, que sí aparece en el diagrama de ESC-01 de la pptx (Vista C&C):** el diagrama muestra 3 consumidores de `Eventos Trabajos` (Proveedores, Reputación, Scoring). Esta entrega construye solo **2 de los 3** (Proveedores y Reputación) — Scoring queda diseñado y dibujado, pero fuera del alcance de esta entrega parcial, consistente con que no se exige implementar el 100% de lo que aparece en los diagramas de arquitectura, solo lo suficiente para validar los 3 escenarios de calidad. Si se pregunta por Scoring en la sustentación, la respuesta es esta, explícita — no es un olvido.

---

## 1.2 Documento de actividades por miembro (5pt, entregable obligatorio aparte del código)

Cada persona agrega su propia entrada a `ACTIVIDADES.md` en la raíz del repo **como parte de su propio Pull Request**. Este archivo **no existe todavía** en el repo — la primera persona en abrirlo lo crea desde cero:

```markdown
## [Tu nombre]
- Microservicio(s) a cargo: ...
- Qué implementé: ...
- Cómo colaboré con el resto del equipo: ...
```

---

## 1.3 Estado de implementación — explícito por microservicio

| Microservicio | Estado antes de esta entrega | Se agrega ahora |
|---|---|---|
| **Proveedores** | ✅ Ya implementado (hexagonal, agregado `Verificacion`, 4 comandos, 3 queries, entrega DDD anterior); publicador actualmente en **Pub/Sub, validado contra GCP real** (ver nota de integración al inicio de este documento) | Migrar publicador de Pub/Sub a Pulsar · consumidor liviano de `trabajos.finalizado` (solo "oír", sin completar la cadena) · job batch de reproceso de DLQ |
| **Gestión de Trabajos** | ❌ No existía | Comando `CrearTrabajo` (tópico de comando) · publicador de eventos (`trabajos.finalizado`, con carga de estado) · query `ConsultarTrabajo` · tabla `trabajos` · **módulo ACL de Pagos** (comandos `PagarTrabajo`/`Compensar`, Strategy `ReglaRegional` Colombia+Brasil, Adapter `PasarelaDePago` Stripe+MercadoPago mockeados — ver sección 0.1, no es un microservicio aparte) |
| **Reputación** | ❌ No existía | Comando `CalificarProveedor` · consumidor de `trabajos.finalizado` (Event Sourcing: event store + proyección) · query `ConsultarPerfilReputacion` |

---

## 1.4 Qué se mockea y qué debe ser real

| Sistema externo mockeado | ¿Para qué? | ¿Ya existe? |
|---|---|---|
| Policía Nacional, RUES, Entidad certificadora | DISP-03 | ✅ Ya existen (`app/mocks/`, parametrizado) |
| Gestión de Agentes (CRM SaaS) | DISP-02 | ❌ Nuevo, mismo patrón que los de arriba |
| Stripe, MercadoPago | MOD-02 (módulo ACL dentro de Gestión de Trabajos, sección 0.1) | ❌ Nuevos, pueden ser mínimos |

**No se mockea nunca:** las bases de datos de los 3 microservicios propios, el cluster de Apache Pulsar, los tópicos y su publicación/consumo real, ni el agregado `Verificacion` en Proveedores.

---

## 1.5 DDD y arquitectura hexagonal — obligatorio en los 3 microservicios propios

Las instrucciones piden que los principios de DDD sean **claros y explícitos** en el diseño: agregaciones, contextos acotados, inversión de dependencias, capas. Los 3 quedan así, nombrados uno por uno:

- **Contextos acotados:** cada uno de los 3 microservicios propios **es su propio Bounded Context** — Gestión de Trabajos, Proveedores y Reputación tienen cada uno su propio modelo de dominio, su propio lenguaje ubicuo, y no comparten entidades entre sí. Pagos **no** es un cuarto contexto acotado propio (sección 0.1) — es un sistema externo con el que Gestión de Trabajos integra vía ACL, igual que Notificaciones o Contabilidad ya lo hacen en `../03-contextos-acotados-TO-BE.cml`.
- **Agregaciones:** cada contexto tiene su propia raíz de agregado — `Verificacion` en Proveedores (ya construido), y el equivalente nuevo en Gestión de Trabajos y Reputación (ej. `Trabajo` en Gestión de Trabajos, `PerfilReputacion` en Reputación).
- **Inversión de dependencias:** el dominio (`domain/`) define **interfaces** (puertos) que la infraestructura implementa — el dominio nunca importa SQLAlchemy, Pulsar, ni ningún detalle técnico; es infraestructura quien depende del dominio, no al revés. El puerto `PasarelaDePago` de Gestión de Trabajos sigue esta misma regla: el dominio de Trabajo no conoce Stripe ni MercadoPago, solo el puerto.
- **Capas (arquitectura hexagonal/cebolla):**

```
domain/       ← agregado + entidades + VOs + eventos de dominio + repositorio (interfaz)
application/  ← comandos + queries (CQS) + puertos
infrastructure/ ← adaptadores concretos (Postgres, Pulsar, PasarelaDePago)
```

No hace falta lógica de negocio rica (1-2 tablas bastan, la guía lo dice explícito) — pero sí que estos 3 principios sean visibles desde el día 1 en los 3 microservicios propios, no solo en Proveedores.

---

## 1.6 README obligatorio

```markdown
# Hogar de los Alpes — POC de Experimentación (Entrega Parcial)

## Escenarios de calidad validados
[ESC-01, DISP-03 (+DISP-02), MOD-02 — la cadena Gestión de Trabajos → Proveedores → (ACL a Pagos externo), más Reputación]

## Estructura del proyecto
[Árbol de carpetas con los 3 microservicios propios]

## Cómo desplegar
[Pasos para levantar el cluster de Pulsar + cada microservicio localmente]
```

---

## 2. Ajustes sobre Proveedores (lo que ya existe)

1. Migrar el publicador de **Pub/Sub** (validado contra GCP real, ver nota de integración) a **Apache Pulsar**.
2. Agregar un consumidor **liviano** de `trabajos.finalizado` — recibe y registra, no completa la cadena (sección 1.1). El consumidor es un adaptador en `infrastructure/`, llama a un comando en `application/` — nunca toca el agregado ni el ORM directo (sección 4.0.1).
3. Job de reproceso automático de la DLQ (pedido por el profe) — en vez de un cron ciego por tiempo fijo, usa la **API de estadísticas de Pulsar** (`GET /admin/v2/persistent/{topic}/stats`) para monitorear el backlog del tópico DLQ y disparar el reproceso cuando supere un umbral, en vez de depender solo del endpoint manual.

**No se toca, bajo ninguna circunstancia:** el flujo de eventos de dominio intra-servicio (`Verificacion` → `IntentoRegistrado`/`VerificacionCompletada`/`VerificacionAgotoReintentos` → `dispatcher_eventos_dominio.py` → `ServicioDeElegibilidad`, sección 4.0-A). Es el ejemplo concreto de comunicación entre módulos del mismo microservicio — si se simplifica o se salta al migrar el publicador, se pierde justo lo que el profe quiere ver evidenciado.

**Riesgo nuevo, explícito, por la migración a Pulsar:** los CP-1..CP-7 de `implementacion/proveedores/plan.md` (sección 6) y el veredicto H1 ya registrado en `escenarios_calidad.md` fueron validados con Pub/Sub contra GCP real. Cambiar el transporte no es solo un cambio de librería de cliente — Pulsar es *at-least-once* con semánticas de entrega, particionado y DLQ distintas a las de Pub/Sub (que a su vez ya difieren de RabbitMQ, ver `README.md` §"Diferencias local vs. GCP"). **No se puede asumir que el veredicto H1 se mantiene igual solo por analogía** — hay que re-ejecutar al menos CP-4 (falla dura + DLQ) y CP-7 (carga concurrente) contra el nuevo transporte antes de reclamarlo en la sustentación.

---

## 2.1 DISP-03 — evidencia consolidada de lo que le interesa al profe

Todo esto **ya existe y está probado** (13/13 pruebas unitarias de dominio, entrega DDD anterior; además validado contra GCP real el 2026-09-06, ver nota de integración) — no es promesa, es código real. Se consolida aquí para tenerlo listo en un solo lugar:

**Agregaciones:** `Verificacion` es la raíz de agregado, con entidad hija `IntentoVerificacion`. Las invariantes se protegen dentro del agregado, nunca desde fuera — ej. `_mover_a_dlq()` lanza `ErrorTransicionInvalida` si se intenta mover a DLQ sin haber agotado los reintentos.

**Eventos de dominio vs. eventos de integración — la distinción que más le interesa al profe:**
- `VerificacionCompletada` es un **evento de dominio interno** — nunca sale del proceso de Proveedores.
- Ese evento lo recibe `ServicioDeElegibilidad` — **otro módulo, dentro del mismo microservicio** — que decide si el proveedor queda habilitado.
- Solo si `ServicioDeElegibilidad` decide que sí, se publica `ProveedorHabilitado` como **evento de integración**, ese sí hacia otros microservicios (Reputación, y a futuro los que se sumen) vía Pulsar.

**Esto ES la comunicación entre módulos del mismo servicio que preguntas si cubrimos — sí, ya existe:** `Verificacion` (módulo de dominio) → evento interno → `ServicioDeElegibilidad` (otro módulo, mismo microservicio) → solo entonces se decide publicar hacia afuera. Es la prueba de que no todo evento cruza la frontera del servicio.

**Comunicación entre servicios (inter-servicio):** con el consumidor nuevo de `trabajos.finalizado` (sección 2, punto 2), Proveedores pasa a **recibir** de Gestión de Trabajos, además de **publicar** hacia Reputación — comunicación real en ambos sentidos, no solo de salida. (Pagos no consume este evento por Pulsar — es un sistema externo al que Gestión de Trabajos llama directamente, sección 0.1.)

**DLQ y proceso de reintento (batch):** reintentos con backoff (`worker/core.py`, ya construido) → agotados los intentos, se mueve a DLQ (invariante protegido en el agregado) → el job batch nuevo (sección 2, punto 3) monitorea el backlog vía la API de estadísticas de Pulsar y dispara `ReprocesarDesdeDLQ` automáticamente cuando corresponde, en vez de esperar a que un humano lo note.

**Arquitectura hexagonal — confirmada con evidencia de código, no solo de nombres de carpetas:** `domain/` en Proveedores tiene cero imports de SQLAlchemy, FastAPI o Pulsar. Los 2 puertos (`IVerificacionRepository`, `IVerificacionExternaPort`) tienen sus adaptadores concretos en `infrastructure/`. `api/main.py` ya no toca el ORM directo — llama a `application/commands` y `application/queries`. Esto ya se auditó línea por línea contra el riesgo de que fuera "por capas disfrazado de hexagonal", y se descartó: el agregado tiene lógica real que lanza excepciones ante invariantes violados, no es un passthrough decorativo.

---

## 2.2 Migración técnica de Proveedores a Pulsar — checklist concreto, archivo por archivo

La sección 2 dice "migrar el publicador a Pulsar" en una línea. Esto es lo mismo bajado al código real de
`implementacion/proveedores/`, siguiendo el mismo patrón puerto/adaptador que ya existe para RabbitMQ↔Pub/Sub
(no se inventa una estructura nueva, se extiende la que ya está probada):

| # | Archivo | Qué existe hoy | Qué cambia |
|---|---|---|---|
| 1 | `app/common/publicador.py` | `Publicador` (puerto ABC) + `PublicadorRabbitMQ` + `PublicadorPubSub`, cada uno implementando `publicar_solicitud`/`publicar_fallida`/`publicar_evento` | Agregar **`PublicadorPulsar`** como tercer adaptador de la misma interfaz — mismo contrato, mismo cuidado de mantener `publicar_evento` (eventos de integración, ej. `proveedor.habilitado`) sobre un **tópico físicamente distinto** al de solicitudes (repetir aquí el bug de producción del 2026-09-06 — topic compartido → `KeyError` en el consumidor — sería la misma falla otra vez, ahora en Pulsar) |
| 2 | `app/common/mq.py` | Topología de RabbitMQ: declara exchanges/colas/bindings | Nuevo `app/common/pulsar_topology.py` (o renombrar `mq.py` a algo transporte-agnóstico si ya va a haber 3 adaptadores) — en Pulsar los tópicos no necesitan declaración explícita de topología (se auto-crean o se provisionan por Terraform/Helm), pero sí hay que fijar: namespace (`persistent://hda/proveedores/...`), política de retención, y la **suscripción con Dead Letter Policy nativa de Pulsar** (`DeadLetterPolicy` del cliente, equivalente al DLX de RabbitMQ y al `dead_letter_policy` de la suscripción Pub/Sub) |
| 3 | `app/common/config.py` | `transporte: str = "rabbitmq"` + bloques `rabbitmq_*` y `pubsub_*` | Agregar rama `transporte = "pulsar"` + `pulsar_service_url`, `pulsar_topic_solicitudes`, `pulsar_topic_fallidas`, `pulsar_topic_eventos` (mismo patrón 1:1 de nombres que ya existe para Pub/Sub, para no romper la simetría que hace legible el resto del código) |
| 4 | `app/api/main.py` | `if settings.transporte == "pubsub": ... else: PublicadorRabbitMQ` | Agregar rama `elif settings.transporte == "pulsar": PublicadorPulsar(...)` |
| 5 | `app/worker/main.py` | Consumidor **pull** de RabbitMQ (`aio_pika`, loop `async for mensaje in it`, semáforo de concurrencia) | Nuevo `app/worker/pulsar_consumer.py` — consumidor pull con `pulsar-client` (Python), mismo patrón de semáforo/concurrencia acotada; Pulsar sí soporta pull nativo (a diferencia de Pub/Sub, que forzó el diseño push de `push_handler.py`), así que este archivo es más parecido a `worker/main.py` que a `push_handler.py` |
| 6 | `app/worker/push_handler.py` | Handler HTTP para la suscripción **push** de Pub/Sub en Cloud Run | Si el despliegue a GKE mantiene el worker como servicio HTTP (en vez de un pod con loop persistente), Pulsar también soporta push vía webhook — pero el default recomendado es **pull directo** (punto 5), que es más simple y evita reintroducir el bug de payload-sin-`verificacion_id`. Si el equipo decide push igual, replicar la misma defensa en profundidad de `push_handler.py` (descartar con 200 en vez de reventar) |
| 7 | `app/worker/core.py` | Docstring dice explícito "la usan tanto el consumidor pull de RabbitMQ como el handler push de Pub/Sub" — la función `procesar_verificacion()` en sí es agnóstica de transporte | Sin cambios de lógica — solo actualizar el docstring para listar también al consumidor de Pulsar (punto 5). Este archivo es la prueba de que el diseño hexagonal ya pagó: cero cambios de negocio por cambiar de broker |
| 8 | `requirements.txt` | `aio-pika==9.4.3`, `google-cloud-pubsub==2.23.0` | Agregar `pulsar-client==<versión fijada>`. Decidir si `aio-pika`/`google-cloud-pubsub` se quitan (si Proveedores deja de soportar RabbitMQ/Pub/Sub del todo) o se mantienen para no perder la comparación histórica documentada en el README — es una decisión de equipo, no técnica |
| 9 | `infra/pubsub.tf`, `infra/cloudrun.tf` | Terraform que aprovisiona los topics de Pub/Sub y el servicio Cloud Run con push subscription | Pulsar en GKE no se aprovisiona igual que un servicio gestionado: nuevo `infra/pulsar/` con el Helm chart oficial (`values.yaml` del cluster: Zookeeper+BookKeeper+Broker) + manifiestos o Terraform (`helm_release` resource) para los namespaces/tópicos/políticas de retención. `infra/cloudrun.tf` se mantiene si el worker/API siguen en Cloud Run (solo cambia qué broker consumen); si el equipo decide mover el worker a GKE junto al cluster, es un cambio de infraestructura más grande, a evaluar aparte |
| 10 | `implementacion/proveedores/README.md` §"Diferencias local vs. GCP" | Documenta RabbitMQ↔Pub/Sub (orden FIFO, filtrado por routing key, at-least-once) | Agregar una tercera columna Pulsar: orden garantizado por **partición** (no global, similar a Kafka), `DeadLetterPolicy` nativa por suscripción, *at-least-once* con posibilidad de *effectively-once* si se usa deduplicación de productor — para que la comparación de 3 transportes quede tan explícita como la de 2 hoy |
| 11 | `tests/test_escenarios_disp03.py` | CP-1..CP-7 corren contra RabbitMQ local (Docker) o Pub/Sub (GCP real), seleccionado por `settings.transporte` | Añadir el caso `transporte=pulsar` a la matriz de ejecución (local vía el `docker-compose` del cluster, después contra GKE) — sin esto, "migrar a Pulsar" es un cambio de infraestructura sin prueba, exactamente el tipo de brecha que el ciclo `experimento-runner`→`validador-hipotesis` existe para atrapar |

**Orden recomendado para ejecutar esta migración (evita quedar con el sistema roto a medio camino):**
1. Puntos 1-3 (puerto + topología + config) — se pueden escribir y probar unitariamente sin tocar `main.py`.
2. Punto 5 (consumidor Pulsar) en paralelo con el punto 1, contra el cluster local del punto de la sección 3.
3. Puntos 4 y 8-9 (enchufar en `api/main.py`, dependencias, infra) — aquí es donde el sistema pasa a depender de Pulsar de verdad.
4. Punto 11 (re-ejecutar CP-1..CP-7) — **antes** de dar la migración por terminada, no después. Ver el riesgo ya señalado en la sección 2: no se puede asumir que el veredicto H1 se mantiene solo por analogía con Pub/Sub.
5. Puntos 6, 7, 10 — documentación y limpieza, al final.

---

## 3. Broker de eventos: Apache Pulsar — cluster, no standalone

La rúbrica exige *"el equipo configuró, desplegó y usó un **cluster**"* (5pt) — `bin/pulsar standalone` no cuenta, empaqueta todo en un proceso pensado solo para pruebas rápidas.

**Local:** `docker-compose.yml` con Zookeeper + BookKeeper + Broker como servicios separados (1 réplica de cada uno ya cuenta como cluster real, no monolítico).

**Despliegue (punto 9 + el ítem de "desplegado en plataforma de preferencia", 5pt aparte):** mismo cluster en **GKE** vía el Helm chart oficial de Pulsar — no hay servicio gestionado nativo en GCP para Pulsar, así que se autogestiona dentro de la nube ya elegida.

**Tópicos:**
- `trabajos.finalizado` — comando `CrearTrabajo` dispara este evento (Gestión de Trabajos → Proveedores, Reputación). *Nota de simplificación:* el nombre `TrabajoFinalizado` ya está establecido en los diagramas de la Entrega 3 (es el evento que conecta Gestión de Trabajos con el resto del sistema en el C&C) — para esta entrega, el comando `CrearTrabajo` publica directamente ese evento como skeleton simplificado, sin modelar los pasos intermedios del ciclo de vida completo del trabajo (eso sí sería parte de la Saga, Entrega 5).
- `verificacion.solicitada`, `verificacion.fallida-dlq`, `proveedor.habilitado` (Proveedores, ya existentes, migran de Pub/Sub a Pulsar)

**Pagos no tiene tópico propio** (sección 0.1): `PagarTrabajo`/`Compensar` son comandos de **aplicación internos** de Gestión de Trabajos (dentro del mismo proceso, CQS puro — sección 4.1 de `implementador-ddd.md`), que a su vez invocan el puerto `PasarelaDePago` vía HTTP síncrono contra el mock de Stripe/MercadoPago. No cruzan Pulsar porque no cruzan un Bounded Context propio — la única frontera real ahí es la de un sistema externo, cubierta por la Regla dura de comunicación (sección 3.1).

**Pendiente de rúbrica al cerrar esta migración:** una vez el publicador de Proveedores use Pulsar de verdad, la fila DISP-03 de `escenarios_calidad.md` (campos "Decisión arquitectural", "Tradeoffs", "Riesgos" — Regla 2 de `REGLAS-DURAS-rubrica-entrega-3.md`) debe actualizarse para reflejar Pulsar en vez de "RabbitMQ local / Pub/Sub en GCP". Es trabajo de `disenador-escenarios`, después de que `validador-hipotesis` confirme que el veredicto H1 se sostiene con el nuevo transporte (ver riesgo señalado en la sección 2).

---

## 3.1 Regla dura de comunicación — sin excepciones, ni siquiera para queries

Aclaración del profe, más estricta que la rúbrica original: *"NO debe haber llamados síncronos entre los servicios usando gRPC o HTTP. Debe crear tópicos de comando para las acciones y tópicos de eventos para propagar."*

**Nuestro diseño ya cumple esto sin cambios:**
- Gestión de Trabajos → Proveedores/Reputación: 100% por evento, nunca por llamada directa.
- Ningún servicio le pregunta nada a otro en tiempo real — todo lo que necesitan viaja en la carga de estado del evento.
- Las únicas llamadas HTTP síncronas son hacia sistemas externos mockeados (Policía/RUES/CONTE, Gestión de Agentes, **Stripe/MercadoPago**) — no son "entre nuestros servicios", son ACL hacia sistemas comprados, exactamente como ya lo modela `../03-contextos-acotados-TO-BE.cml` para Pagos/Notificaciones/Contabilidad (sección 0.1).
- La API HTTP de cada microservicio (ej. `POST /verificaciones`) es la puerta de entrada del sistema, no una llamada de un microservicio a otro.

---

## 4. Diseño de eventos

### 4.0 Dos tipos de comunicación por evento — intra-servicio y entre servicios (el profe le da peso especial a esto)

No es lo mismo un módulo hablándole a otro módulo **dentro del mismo microservicio**, que un microservicio hablándole a **otro microservicio**. Los dos deben quedar demostrados, con ejemplos concretos — no solo mencionados.

**A) Comunicación intra-servicio (módulo↔módulo, dentro de Proveedores) — ya existe, construido y probado desde la entrega de DDD anterior:**

```
Verificacion (agregado, domain/)
      │ registra internamente
      ▼
IntentoRegistrado / VerificacionCompletada / VerificacionAgotoReintentos   ← eventos de DOMINIO, nunca salen del proceso
      │
      ▼
dispatcher_eventos_dominio.py   ← reparte el evento a otros módulos, todavía dentro de Proveedores
      │
      ▼
ServicioDeElegibilidad   ← OTRO módulo del mismo microservicio, reacciona al evento de dominio
      │ decide si el proveedor queda habilitado
      ▼
publica ProveedorHabilitado   ← AQUÍ, y solo aquí, cruza a Pulsar como evento de integración
```

Estos 3 eventos (`IntentoRegistrado`, `VerificacionCompletada`, `VerificacionAgotoReintentos`) **nunca tocan Pulsar** — son el ejemplo real de comunicación intra-servicio que pide el profe. **Al migrar el publicador a Pulsar (sección 2), este flujo interno no se toca** — solo cambia el transporte del evento que sí sale (`ProveedorHabilitado`), nunca los 3 internos.

**B) Comunicación entre servicios (Pulsar) — la cadena de la transacción larga:**

```
Gestión de Trabajos --trabajos.finalizado--> Proveedores / Reputación
Proveedores --proveedor.habilitado--> (otros contextos que lo consuman a futuro)
Gestión de Trabajos --HTTP síncrono (ACL, no Pulsar)--> Pagos (mock Stripe/MercadoPago, sección 0.1)
```

Estos sí cruzan el proceso — van por tópico de Pulsar, con schema Avro versionado (sección 4.2/4.3). La
llamada a Pagos es la excepción explícita y permitida de la sección 3.1: no cruza un Bounded Context
propio, cruza hacia un sistema comprado.

### 4.0.1 Arquitectura hexagonal en DISP-03 — ya auditada, se preserva al extenderla

Ya se verificó exhaustivamente (no por nombres de carpetas, por imports reales): `domain/` en Proveedores no importa nada de infraestructura, `application/commands` y `application/queries` no importan infraestructura directo, y el agregado `Verificacion` tiene invariantes reales (lanza excepciones, no solo pone un campo). **Al agregar el consumidor nuevo de `trabajos.finalizado` y el job batch de la DLQ (sección 2), ambos deben respetar la misma regla**: el consumidor es un adaptador de entrada en `infrastructure/`, que llama a un comando en `application/` — nunca toca el agregado directo ni el ORM. Si esto se rompe al agregar las piezas nuevas, se pierde exactamente lo que ya se había corregido.

### 4.1 ¿Integración o con carga de estado?

| Evento | Tipo | Por qué |
|---|---|---|
| `trabajos.finalizado` (ESC-01) | **Con carga de estado** | 2 consumidores (Proveedores, Reputación) necesitan datos distintos del trabajo; evita que cada uno llame de vuelta a Gestión de Trabajos bajo picos de 4x |
| `verificacion.solicitada` (DISP-03) | Delgado | Solo IDs, no hay urgencia de evitar callbacks |
| `verificacion.fallida-dlq`, `proveedor.habilitado` (DISP-03) | Con carga de estado | Evita re-consulta |

`PagarTrabajo`/`Compensar` (MOD-02) no aparecen en esta tabla — no son tópicos de Pulsar, son comandos
internos de Gestión de Trabajos (sección 3, "Pagos no tiene tópico propio").

### 4.2 Avro, no Protobuf

Tres razones: (1) es el schema nativo del Schema Registry de Pulsar, compatibilidad `BACKWARD/FORWARD` integrada sin herramientas extra; (2) equipo 100% Python — Avro se define en JSON, sin paso de compilación como exige Protobuf; (3) resolución de esquemas por nombre de campo más flexible para eventos que van a evolucionar rápido.

### 4.3 Event Stream Versioning

Por **compatibilidad de schema**, no por nombre de tópico. Campos nuevos siempre opcionales con default (`BACKWARD`), Schema Registry de Pulsar configurado en modo `BACKWARD`, campos retirados se marcan `deprecated` al menos una entrega antes de eliminarse.

---

## 5. Almacenamiento: descentralizado (no híbrido)

Se evaluó explícitamente agrupar Reputación con algún otro servicio (candidato más obvio, ya que ambos consumirían el mismo evento) y se descartó: no hay ninguna consulta cruzada que una BD compartida simplificaría (todo se resuelve con la carga de estado del evento), y mantiene consistencia con "BD por microservicio", ya defendido desde ESC-03 en la Entrega 3.

Cada uno de los 3 microservicios propios tiene su propia base de datos — nadie consulta la BD de otro directamente. Pagos no aporta una BD propia al conteo: su estado "actual" (pagos realizados, compensaciones) vive en la tabla `pagos` de Gestión de Trabajos, dueño único de ese submódulo (sección 0.1).

---

## 6. CRUD vs. Event Sourcing (mezcla justificada)

| Microservicio | Patrón | Por qué |
|---|---|---|
| Gestión de Trabajos | CRUD clásico | Simplicidad de razonamiento para el PoC; incluye la tabla `pagos` del módulo ACL (sección 0.1) |
| Proveedores | CRUD clásico (ya construido) | El estado se guarda directo; eventos de dominio son para side-effects |
| **Reputación** | **Event Sourcing** | El read model (`Perfil de reputación`) es una proyección acumulada de calificaciones — el caso más natural de los 3 |

---

## 7. Checklist con el desglose exacto de puntos de la rúbrica

| Ítem de la rúbrica | Puntos | Dónde queda cubierto |
|---|---|---|
| 3 microservicios propios diseñados e implementados para 3 escenarios de calidad (+1 sistema externo mockeado, Pagos) | 30pt | Sección 1 — cadena Gestión de Trabajos→Proveedores→(ACL a Pagos) + Reputación |
| Comunicación por comandos/eventos, sin excepciones síncronas | 20pt | Sección 3.1 |
| Cluster de Apache Pulsar configurado, desplegado y usado | 5pt | Sección 3 |
| Tipos de evento justificados + esquema + evolución | 5pt | Sección 4 |
| Topología de almacenamiento justificada e implementada | 5pt | Sección 5 |
| CRUD o Event Sourcing en al menos 3 de los 4 servicios* | 25pt | Sección 6 — los 3 propios cubiertos. *Si la rúbrica cuenta literalmente "4 servicios", puede requerir confirmación con el tutor de que 3 propios + 1 externo mockeado satisface el ítem — ver sección 0.1 |
| Documento de actividades por miembro | 5pt | Sección 1.2 |
| Servicios desplegados en plataforma de preferencia | 5pt | Sección 3 — GKE |

**Total: 100pt** cubiertos en diseño — falta la ejecución (sección 8 de `13-guia-entrega-4-pasos.md`, Fase 3).

---

## 8. Runbook por persona — reparto en 3 partes equivalentes (Frans, Johan, Daniel)

**Por qué este reparto y no otro:** cada quien es dueño de carpetas que nadie más toca (cero archivos
compartidos entre ramas, salvo lo marcado explícitamente abajo) — así la contribución de cada persona
queda 100% atribuible en `git log --author` y en el historial de PRs, que es justamente lo que hace
verificable una contribución equitativa real, no solo declarada en `ACTIVIDADES.md`. El peso de las 3
partes es comparable (cada una combina 1 pieza "pesada" — un microservicio nuevo o el cluster — con 1-2
piezas más livianas), no una simple división por conteo de tareas:

| Persona | Carpetas de las que es dueño único | Peso relativo |
|---|---|---|
| **Frans** | `implementacion/gestion-de-trabajos/` completo (núcleo + módulo ACL de Pagos) | 1 microservicio nuevo + 1 submódulo (Strategy+Adapter) |
| **Johan** | `implementacion/proveedores/` (ajustes) + `implementacion/mocks-pagos/` (nuevo) + `.github/workflows/pr-quality-gate.yml` | 1 migración sobre servicio ya certificado (requiere más cuidado, no más código) + mocks + CI |
| **Daniel** | `implementacion/reputacion/` (nuevo) + `implementacion/pulsar-infra/` (cluster local + Helm/GKE) | 1 microservicio nuevo (Event Sourcing) + infraestructura del cluster |

**Antes de empezar, cada quien corre esto una sola vez, con sus datos reales:**

```bash
git config user.name "Tu Nombre Real"
git config user.email "tu-correo-real@ejemplo.com"

mkdir -p .claude
echo '{ "includeCoAuthoredBy": false }' > .claude/settings.local.json
```

Revisa el commit antes de hacer push (`git log -1`) — si ves `Co-Authored-By: Claude`, quítalo con `git commit --amend`.

---

### Frans — Gestión de Trabajos (núcleo + módulo ACL de Pagos)

```bash
git checkout main && git pull
git checkout -b feature/gestion-trabajos-y-acl-pagos
```

**Prompt para el agente:**
> Lee `experimento-arquitectura/contexto/12-plan-entrega-4.md` completo (en especial la sección 0.1) y `.claude/agents/implementador-ddd.md`. Necesito, todo dentro de un único microservicio nuevo `Gestión de Trabajos` en `experimento-arquitectura/implementacion/gestion-de-trabajos/` (hexagonal: domain/application/infrastructure):
>
> 1. **Núcleo**: comando `CrearTrabajo` (expuesto como tópico de comando en Pulsar, no HTTP entre servicios), query `ConsultarTrabajo`, tabla `trabajos`, y publicador del evento `trabajos.finalizado` con carga de estado (ver sección 4.1 del plan).
> 2. **Módulo ACL de Pagos** (NO como servicio aparte — ver sección 0.1: Pagos es un `GENERIC_SUBDOMAIN` externo según `01-dominios-subdominios.cml`/`../03-contextos-acotados-TO-BE.cml`/`05-vista-modulo.puml`): comandos de aplicación `PagarTrabajo`/`Compensar`, Strategy `ReglaRegional` (`ReglaColombia` + `ReglaBrasil` nueva), puerto+adaptador `PasarelaDePago` (`Stripe` + `MercadoPago`, mockeados vía HTTP síncrono contra los mocks que construye Johan por separado), query `ConsultarPago`, tabla `pagos` (misma BD de Gestión de Trabajos, no una BD nueva).
>
> Ambas piezas comparten el mismo esqueleto hexagonal pero viven en archivos/módulos separados dentro
> de `domain/`, `application/commands/` e `infrastructure/adapters/` — para que quede claro en el
> código que son dos responsabilidades distintas del mismo Bounded Context, no una mezcla.

```bash
git add .
git commit -m "feat: microservicio Gestion de Trabajos (nucleo + modulo ACL de Pagos)"
git push -u origin feature/gestion-trabajos-y-acl-pagos
```

**Coordinación:** el adaptador `PasarelaDePago` necesita las URLs de los mocks de Stripe/MercadoPago
que construye Johan (`implementacion/mocks-pagos/`) — puedes desarrollar contra un stub local primero
y apuntar al mock real de Johan antes de abrir el PR final, sin bloquear tu propio avance.

---

### Johan — Ajustes a Proveedores + mocks de Pagos + CI extendido

```bash
git checkout main && git pull
git checkout -b feature/proveedores-pulsar-y-ci
```

**Prompt para el agente:**
> Lee `experimento-arquitectura/contexto/12-plan-entrega-4.md` (secciones 0.1, 2, 2.2, 3, 3.1) y `.claude/agents/implementador-ddd.md`. Necesito:
>
> 1. Sobre `Proveedores` (`implementacion/proveedores/`) ya existente: (a) migra el publicador de Pub/Sub a Apache Pulsar siguiendo el checklist archivo por archivo de la sección 2.2, (b) agrega un consumidor **liviano** de `trabajos.finalizado` — solo recibe y registra el evento, no completes la cadena de verificación automáticamente (ver sección 1.1: eso es de la Entrega 5), (c) agrega un job programado que use la API de estadísticas de Pulsar para reprocesar la DLQ automáticamente cuando el backlog supere un umbral, llamando a `ReprocesarDesdeDLQ`.
> 2. Los dobles (mocks) de **Stripe** y **MercadoPago** para MOD-02, en `implementacion/mocks-pagos/` — mismo patrón que los mocks existentes de Policía/RUES/CONTE en `implementacion/proveedores/app/mocks/` (FastAPI + endpoint de control de fallas/latencia). **No** son un microservicio de dominio — son sistemas externos simulados que consume el módulo ACL de Pagos que construye Frans dentro de Gestión de Trabajos.
> 3. Extiende `.github/workflows/pr-quality-gate.yml` a matriz, cubriendo los 3 microservicios propios en `experimento-arquitectura/implementacion/*/` (Gestión de Trabajos, Proveedores, Reputación), no solo DISP-03.
>
> **No toques el flujo de eventos de dominio intra-servicio** (`Verificacion` → `IntentoRegistrado`/`VerificacionCompletada`/`VerificacionAgotoReintentos` → `dispatcher_eventos_dominio.py` → `ServicioDeElegibilidad`) — es el ejemplo de comunicación entre módulos del mismo microservicio, y debe seguir intacto. Solo cambia el transporte del evento que sí sale hacia afuera (`ProveedorHabilitado`), de Pub/Sub a Pulsar. No toques el agregado `Verificacion` ni sus invariantes.

```bash
git add .
git commit -m "feat: migracion Proveedores a Pulsar + mocks Stripe/MercadoPago + CI extendido"
git push -u origin feature/proveedores-pulsar-y-ci
```

**Coordinación:** el punto 3 (CI) toca un archivo compartido (`pr-quality-gate.yml`) que los otros dos
también necesitan para sus propios PRs — conviene mergear este PR primero o coordinar el orden con
Daniel/Frans para no pisarse la matriz del workflow.

---

### Daniel — Reputación + infraestructura del cluster de Pulsar

```bash
git checkout main && git pull
git checkout -b feature/reputacion-y-pulsar-infra
```

**Prompt para el agente:**
> Lee `experimento-arquitectura/contexto/12-plan-entrega-4.md` (secciones 1, 1.1, 3, 6) y `.claude/agents/implementador-ddd.md`. Necesito:
>
> 1. Un microservicio nuevo `Reputación` en `experimento-arquitectura/implementacion/reputacion/` — hexagonal, con **Event Sourcing** (justificación en sección 6): comando `CalificarProveedor`, un consumidor **liviano** de `trabajos.finalizado` (solo recibe y registra, no completa ninguna cadena — ver sección 1.1), query `ConsultarPerfilReputacion` que proyecta el event store.
> 2. Infraestructura del **cluster** de Apache Pulsar en `experimento-arquitectura/implementacion/pulsar-infra/`: `docker-compose.yml` local (Zookeeper + BookKeeper + Broker como servicios separados, no `bin/pulsar standalone`) + el Helm chart oficial de Pulsar parametrizado para GKE (sección 3 del plan).
>
> Solo esqueleto de negocio — no lógica de negocio completa. La infraestructura del punto 2 sí debe
> quedar funcional de verdad (`docker-compose up` levantando un cluster real), porque los otros dos
> la necesitan para probar sus propios publicadores/consumidores.

```bash
git add .
git commit -m "feat: microservicio Reputacion (event sourcing) + infra cluster Pulsar"
git push -u origin feature/reputacion-y-pulsar-infra
```

**Coordinación:** este PR es el que más urge mergear primero (sección 10, orden de construcción) —
sin el cluster de Pulsar corriendo, ni Frans ni Johan pueden probar sus publicadores/consumidores
contra algo real. Avisar al equipo apenas el `docker-compose.yml` del punto 2 esté funcional, aunque
el resto de Reputación siga en progreso.

---

**Antes de mergear cualquiera de los 3 PRs:** que otra persona del equipo (no quien lo escribió) lo revise y comente en GitHub antes de aprobar. Cada quien agrega su propia entrada a `ACTIVIDADES.md` (sección 1.2) en su propio PR — es la evidencia formal de la contribución individual, además del propio historial de commits por carpeta.

---

## 9. Cómo se prueban los 3 escenarios — con las herramientas que dio el profe

| Escenario | Cómo se ejecuta la prueba | Herramienta concreta |
|---|---|---|
| ESC-01 | Generar carga creciente de mensajes sobre el tópico `trabajos.finalizado`, midiendo throughput y latencia de punta a punta | **Pulsar Perf** (`pulsar-perf produce`/`consume`) — es la herramienta nativa de Pulsar para esto exacto, mejor que un script propio porque mide directo la capacidad del broker, no solo de nuestro código. Complementar con **JMeter** si además se quiere estresar el endpoint HTTP que dispara `CrearTrabajo` (dos capas: broker y API) |
| ESC-01 (análisis) | Visualizar la distribución de latencias del resultado de Pulsar Perf (percentiles p50/p95/p99) | **Histogram Plotter** de HdrHistogram — Pulsar Perf ya exporta en formato `.hdr`, se sube directo, sin transformar nada |
| DISP-03 (+DISP-02) | Inyectar falla en el mock externo (`/_control/config`) — ya lo teníamos — **y ahora además**, monitorear en vivo el tamaño de la DLQ mientras ocurre la falla | **API de estadísticas de Pulsar** (`GET /admin/v2/persistent/{topic}/stats`) — resuelve el pendiente que ya habíamos identificado: "sin alerta activa sobre el tamaño de la DLQ, el SLA de 24h podría incumplirse en silencio". El job batch de reproceso (sección 2, punto 3) puede usar esta misma API como su disparador — reprocesa cuando el backlog del tópico DLQ supera un umbral, no solo por tiempo fijo |
| DISP-03/02 (degradar cluster) | Tumbar un broker del cluster y confirmar que el resto sigue aceptando/publicando | **CLI Tools de Pulsar** (`pulsar-admin brokers list`, `bin/pulsar-admin brokers healthcheck`) — para apagar un broker específico y verificar el estado del cluster antes/después, sin adivinar |
| MOD-02 | Agregar `ReglaBrasil`/`MercadoPago` sin tocar el resto | Diff de código (sin herramienta especial) |
| Mocks (todos) | Que los externos respondan con datos realistas, no solo `{"status": "ok"}` hardcodeado | **Mockaroo** — generar respuestas sintéticas pero con sintaxis y semántica correctas (ej. un NIT colombiano con formato válido, no `"123"`) |

**Sobre el cluster de Pulsar (sección 3):** el profe menciona **DataStax Astra Streaming** y **StreamNative** como alternativas gestionadas a instalar el cluster manualmente. Es tentador por tiempo — pero **no se recomienda usarlas aquí**: la rúbrica pide explícitamente que *"el equipo **configuró**, desplegó y usó un cluster"* (5pt) — con un servicio 100% gestionado, la configuración del cluster la hace el proveedor, no ustedes, lo que debilita justo lo que ese ítem evalúa. Se mantiene la sección 3 como está (Docker local + GKE) — más trabajo, pero evidencia real de que configuraron el cluster ustedes mismos.

**Ejemplos de mala experimentación a evitar (explícito en la guía del profe):** no probar "que Pulsar sirve", no medir cobertura de código, no medir "cuánto tardó agregar un método". Las métricas deben ser las que ya definimos en `escenarios_calidad.md` para cada escenario (latencia de aceptación, % disponibilidad, etc.), no sustitutos técnicos fáciles de medir pero irrelevantes al negocio.

---

## 10. Orden de construcción sugerido

1. **Cluster de Pulsar local** (Docker, Daniel) — antes que cualquier código; se avisa al equipo apenas esté funcional, sin esperar a que el resto de su PR (Reputación) esté terminado.
2. **Mocks de Stripe/MercadoPago** (Johan) — en paralelo con el punto 1, no depende del cluster.
3. **Ajustes a Proveedores** (migrar a Pulsar, Johan) — valida que el cluster del punto 1 funciona antes de construir encima.
4. **Gestión de Trabajos — núcleo** (Frans) — publisher de `trabajos.finalizado`, arranca la cadena; depende del cluster del punto 1.
5. **Reputación — resto del microservicio** (Daniel) — consumidor de `trabajos.finalizado`, en paralelo con el punto 4.
6. **Módulo ACL de Pagos** dentro de Gestión de Trabajos (Frans, sección 0.1) — una vez el núcleo del punto 4 ya tiene su estructura hexagonal, y apuntando a los mocks del punto 2.
7. **Consumidor liviano** en Proveedores (Johan), una vez Gestión de Trabajos ya publica de verdad.
8. **Extender el CI** (Johan) — al final, una vez los 3 microservicios propios tengan su propio `tests/`.

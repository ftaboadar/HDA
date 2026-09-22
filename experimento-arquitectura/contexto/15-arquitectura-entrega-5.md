# Entrega 5 — Arquitectura de referencia (fuente de verdad)

> **Este documento manda.** Si otro archivo del repo contradice algo de aquí (en especial
> `historico/12-plan-entrega-4.md`, `historico/13-guia-entrega-4-pasos.md`, `historico/11-implementacion-ddd-verificacion.md` o
> una versión vieja de las vistas), **gana este documento**: los otros son registro histórico de
> entregas anteriores. Si al implementar descubres que algo de aquí está mal o incompleto, corrígelo
> **aquí primero** y luego el código, nunca al revés.
>
> Estado: decisiones de alcance **cerradas** con el equipo el 2026-09-21. La rúbrica de la Entrega 5
> todavía no está en el repo; lo que depende de ella está marcado **[PENDIENTE-RÚBRICA]**.
> Rama de trabajo: `feature/entrega-5-journey-saga` (sale de `main`).

Cómo se despliega y cómo se construye cada servicio (layout de carpetas, Terraform, Pulsar, CI):
[`../implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](../implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md).

**Este documento es el diseño objetivo, no el estado actual.** Qué existe de verdad hoy y qué se puede
desplegar: [`../implementacion/ESTADO-IMPLEMENTACION.md`](../implementacion/ESTADO-IMPLEMENTACION.md).

---

## 1. Qué pide esta entrega (en una frase)

Hasta la Entrega 4 los 4 escenarios implementados (ESC-01, DISP-03, DISP-02, MOD-02) corrían
**sueltos**: cada uno se disparaba con su propio endpoint, y los servicios "se oían" pero no
reaccionaban (ver el docstring de `reputacion/app/application/commands/registrar_evento_trabajo_finalizado.py`:
*"eso es parte de la Saga, Entrega 5"*). La Entrega 5 **cierra la saga**: un solo journey de negocio,
del proveedor habilitado al trabajo pagado y calificado, con **comunicación entre servicios** (eventos
de integración por Pulsar) y **comunicación entre módulos** dentro de cada servicio (eventos de
dominio en memoria + llamadas síncronas a la capa de aplicación del otro módulo), siguiendo las 4
vistas de arquitectura del equipo.

## 2. Las 4 vistas vigentes

| Vista | Archivo visual (lo que se presenta) | Fuente legible por agentes | Qué fija |
|---|---|---|---|
| Contexto | `diagramas/entrega-5/01-vista-contexto.{png,svg}` | `04-vista-contexto.puml` | actores, servicios, externos |
| Información | `diagramas/entrega-5/02-vista-informacion.{png,svg}` | `07-vista-informacion.puml` | agregados y referencias por ID |
| Módulos | `diagramas/entrega-5/03-vista-modulos.{png,excalidraw.svg}` | `05-vista-modulo.puml` | módulos internos de cada servicio y cómo se hablan |
| C&C funcional | `diagramas/entrega-5/04-vista-cyc-funcional.{drawio,svg,png}` | `06-vista-cyc.puml` | runtime: comandos, tópicos, ACL, DLQ, flujos |

Las `.puml` se reescribieron para reflejar las 4 vistas **ya corregidas** según la sección 3. Las
imágenes exportadas (PNG/SVG) todavía no traen todas las correcciones: la lista exacta de lo que falta
redibujar está en `diagramas/entrega-5/CORRECCIONES.md`. El `.drawio` de C&C ya está corregido; falta
volver a exportar su PNG/SVG desde draw.io.

## 3. Decisiones cerradas (no reabrir sin acuerdo del equipo)

### 3.1 Inconsistencias entre vistas — cómo se resolvieron

| # | Tema | Decisión |
|---|---|---|
| A1 | ¿Pagos interno o externo? | **Gestión de Pagos es un Bounded Context propio** (`implementacion/pagos/`, microservicio con BD propia). **La Pasarela** (Stripe, MercadoPago) es el sistema **externo**. El subdominio `Pagos` sigue siendo `GENERIC_SUBDOMAIN` en el `.cml` (la capacidad es genérica), pero ya no es "algo que se compra entero": HdA construye el contexto y compra solo la pasarela. Invalida la sección 0.1 de `historico/12-plan-entrega-4.md` |
| A2 | Broker | **Apache Pulsar** (VM `pulsar-infra/gcp`) para toda la integración entre servicios. Desde A24 **también la cola de Verificación (DISP-03)** va en Pulsar, con su DLQ nativa: un solo broker. Donde un diagrama diga "Kafka" o "bus genérico", léase Pulsar |
| A3 | Novedades | **Módulo dentro de Gestión de Trabajos**, no un servicio aparte. En C&C se dibuja como "camino alterno" pero vive en el mismo proceso que GT |
| A4 | Vuelta Proveedores → GT | GT publica `TrabajoCreado` → Proveedores publica `ElegiblesPublicados` → **el canal dueño del origen** elige (ver A9) → `ProveedorSeleccionado` → GT asigna. La vuelta existe y pasa por el canal, nunca directo de Proveedores a GT |
| A5 | Cierre del pago | **Pagos publica `PagoLiberado` / `PagoFallido` / `PagoCompensado` y GT los consume** (PAGADO / compensación). Faltaba en todas las vistas; se agregó |
| A6 | Circuit Breaker de GT (sidecar) | Solo hacia **Notificaciones (Twilio) y Gestor Documental (S3)**, llamadas REST síncronas. **Pagos NO va por REST desde GT**: va por evento (`TrabajoFinalizado`) |
| A7 | Vista de módulos | Se corrigen: SP4 faltante, "MercadoPago (futuro)" → ya implementado (es el cambio aplicado de MOD-02), Strategy regional visible dentro de Pagos, etiquetas encimadas en GT |
| A8 | Cotización (información vs. módulos/C&C) | **`Cotizacion` es entidad de `SolicitudTrabajo` (Marketplace).** `Trabajo` guarda solo la cotización aceptada **por ID** y su `Monto`. Decidido por el equipo el 2026-09-21 (antes D5) |
| A9 | ¿Quién elige al proveedor? (antes D2, cerrada con el enunciado p.9-14) | **Siempre elige alguien de negocio y GT solo asigna** (GT es agnóstico al origen). **Marketplace:** el dueño compara cotizaciones y selecciona (p.12). **Siniestros:** el proveedor cotiza si aplica y **el partner aprueba** (comando *Aprobar paso*), después de filtrar por su red permitida/homologados y su monto máximo (p.9, p.13). **Suscripciones:** el cliente elige en el primer ciclo; los siguientes repiten el mismo proveedor durante todo el periodo, mínimo el mes (A13). **No-show:** se publica una lista nueva sin el que falló y elige el mismo actor del origen (p.14: *"el sistema inició re-asignación: 3 candidatos"*). Filtro de elegibles: **verificación básica** (Marketplace, Suscripciones) o **completa** (Siniestros) (p.10) + categoría + zona + **disponibilidad** (p.12; ver A12) + **franja libre en la agenda** (A14). Orden: **reputación compuesta** (A10), luego número de trabajos calificados; proveedor sin calificaciones = neutro 3,0 |
| A10 | Reputación compuesta (enunciado p.10: *"calificaciones, cumplimiento, garantías"*) | `reputacion = promedio_calificaciones × tasa_cumplimiento − 0,2 × garantias_reclamadas` (mínimo 0), con `tasa_cumplimiento = 1 − no_shows / asignaciones`. Reputación cuenta asignaciones (`AgendaConfirmada`), no-shows y garantías (`NovedadResuelta`). Los pesos son del PoC y se pueden ajustar sin cambiar el contrato |
| A11 | Novedades de siniestros sincronizadas con el partner (antes D3; enunciado p.14 iv) | **Dentro del alcance.** Toda novedad de un trabajo de origen SINIESTRO se publica (`NovedadRegistrada`) y **Siniestros·Orquestación de Partner** aplica la `ReglaDeAprobacion` del partner: si no requiere aprobación responde `DecisionPartner(APROBADA)` enseguida; si la requiere (p. ej. *cambios > umbral de monto*), queda pendiente hasta que el partner ejecute *Aprobar paso*. GT **no aplica** la resolución (reasignar, compensar) de un trabajo de siniestro hasta recibir `DecisionPartner(APROBADA)` |
| A12 | Disponibilidad del proveedor (antes D7; enunciado p.12 *"categoría, zona y disponibilidad"*) | `capacidad = 3 × técnicos verificados` (persona natural = 1 técnico → 3; empresa con 5 técnicos verificados → 15). Disponible = trabajos asignados sin finalizar < capacidad; Proveedores lo cuenta con `AgendaConfirmada` (+1) y `TrabajoFinalizado` (−1). **Nunca lista vacía:** si quedan menos de 3 elegibles, se agregan los que están en su límite, ordenados por menor carga. Configurable: `CAPACIDAD_POR_TECNICO=3`, `MINIMO_ELEGIBLES=3`. Razón: con el enunciado (8.400 siniestros/día, 6.500 acreditados, ~2,4 días por trabajo) un proveedor promedio ya tiene ~3 trabajos abiertos en un día normal y ~12 en el pico 4x de ESC-01; un tope fijo de 3 vaciaría las listas en el pico |
| A13 | Continuidad del proveedor en Suscripciones (antes D6) | El cliente elige al proveedor en el primer ciclo y **ese mismo proveedor atiende todos los ciclos del periodo contratado (mínimo el mes)**; al renovar el periodo continúa el mismo, salvo que el cliente pida cambio. Solo se rota antes por **no-show** o si el proveedor queda **deshabilitado** (re-validación fallida); en ese caso el cliente vuelve a elegir entre elegibles. Desde el segundo ciclo `CicloSuscripcion` ya trae `proveedor_id` y GT asigna directo, sin pedir elegibles |
| A14 | Agenda del técnico: una franja reservada **bloquea cualquier trabajo** (suscripción, Marketplace, Siniestros) | **Franja = fecha + bloque** (`MANANA` 8-12, `TARDE` 14-18). Cada trabajo pide una franja: Marketplace la fija al agendar la visita con la cotización (p.11 *"agendan visitas"*), Siniestros la fija el partner o, en urgencia, la primera libre; una suscripción reserva el mismo día de la semana + bloque en **todas las fechas del periodo** (A13). La agenda vive en **Proveedores** (agregado `AgendaTecnico`, uno por técnico verificado, con entidades `Reserva`; persona natural = 1 técnico). Un técnico solo es elegible si tiene libre la franja pedida (además de A12). **La reserva se confirma antes de asignar:** el canal publica `ProveedorSeleccionado` → Proveedores intenta reservar de forma atómica → `AgendaConfirmada` (GT asigna) o `AgendaRechazada` (la franja se ocupó mientras el cliente/partner elegía: el canal pide una lista nueva, que es la compensación de ese paso). Se libera por no-show, proveedor deshabilitado, cancelación o fin del periodo. Fuera de alcance: trabajos de varios días seguidos (un trabajo = una franja; hay 1 sub-trabajo por trabajo) |
| A15 | `POST /trabajos` de la Entrega 4 (crea y finaliza de una vez; lo usa `k6/esc-01.js`) (antes D4) | **Se conserva como atajo de carga**, apagado por defecto (`HABILITAR_ATAJO_CARGA=false`) y encendido solo en las corridas de k6, para que ESC-01 siga siendo **comparable** con sus corridas previas (`RESULTADOS-ESCALABILIDAD-GCP.md`). No es parte del journey ni de la máquina de estados. ESC-01 se mide además **dentro del journey** (JRN-02, §11) |
| A16 | Proveedores es un servicio con **4 módulos** (antes era, en la práctica, solo Verificación como servicio) | **Registro** (nuevo: agregado `Proveedor` persona natural/empresa, `Tecnico`, `Servicio`, `ZonaCobertura`; enunciado p.15 paso 1), **Verificación** (existe; se amplía a verificar **cada técnico** y, en empresas, la documentación de la empresa, p.15 pasos 2-3, y emite `ProveedorVerificado`), **Elegibilidad** (nuevo: habilitación por servicio y zona p.15 paso 4, filtro y orden A9/A10/A12, `ElegiblesPublicados`), **Agenda** (nuevo: agregado `AgendaTecnico`, reserva atómica, A14). Módulo = organización del código; el servicio mantiene varios procesos (api, worker de verificación con Pub/Sub de DISP-03, worker de Pulsar) sobre la misma BD |
| A17 | `Novedad`: ¿entidad del agregado Trabajo (vista de información) o agregado propio (código y vista de módulos)? | **Agregado propio del módulo Novedades** de GT, con referencia por ID al `Trabajo`. Así una ráfaga de novedades (DISP-02) no compite por el mismo agregado que el ciclo de vida. Se corrige la imagen de información |
| A18 | Pagos: **retener, liberar, compensar** (enunciado p.12 *"retenido hasta finalizar el trabajo"*; vista de contexto *"Pasarela: cobro y retención"*) | **Retener** al confirmarse la agenda (`AgendaConfirmada`): se cobra al dueño y queda retenido → `PagoRetenido` / `PagoRetencionFallida`. **Liberar** al finalizar (`TrabajoFinalizado`) → `PagoLiberado`. **Compensar** en disputa (`NovedadResuelta(DISPUTA)`) → devuelve lo retenido → `PagoCompensado`. Por origen: **Marketplace** retiene por trabajo; **Suscripción** retiene por cada ciclo; **Siniestro** no cobra al dueño: a la aseguradora la factura Siniestros·Facturación al cierre. Los dos módulos de la vista: *Liberación y Compensación* (retener/liberar/compensar + Strategy regional) y *Pasarelas* (Adapter Stripe/MercadoPago) |
| A19 | Suscripciones sin módulos en la vista (decía "pendiente") | Módulo **Ciclo de Suscripción**: contrato (`Suscripcion`), generación de ciclos (`CicloSuscripcion`), continuidad del proveedor (A13) y reserva recurrente de franja (A14) |
| A20 | Nombre de los recursos de Proveedores en GCP (`disp03-poc-*`, histórico) | Al rehacer el stack en la Entrega 5 el prefijo pasa a **`proveedores-poc`** (variable `entorno`), para no confundir el servicio con el experimento. DISP-03 sigue siendo el nombre del escenario |
| A21 | **Esquemas: JSON con Schema Registry de Pulsar** (`pulsar.schema.JsonSchema` + clases `Record`). Compatibilidad **BACKWARD** por namespace; un cambio que rompe = tópico nuevo `…v2`. Responde "¿Avro o Protobuf?": se eligió JSON con esquema por legibilidad en logs/video con las mismas garantías de registry y compatibilidad (justificar en el documento; Avro queda como ruta de mejora si el payload pesa en ESC-01) |
| A22 | **Saga orquestada**. Coordinador = módulo **Motor de Workflow** de Gestión de Trabajos. Envía **comandos** por Pulsar y recibe **eventos** de respuesta. **Saga Log** en la BD de GT (tabla append-only). Resuelve D1 |
| A23 | **Escenarios oficiales:** ESC-01 (escalabilidad), MOD-02 (modificabilidad), **DISP-02** (disponibilidad). DISP-03 sigue implementado dentro del journey (paso 0) y cuenta para "sin regresión" |
| A24 | **Todo en Pulsar**: la cola de Verificación deja Pub/Sub (`transporte="pulsar"` ya existe en `proveedores/app/common/config.py`; DLQ nativa en `pulsar_topology.py::construir_dead_letter_policy`). Se elimina `proveedores/infra/pubsub.tf` |
| A25 | **BFF REST** (FastAPI, OpenAPI en `/docs`), servicio nuevo `implementacion/bff/`, único punto de entrada para actores externos; llama síncrono a las APIs de los servicios. Son 9 servicios |
| A26 | **Topología descentralizada** (una BD por servicio, nadie lee la de otro), comparada con centralizada e híbrida en el documento. Almacenamiento: Postgres CRUD en todos, **Event Sourcing** en Reputación (existe) y en el Saga Log |
| A27 | **Alcance: todo lo decidido (A1-A20) es obligatorio**, incluidos agenda, sincronización con el partner, reputación compuesta, retención de pagos y los 3 caminos alternos |
| A28 | **Retrocompatibilidad de contratos, módulos y datos** (evolucionar sin romper a nadie) | Regla común: **solo se agrega, nunca se quita ni se renombra**. **Eventos y comandos (Pulsar):** Schema Registry con compatibilidad BACKWARD (solo campos nuevos con valor por defecto; los consumidores ignoran lo que no conocen); un cambio que rompe crea un tópico `…v2` que convive con el `…v1` hasta migrar al último consumidor. **APIs REST (BFF y servicios):** rutas `/v1`; dentro de `/v1` solo se agregan endpoints y campos opcionales; un cambio que rompe es `/v2` con el header `Deprecation`; el CI corre **oasdiff** y falla el PR si detecta un cambio que rompe. **Módulos de un servicio:** su interfaz pública (comandos, consultas y eventos de dominio de `application/`) se cambia en el mismo PR que sus usuarios; una **prueba de arquitectura** falla si un módulo importa el dominio o la infraestructura de otro. **Datos:** migraciones versionadas y *expand/contract* (primero se agrega, luego se migra el código, luego se quita). Detalle en §14 |

### 3.2 Alcance

| Tema | Decisión |
|---|---|
| Servicios **nuevos** | **Marketplace, Siniestros, Suscripciones, Scoring**: los 4 se implementan como microservicios reales (DDD + hexagonal + CQS + BD propia + Pulsar + Cloud Run) |
| Servicios **existentes que se completan** | **Gestión de Trabajos** (módulos + ciclo de vida), **Proveedores** (módulo Elegibilidad), **Pagos** (consumir/publicar eventos), **Reputación** (reaccionar a `TrabajoFinalizado`, publicar reputación, consumir scoring) |
| Estados del Trabajo | `SOLICITADO → ESPERANDO_ELEGIBLES → ASIGNADO → EN_CURSO → FINALIZADO → PAGADO`, más `EN_DISPUTA` y `CANCELADO` (sección 6). **Un solo sub-trabajo por trabajo** en esta entrega |
| Caminos alternos de `NovedadResuelta` | Se implementan **3**: *proveedor no-show → reasignar*, *disputa/garantía → Pagos·Compensar* y *sincronización con el partner* en trabajos de siniestro (A11). Quedan solo dibujados: *re-diagnóstico* y *cancelación* |
| Reputación | **Compuesta** (A10): calificaciones + cumplimiento + garantías, y alimenta el orden de elegibles |
| Despliegue | **Todo se despliega y se valida en GCP** (Cloud Run + Cloud SQL + Pulsar en VM), no solo en docker-compose |
| Fuera de alcance explícito | IA Asistida, Notificaciones/Gestor Documental/ERP reales (se usan mocks o puertos con adaptador de log), MOD-01/MOD-03/DISP-01/ESC-02/ESC-03 como experimentos medidos (sí aparecen en C&C) |

### 3.3 Decisiones abiertas

Ninguna. D1 (coreografía u orquestación) se cerró como A22 con la rúbrica de la Entrega 5.


### 3.4 Justificación de las decisiones de la Entrega 5 (base de la sustentación)

Formato de cada ficha: **problema de negocio → opciones evaluadas → decisión → atributo de calidad que
favorece → qué se sacrifica → cómo se demuestra (video o código)**. Las 7 fichas:

| Decisión | Por qué (negocio + atributo) | Qué se sacrifica | Descartadas y por qué |
|---|---|---|---|
| **A22 Orquestación y no coreografía** | La Saga del Trabajo es **larga y con pasos dependientes** (no se retiene el pago sin franja; no se libera sin trabajo terminado), con **3 compensaciones que cruzan servicios** (liberar franja, devolver lo retenido, cancelar) y **3 orígenes** con reglas distintas. El enunciado dice que **agentes humanos monitorean cada trabajo** (p.4 y p.14): un coordinador responde en un solo lugar *"¿en qué paso va y qué se compensó?"*, que es justo el Saga Log. GT ya es "Orquestación de flujos" en la vista de contexto. Favorece **modificabilidad del flujo** (un paso nuevo o un partner nuevo se agrega en el coordinador) y **disponibilidad** (plazos por paso con compensación automática) | GT concentra más responsabilidad (ya es SP1); se mitiga con réplicas, Saga Log persistente e idempotencia de comandos. Más acoplamiento al contrato de comandos | **Coreografía**: con 9 servicios y 3 compensaciones, el flujo quedaría repartido en reacciones implícitas; nadie sabe el estado global, se arriesga a ciclos de eventos, y el Saga Log habría que reconstruirlo desde afuera. Se conserva **coreografía** donde sí encaja: el fan-out de `TrabajoFinalizado` a Reputación, Scoring y Suscripciones (MOD-03: consumidores nuevos sin tocar el core) |
| **A22 Coordinador dentro de GT** | GT es dueño del agregado `Trabajo` y de su máquina de estados: el coordinador y el estado que coordina viven en el mismo contexto y la misma transacción local (Saga Log + estado del Trabajo se escriben juntos) | GT crece; se separa por módulo (`workflow`) para no mezclarlo con `ciclo_vida` | **Servicio coordinador aparte**: un servicio más sin dominio propio que tendría que consultar el estado del Trabajo a GT, sumando una llamada y un punto de falla |
| **A21 JSON con Schema Registry** | El 2,5/5 de la Entrega 4 fue por **no tener esquemas**, no por el formato. El Schema Registry de Pulsar da **contrato registrado, versiones y rechazo de cambios incompatibles** (BACKWARD) con JSON igual que con Avro. JSON mantiene los mensajes **legibles** en Cloud Logging, en `pulsar-admin` y en el video, y es el formato que ya usan y entienden los 3 servicios existentes (menos riesgo de repetir el fallo de la Entrega 4). Favorece **modificabilidad** (evolución controlada) | Mensajes más grandes y serialización más lenta que binario. Se cuantifica en ESC-01 (tamaño de mensaje en `mensaje_publicado.tamano_bytes`); hoy ~191 bytes por `TrabajoFinalizado`, despreciable frente a los ~380 ms medidos en la publicación | **Avro**: binario y compacto, pero ilegible sin herramientas, y en la Entrega 4 falló por dependencia (`fastavro`) y por desalineación de consumidores; se deja como ruta de mejora si ESC-01 mostrara que el tamaño pesa. **Protobuf**: requiere compilar `.proto` en cada servicio y el soporte nativo de Pulsar en Python es más limitado |
| **A21 Versionamiento** | Cambios **aditivos** (campo nuevo con default) no rompen: los acepta BACKWARD. Cambio que rompe → tópico `…v2` y ambos conviven hasta migrar consumidores (*Event Stream Versioning*). APIs REST versionadas en el BFF (`/v1`). Favorece **modificabilidad** con 9 equipos evolucionando por separado | Convivencia temporal de dos versiones de un tópico | Versionar solo en el cuerpo del mensaje sin registry: nadie lo hace cumplir |
| **A25 BFF REST** | Los 3 actores (dueño, proveedor, partner) y los agentes necesitan **una sola puerta** con capacidades de negocio, no 9 APIs. El BFF **oculta la topología interna**, traduce llamadas síncronas del cliente en comandos del sistema, propaga el `correlation_id` y permite cerrar los servicios internos al público. REST porque Postman, OpenAPI y el equipo ya lo usan. Favorece **modificabilidad** (los servicios cambian sin romper clientes) y **seguridad/operación** | Un salto de red más y un componente que debe escalar con el tráfico de entrada (sin estado, escala horizontal en Cloud Run) | **API Gateway genérico**: enruta, pero no compone capacidades por actor. **GraphQL**: flexible para componer, pero más trabajo y menos directo con Postman |
| **A24 Todo en Pulsar** | El enunciado pide Pulsar como broker y el profesor observó el doble broker. Pulsar da la **DLQ nativa** que DISP-03 necesita, así que no se pierde la táctica. Un solo broker = una sola forma de operar, monitorear y documentar (AsyncAPI) | Se pierde la comparabilidad exacta con la medición de DISP-03 en Pub/Sub (se re-mide dentro del journey) | Mantener Pub/Sub: dos tecnologías para lo mismo, sin beneficio de negocio |
| **A26 Topología descentralizada** | HdA sale de un **monolito con una BD compartida** que bloquea a los equipos (enunciado p.4). BD por servicio = cada contexto evoluciona, escala y se despliega solo (ESC-01 pico en Siniestros no satura a Pagos; MOD-03 servicios nuevos sin migrar datos). Favorece **escalabilidad y modificabilidad** | Consistencia eventual y sin joins entre servicios; se resuelve con la saga (consistencia por compensación) y eventos con carga de estado | **Centralizada**: la más simple (ACID, joins), pero repite el problema del monolito y concentra el pico en un solo punto. **Híbrida**: compartir BD entre algunos rompe los límites de los contextos acotados |
| **A26 CRUD o Event Sourcing** | **Event Sourcing** donde el historial es el valor de negocio: Reputación (auditar cómo llegó un proveedor a su puntaje) y Saga Log (reconstruir cada paso y compensación). **CRUD** donde importa el estado actual y la simplicidad (Trabajo, Proveedor, Pago, Solicitud, Siniestro, Suscripción, PerfilCrediticio). Motor: Postgres en todos (transacciones locales para el Saga Log + estado; Cloud SQL gestionado). Documental (Mongo) no aporta: los agregados son relacionales y pequeños | ES cuesta más en consultas (proyecciones); se usa solo donde vale | ES en todo: complejidad sin beneficio. Mongo: otra tecnología que operar sin ganancia |
| **A23 Escenarios** | Uno por atributo y **relevante para el negocio**: ESC-01 = pico 4x de siniestros por clima (70 % del volumen es B2B2C); MOD-02 = entrar a Brasil con su moneda y pasarela sin tocar Colombia (expansión global); DISP-02 = granizada con ráfaga de novedades contra el CRM de los 100 agentes. DISP-02 vive **dentro de la saga** (novedad → reasignación o compensación) | DISP-03 no es el oficial de disponibilidad | DISP-03: se mantiene implementado (paso 0) pero queda fuera del camino de la saga |
| **A28 Retrocompatibilidad** | HdA tiene **9 servicios que evolucionan por separado** y, con la expansión, crecerá el número de equipos y de partners que consumen las APIs (enunciado p.4: hoy los equipos se bloquean entre sí). Si un cambio de un servicio obligara a desplegar a todos a la vez, se repetiría el problema del monolito (despliegues de 3-4 horas). Con contratos retrocompatibles, cada servicio se despliega solo. Favorece **modificabilidad** (MOD-01/02/03: partners y países nuevos sin tocar el core) y **disponibilidad** (un despliegue no rompe a los consumidores que aún no migraron) | Convivencia temporal de dos versiones (tópicos `…v1` y `…v2`, rutas `/v1` y `/v2`) y campos que no se pueden borrar hasta migrar a todos; disciplina de expand/contract en las migraciones | **Versiones simultáneas obligatorias (big bang)**: despliegue coordinado de todos los servicios, con ventana de riesgo. **Solo convención sin chequeo**: nadie lo hace cumplir; por eso hay Schema Registry, oasdiff y prueba de arquitectura |

Los escenarios ya se probaron sueltos en las Entregas 3-4 (`implementacion/RESULTADOS-*.md`): la Entrega 5
los **vuelve a correr dentro de los journeys**, con los mismos umbrales, y compara contra esas corridas.

## 4. Servicios y responsabilidades

| Servicio (carpeta) | Estado | Módulos internos (vista de módulos) | Agregado(s) raíz (vista de información) | Escenario |
|---|---|---|---|---|
| `marketplace/` | **NUEVO** | Diagnóstico · Publicación y Cotización · Seedwork | `SolicitudTrabajo` (con `Diagnostico`, `Cotizacion`) | entrada del journey |
| `siniestros/` | **NUEVO** (reglas del partner: red permitida, monto máximo, aprobación de pasos y de novedades) | Orquestación de Partner · Facturación · Seedwork | `Partner` (Aseguradora/Banco/Comercio, `ReglaDeAprobacion`), `Siniestro` (`DatosPoliza`, `EvidenciaClimatica`), `Factura` | fuente del pico 4x (ESC-01) |
| `suscripciones/` | **NUEVO** (A19) | Ciclo de Suscripción · Seedwork | `Suscripcion` (`TipoServicioRecurrente`, `Frecuencia`, `EstadoSuscripcion`) | MOD-03 (nuevo consumidor, 0 cambios en el core) |
| `scoring/` | **NUEVO** | Cálculo de Score · Seedwork | `PerfilCrediticio` (`PuntajeCrediticio`) | consumidor de `TrabajoFinalizado` |
| `gestion-de-trabajos/` | se completa | **Ciclo de Vida** · **Motor de Workflow** (nuevo) · **Novedades** · **Integraciones Externas** (throttler CRM + circuit breaker Twilio/S3 + webhook de vuelta del CRM) · Seedwork | `Trabajo` (`SubTrabajo`, `EstadoTrabajo`, `Monto`, `Moneda`, `Ubicacion`, `Urgencia`, `Categoria`, franja) · `Novedad` (agregado propio, A17) | **ESC-01**, **DISP-02** |
| `proveedores/` | se completa (A16) | **Registro** (nuevo) · **Verificación** (existe, se amplía) · **Elegibilidad** (nuevo) · **Agenda** (nuevo) · Seedwork | `Proveedor` (`Verificacion`, `Tecnico`, `NivelVerificacion`, `ZonaCobertura`) · `AgendaTecnico` (`Reserva`, `Franja`) | **DISP-03** |
| `pagos/` | se completa (A18) | **Liberación y Compensación** (retener · liberar · compensar + Strategy regional) · **Pasarelas** (Adapter Stripe, MercadoPago) · Seedwork | `Pago` (`EstadoPago`: RETENIDO → LIBERADO / COMPENSADO / FALLIDO, `Dinero`, `Region`) | **MOD-02** |
| `reputacion/` | se completa (reputación compuesta, A10) | Calificación · Seedwork | `PerfilReputacion` (Event Sourcing, `Calificacion`, `Puntaje`, cumplimiento, garantías) | consumidor de `TrabajoFinalizado` |

Sistemas externos (simulados con mocks en `implementacion/mocks-*`): Verificación (Policía, RUES,
Certificadora), Pasarela (Stripe, MercadoPago), Gestión de Agentes (CRM), y, solo como puerto con
adaptador simple, Notificaciones, Gestor Documental y ERP Contable.

## 5. El journey

### 5.1 Flujo feliz

> **Con A22 (orquestación):** este flujo describe el **orden de negocio**. Cada paso que avanza la saga
> lo dispara el coordinador (GT·Motor de Workflow) con un **comando** (§7.1) y el servicio responde con un
> **evento**; donde aquí dice que un servicio "consume" un evento para avanzar (p. ej. Pagos y `AgendaConfirmada`),
> en la implementación es el comando `RetenerPago`. Se mantiene coreografía solo en el fan-out de `TrabajoFinalizado`.

```
 0  Proveedor ─API→ Proveedores·Registro (persona natural o empresa, técnicos, servicios, zonas)
    ─sync→ Elegibilidad ─sync→ Verificación (por técnico y, si es empresa, empresarial) ─(Policía/RUES/Certificadora:
    cola + reintento con backoff + DLQ + reproceso manual)─ async ProveedorVerificado → Elegibilidad
    → proveedor HABILITADO                                                                   [DISP-03]

 1  Dueño ─API→ Marketplace·Diagnóstico ─sync→ Publicación y Cotización
      ══ SolicitudDiagnosticada ══▶ GT·Ciclo de Vida: CrearTrabajo (SOLICITADO)
    (todo trabajo lleva la franja pedida o "primera libre" si es urgente — A14)
    (variantes: Siniestros ══ SiniestroAprobado ══▶ GT ;  Suscripciones ══ CicloSuscripcion ══▶ GT)

 2  GT ══ TrabajoCreado ══▶ Proveedores·Elegibilidad: filtra elegibles (nivel de verificación según
    origen, categoría, zona, disponibilidad — A12) y los ordena por reputación compuesta (A9, A10)
                                                           (GT pasa a ESPERANDO_ELEGIBLES)   [ESC-01]

 3  Proveedores ══ ElegiblesPublicados ══▶ el canal dueño del origen:
      • Marketplace·Publicación: publica el trabajo a los elegibles
      • Siniestros·Orquestación de Partner: aplica la red permitida / homologados y el monto máximo
      • Suscripciones·Ciclo: solo en el primer ciclo (los siguientes ya traen proveedor_id, A13)

 4  Selección (A9):
      • Marketplace: Proveedor ─API→ Cotizar ; Dueño ─API→ SeleccionarCotizacion
      • Siniestros:  Proveedor ─API→ Cotizar (si aplica) ; Partner ─API→ AprobarPaso(proveedor)
      • Suscripciones: Cliente ─API→ ElegirProveedor (primer ciclo)
      ══ ProveedorSeleccionado ══▶ Proveedores·Elegibilidad·Agenda: ReservarFranja (atómico, A14)
          ├─ libre   ══ AgendaConfirmada ══▶ GT·Ciclo de Vida: AsignarProveedor (ASIGNADO)
          │                              ├─▶ Pagos·Liberación: RetenerPago (origen mkt / suscripción, A18)
          │                              │     ══ PagoRetenido ══▶ GT  |  ══ PagoRetencionFallida ══▶ GT (CANCELADO + libera agenda)
          │                              └─▶ canal del origen · Reputación (asignaciones, A10)
          └─ ocupada ══ AgendaRechazada  ══▶ canal del origen: pide lista nueva (vuelve al paso 3)

 5  GT·Ciclo de Vida (con PagoRetenido, o directo si es siniestro) ─sync IniciarWorkflow(trabajoId)→
    Motor de Workflow (EN_CURSO)
    Proveedor ─API→ GT: CompletarSubTrabajo → Motor ─async SubTrabajosCompletos→ Ciclo de Vida:
    CerrarTrabajo (FINALIZADO)

 6  GT ══ TrabajoFinalizado ══▶ (una sola publicación, fan-out por suscripción)              [ESC-01]
      ├─▶ Reputación: habilita calificar ese trabajo
      ├─▶ Scoring: actualiza PerfilCrediticio ══ ScoringActualizado ══▶ Reputación
      ├─▶ Pagos (origen MARKETPLACE / SUSCRIPCION): LiberarPago (lo retenido pasa al proveedor)  [MOD-02]
      │     regla regional (Strategy: ReglaColombia / ReglaBrasil) + pasarela (Adapter: Stripe / MercadoPago)
      │     ══ PagoLiberado ══▶ GT (PAGADO)     ══ PagoFallido ══▶ GT (queda FINALIZADO, se registra novedad)
      ├─▶ Siniestros (origen SINIESTRO): FacturarAPartner → asiento contable (ERP, puerto)
      ├─▶ Proveedores: registra historial del proveedor
      └─▶ Suscripciones: registra el ciclo cumplido (MOD-03: consumidor nuevo sin tocar GT)

 7  Dueño ─API→ Reputación: CalificarProveedor (solo si el trabajo está FINALIZADO y no calificado)
      ══ ReputacionPublicada ══▶ Proveedores·Elegibilidad (el próximo ranking de elegibles la usa)
```

`══▶` = evento de integración por Pulsar (entre servicios). `─sync→` / `─async→` dentro de un servicio
= comunicación entre módulos (sección 8). `─API→` = comando HTTP de un actor vía API Gateway.

### 5.2 Camino alterno — Novedades (DISP-02)

```
 5a Cualquier cambio de estado del Trabajo o un reporte explícito (POST /trabajos/{id}/novedades)
    GT·Motor ─async EstadoTrabajoCambiado / NovedadRequiereSaaS→ GT·Novedades
    ─sync→ GT·Integraciones Externas ─«Throttler» (cola acotada + token bucket + Retry-After)→ CRM   [DISP-02]

 5b CRM ─webhook→ GT·Integraciones Externas ─async RespuestaExternaRecibida→ GT·Novedades/Motor
    resolución:
      • proveedor no-show → Ciclo de Vida: ReasignarProveedor (siguiente elegible; vuelve a ASIGNADO)   ✔ implementar
      • disputa/garantía  → GT pasa a EN_DISPUTA ══ NovedadResuelta(DISPUTA) ══▶ Pagos: Compensar (devuelve lo retenido)
                             ══ PagoCompensado ══▶ GT (CANCELADO)                                     ✔ implementar
      • re-diagnóstico → Marketplace·Re-cotizar                                                        solo diagrama
      • cancelación    → Ciclo de Vida: CerrarTrabajo(CANCELADO)                                       solo diagrama

 5c Si el trabajo es de origen SINIESTRO (A11), antes de aplicar cualquier resolución:
    GT ══ NovedadRegistrada ══▶ Siniestros·Orquestación de Partner: evalúa ReglaDeAprobacion
      • no requiere aprobación → ══ DecisionPartner(APROBADA) ══▶ GT aplica la resolución
      • requiere aprobación    → Partner ─API→ AprobarPaso / RechazarPaso
                                 ══ DecisionPartner(APROBADA | RECHAZADA) ══▶ GT                     ✔ implementar
    (GT también publica NovedadRegistrada para los otros orígenes; Siniestros solo procesa los suyos)

 5d Reputación consume NovedadResuelta(NO_SHOW | GARANTIA) para la reputación compuesta (A10)       ✔ implementar
```

### 5.3 Dónde queda cada escenario dentro del journey

| Escenario | Paso | Qué se demuestra ahora que antes no |
|---|---|---|
| **DISP-03** | 0 | La verificación es **precondición de negocio**: un proveedor en DLQ no aparece en `ElegiblesPublicados` hasta que se reprocesa |
| **ESC-01** | 1-2 y 6 | El pico 4x entra por Siniestros (canal real), y `TrabajoFinalizado` alimenta a **6 consumidores reales** con suscripción propia cada uno |
| **DISP-02** | 5a-5b | La novedad **nace del ciclo de vida del Trabajo**, y la respuesta del CRM **cambia el Trabajo** (reasignación) y **mueve dinero** (compensación) |
| **MOD-02** | 6 y 5b | La región y la moneda del pago salen del Trabajo (País), no del request; el pago lo dispara un evento, no un cliente HTTP |

## 6. Máquina de estados del Trabajo (GT · Ciclo de Vida)

| Desde | Evento / comando | Hacia | Publica |
|---|---|---|---|
| — | `SolicitudDiagnosticada` · `SiniestroAprobado` · `CicloSuscripcion` → `CrearTrabajo` | `SOLICITADO` | `TrabajoCreado` |
| `SOLICITADO` | `TrabajoCreado` publicado | `ESPERANDO_ELEGIBLES` | — |
| `ESPERANDO_ELEGIBLES` | `AgendaConfirmada` (tras la selección del canal, A9 + A14) → `AsignarProveedor` | `ASIGNADO` | — |
| `ESPERANDO_ELEGIBLES` | `AgendaRechazada` | `ESPERANDO_ELEGIBLES` (sin cambio; el canal re-selecciona) | — |
| `SOLICITADO` | `CicloSuscripcion` con `proveedor_id` (ciclos siguientes, A13; la franja ya quedó reservada para todo el periodo) → `AsignarProveedor` | `ASIGNADO` | `TrabajoCreado` |
| `ASIGNADO` | `PagoRetenido` (mkt/suscripción) o directo (siniestro) → `IniciarWorkflow` | `EN_CURSO` | — |
| `ASIGNADO` | `PagoRetencionFallida` | `CANCELADO` | — (Proveedores libera la franja al ver `CANCELADO` vía `NovedadResuelta`) |
| `ASIGNADO` / `EN_CURSO` | novedad no-show (y `DecisionPartner(APROBADA)` si es siniestro) → `SolicitarReasignacion` | `ESPERANDO_ELEGIBLES` | `TrabajoCreado` con `excluidos` · `NovedadResuelta(NO_SHOW)` |
| `EN_CURSO` | `SubTrabajosCompletos` → `CerrarTrabajo` | `FINALIZADO` | `TrabajoFinalizado` |
| `FINALIZADO` | `PagoLiberado` | `PAGADO` | — |
| `FINALIZADO` / `PAGADO` | novedad disputa | `EN_DISPUTA` | `NovedadResuelta(DISPUTA)` |
| `EN_DISPUTA` | `PagoCompensado` | `CANCELADO` | — |

Para trabajos de origen SINIESTRO, las transiciones que vienen de una novedad (reasignación, `EN_DISPUTA`) se aplican solo después de `DecisionPartner(APROBADA)` (A11); mientras tanto la `Novedad` queda en `PENDIENTE_PARTNER` y el Trabajo no cambia de estado.

Invariantes del agregado: no se asigna proveedor fuera de `ESPERANDO_ELEGIBLES`/reasignación; no se
cierra un trabajo sin proveedor asignado; `FINALIZADO` es irrepetible (ya existe hoy:
`trabajo.py` lanza error al finalizar dos veces). Toda transición inválida lanza excepción de dominio.

## 7. Catálogo de eventos de integración (contrato)

> **Con A22** la tabla de abajo lista los **eventos**. Los **comandos** de la saga están en §7.1, y el tipo de
> cada mensaje con su porqué en §7.2. Donde un evento figura como consumido por un servicio para avanzar la saga,
> en la implementación el coordinador envía el comando correspondiente.

Convenciones (detalle técnico en `CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md` §3):

- Tópico: `persistent://hda/<servicio-productor>/<evento>`; namespace = servicio dueño del evento.
- Suscripción: `<servicio-consumidor>-<evento>`, tipo **Shared**; cada consumidor tiene la suya (el
  lag de uno no frena a otro — ESC-01).
- Cuerpo: JSON plano (no Avro — ver `MENSAJERIA-Y-DATOS.md` §4). Metadatos en **propiedades** del
  mensaje Pulsar: `tipo_evento`, `version_esquema`, `content_type`, `productor` (ya existen) **más**
  `id_evento` (uuid, para idempotencia), `correlation_id` (= `trabajo_id` en todo el journey; en el
  paso 0, `proveedor_id`) y `causation_id` (`id_evento` que lo provocó).
- Todo consumidor es **idempotente por `id_evento`** (at-least-once de Pulsar).
- Cambios **aditivos** (campos nuevos) no suben `version_esquema`; cambios que rompen, sí, y conviven
  las dos versiones hasta que migren todos los consumidores.

| Evento | Tópico | Productor | Consumidores (suscripción) | Campos mínimos del cuerpo | Estado hoy |
|---|---|---|---|---|---|
| `SolicitudDiagnosticada` | `persistent://hda/marketplace/solicitud.diagnosticada` | Marketplace | GT (`gestion-trabajos-solicitud.diagnosticada`) | `solicitud_id, cliente_id, categoria, urgencia, ubicacion, region, descripcion` | nuevo |
| `SiniestroAprobado` | `persistent://hda/siniestros/siniestro.aprobado` | Siniestros | GT | `siniestro_id, partner_id, categoria, urgencia, ubicacion, region, monto_maximo, moneda` | nuevo |
| `CicloSuscripcion` | `persistent://hda/suscripciones/ciclo.suscripcion` | Suscripciones | GT | `suscripcion_id, cliente_id, tipo_servicio, ciclo, region, monto, moneda` | nuevo |
| `TrabajoCreado` | `persistent://hda/gestion-trabajos/trabajo.creado` | GT | Proveedores | `trabajo_id, origen, origen_id, partner_id?, categoria, ubicacion, region, nivel_verificacion_requerido, franja:{fecha, bloque} | primera_libre, excluidos?` | nuevo |
| `ElegiblesPublicados` | `persistent://hda/proveedores/elegibles.publicados` | Proveedores | Marketplace (origen MARKETPLACE), Siniestros (SINIESTRO), Suscripciones (SUSCRIPCION, primer ciclo) | `trabajo_id, origen, origen_id, excluidos:[proveedor_id], elegibles:[{proveedor_id, tecnico_id, franja_ofrecida:{fecha, bloque}, reputacion, nivel_verificacion}]` (ordenados) | nuevo |
| `ProveedorSeleccionado` | `persistent://hda/{marketplace,siniestros,suscripciones}/proveedor.seleccionado` (uno por canal) | Marketplace, Siniestros, Suscripciones | Proveedores (agenda, A14) | `trabajo_id, origen, origen_id, proveedor_id, tecnico_id, franja:{fecha, bloque} | recurrente:{dia_semana, bloque, vigente_hasta}, cotizacion_id?, monto, moneda` | nuevo |
| `AgendaConfirmada` · `AgendaRechazada` | `persistent://hda/proveedores/agenda.confirmada` · `.../agenda.rechazada` | Proveedores | Confirmada: GT, Pagos (retener, A18), canal del origen, Reputación · Rechazada: canal del origen | todos los campos de `ProveedorSeleccionado` + `reserva_id` (confirmada) o `motivo` (rechazada) | nuevo |
| `TrabajoFinalizado` | `persistent://hda/gestion-trabajos/trabajos.finalizado` | GT | Reputación, Scoring, Pagos, Siniestros, Proveedores (historial + disponibilidad), Suscripciones | `trabajo_id, proveedor_id, monto, moneda, region, ocurrido_en` (existen) **+ `origen`, `origen_id`** (aditivo) | **existe** (se mantiene el nombre plural para no romper la evidencia de ESC-01) |
| `NovedadRegistrada` | `persistent://hda/gestion-trabajos/novedad.registrada` | GT | Siniestros (solo origen SINIESTRO, A11) | `trabajo_id, novedad_id, origen, origen_id, partner_id?, tipo_novedad, impacto_monto?, descripcion` | nuevo |
| `DecisionPartner` | `persistent://hda/siniestros/decision.partner` | Siniestros | GT | `trabajo_id, novedad_id, partner_id, decision (APROBADA/RECHAZADA), regla_aplicada, automatica` | nuevo |
| `NovedadResuelta` | `persistent://hda/gestion-trabajos/novedad.resuelta` | GT | Pagos (`resolucion=DISPUTA`), Reputación (`NO_SHOW`, `GARANTIA`) | `trabajo_id, novedad_id, proveedor_id, resolucion, pago_id?` | nuevo |
| `PagoRetenido` · `PagoRetencionFallida` · `PagoLiberado` · `PagoFallido` · `PagoCompensado` | `persistent://hda/pagos/pago.retenido` · `.../pago.retencion-fallida` · `.../pago.liberado` · `.../pago.fallido` · `.../pago.compensado` | Pagos | GT | `pago_id, trabajo_id, monto, moneda, pasarela, regla_regional, motivo?` | eventos de dominio existen (`PagoMarcadoExitoso/Fallido`, `PagoCompensado`); **falta publicarlos** |
| `AgendaLiberada` | `persistent://hda/proveedores/agenda.liberada` | Proveedores | canal del origen (informativo) | `reserva_id, tecnico_id, franjas, motivo (NO_SHOW, DESHABILITADO, CANCELACION, FIN_PERIODO)` | nuevo |
| `ReputacionPublicada` | `persistent://hda/reputacion/reputacion.publicada` | Reputación | Proveedores | `proveedor_id, reputacion, promedio, total_calificaciones, tasa_cumplimiento, garantias_reclamadas` | nuevo |
| `ScoringActualizado` | `persistent://hda/scoring/scoring.actualizado` | Scoring | Reputación | `proveedor_id, puntaje_crediticio, trabajos_contados` | nuevo |
| `ProveedorHabilitado` | `persistent://hda/proveedores/proveedor.habilitado` | Proveedores | ninguno obligatorio (la habilitación se usa **dentro** de Proveedores vía el evento de dominio `ProveedorVerificado`) | ya definido | **existe** |

**Colas internas que NO son eventos de integración** (no cambian): la cola de solicitudes de
Verificación y su DLQ (Pub/Sub en GCP, `disp03-poc-verificacion-*`), y la cola en memoria del
Throttler hacia el CRM (DISP-02).

**Namespaces Pulsar a crear** (hoy existen `hda/gestion-trabajos`, `hda/proveedores`,
`hda/reputacion`): `hda/marketplace`, `hda/siniestros`, `hda/suscripciones`, `hda/pagos`,
`hda/scoring`. Ver `CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md` §4.

**Bug conocido que hay que corregir al implementar:** `proveedores/app/common/pulsar_topology.py`
define `TOPIC_TRABAJOS_FINALIZADO = "persistent://hda/trabajos/trabajos.finalizado"` pero GT publica
en `persistent://hda/gestion-trabajos/trabajos.finalizado` (ver `MENSAJERIA-Y-DATOS.md` §3).

### 7.1 Comandos de la Saga del Trabajo (A22)

Coordinador en GT·Motor de Workflow. Comandos en `persistent://hda/<servicio-destino>/comandos`, respuestas
como eventos en el namespace del servicio que responde. Servicios en la saga: GT, Proveedores, Pagos, y el canal
del origen (Marketplace, Siniestros o Suscripciones) → ≥ 4.

| Paso | Comando (GT → servicio) | Respuesta ok / falla | Compensación |
|---|---|---|---|
| 1 | local `CrearTrabajo` (desde `SolicitudDiagnosticada` / `SiniestroAprobado` / `CicloSuscripcion`) | saga `INICIADA` | — |
| 2 | Proveedores `PublicarElegibles` | `ElegiblesPublicados` → canal; canal publica `ProveedorSeleccionado` | — |
| 3 | Proveedores `ReservarFranja` | `AgendaConfirmada` / `AgendaRechazada` (vuelve a 2; catálogo §7) | `LiberarFranja` |
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

### 7.2 Tipo de cada mensaje y por qué (observación de la Entrega 4)

| Mensaje | Tipo | Por qué |
|---|---|---|
| `TrabajoFinalizado` | Evento de integración **con carga de estado** (trabajo, proveedor, monto, moneda, región, origen) | Lo consumen 6 servicios en el pico 4x (ESC-01): si fuera delgado, cada uno consultaría de vuelta a GT justo cuando está bajo presión |
| `SolicitudDiagnosticada`, `SiniestroAprobado`, `CicloSuscripcion` | Integración **con carga de estado** | GT crea el Trabajo sin llamar de vuelta al canal (el canal puede estar bajo el mismo pico) |
| `ElegiblesPublicados` | Integración **con carga de estado** (lista ordenada con franjas y reputación) | El canal presenta las opciones sin consultar a Proveedores por cada candidato |
| Comandos de la saga (`ReservarFranja`, `RetenerPago`, …) | **Comando** (punto a punto, un solo receptor) | Es una orden del coordinador con un dueño claro de ejecutarla; lleva `id_comando` para idempotencia |
| Respuestas (`AgendaConfirmada`, `AgendaRechazada`, `PagoRetenido`, `PagoRetencionFallida`, …) | Evento de integración **delgado** (ids + resultado + motivo) | El coordinador ya tiene el estado de la saga; solo necesita el resultado del paso |
| `ReputacionPublicada`, `ScoringActualizado`, `DecisionPartner` | Integración **delgado** | Actualizan una proyección del consumidor; no hace falta más estado |
| `IntentoRegistrado`, `ProveedorVerificado`, `EstadoTrabajoCambiado`, `SubTrabajosCompletos`, `PagoConfirmado`, `SiniestroAprobado` (intra) | Evento **de dominio** | Comunicación entre módulos dentro de un servicio (§8); nunca sale a Pulsar |

### 7.3 Esquemas y versionamiento (A21)

Todos los tópicos tienen esquema registrado en el **Schema Registry de Pulsar** (`JsonSchema` + clases `Record`
en `infrastructure/messaging/esquemas.py` de cada servicio). Política **BACKWARD** por namespace: se aceptan
campos nuevos con valor por defecto; un cambio que rompe crea un tópico `…v2` que convive con el anterior hasta
migrar los consumidores. Los eventos que hoy salen como JSON sin esquema (`trabajos.finalizado`,
`proveedor.habilitado`) pasan a tener esquema. El contrato ejecutable se documenta en `asyncapi/hda-asyncapi.yaml`.
Las APIs REST del BFF y de cada servicio se versionan por ruta (`/v1`); reglas completas de retrocompatibilidad en §14.

## 8. Comunicación entre módulos (dentro de un servicio)

Es lo que la vista de módulos dibuja con flechas `sync` y `async` entre las capas Aplicación/Dominio
de módulos hermanos. Reglas para todos los servicios:

1. **Síncrona** = un módulo invoca un **comando o consulta de la capa `application/` del otro
   módulo** (su interfaz pública). Nunca importa el `domain/` ni la `infrastructure/` del otro.
   Ejemplos: GT·Ciclo de Vida → `IniciarWorkflow(trabajoId)` del Motor; Proveedores·Elegibilidad →
   `SolicitarVerificacion` de Verificación; Pagos·Liberación → puerto `PasarelaDePago` de Pasarelas.
2. **Asíncrona** = un módulo emite un **evento de dominio** y el otro lo recibe por el dispatcher en
   memoria del servicio (`application/dispatcher_eventos_dominio.py`, patrón que ya usan GT, Pagos y
   Proveedores). Nunca cruza Pulsar. Ejemplos: `ProveedorVerificado` (Verificación → Elegibilidad),
   `EstadoTrabajoCambiado` / `NovedadRequiereSaaS` (Motor → Novedades), `RespuestaExternaRecibida`
   (Integraciones Externas → Motor), `SubTrabajosCompletos` (Motor → Ciclo de Vida),
   `SiniestroAprobado` (Orquestación de Partner → Facturación, dentro de Siniestros).
3. Un evento de **dominio** solo se traduce a evento de **integración** (Pulsar) en la capa de
   aplicación, después de persistir el agregado — como ya hace `gestion-de-trabajos` con
   `TrabajoFinalizado`. En los logs se distinguen por `tipo_mensaje`.
4. **Seedwork** es un módulo compartido **dentro de cada servicio** (copia propia por servicio, igual
   que hoy): no hay librería común entre servicios.

## 9. Trazabilidad del journey

Un mismo `correlation_id` (= `trabajo_id`) viaja en las propiedades Pulsar, en el header HTTP
`X-Correlation-Id` y en cada línea de log (`jsonPayload.correlation_id`). Con una sola query en Logs
Explorer (`jsonPayload.correlation_id="<trabajo_id>"`) se debe ver el journey completo a través de los
8 servicios. [PENDIENTE-RÚBRICA: si se exige, panel de Grafana "Journey".]

## 10. Qué cambia en los documentos anteriores

| Documento | Qué queda invalidado |
|---|---|
| `historico/12-plan-entrega-4.md` §0.1, §1, §3.1, §4 | "Pagos es externo / módulo ACL dentro de GT / sin tópico propio" |
| `historico/13-guia-entrega-4-pasos.md` | referencias a Pagos como ACL interno de GT |
| `historico/11-implementacion-ddd-verificacion.md` §7 | el tercer adaptador Kafka nunca se construyó; el bus es Pulsar |
| `05-vista-modulo.puml`, `06-vista-cyc.puml`, `04-vista-contexto.puml`, `07-vista-informacion.puml` (versiones anteriores al 2026-09-21) | reescritas; lo anterior queda en el historial de git |
| `03-contextos-acotados-TO-BE.cml` | `ContextoPagos` deja de estar entre los "sistemas genéricos externos" |
| `historico/README-entrega-1.md` (antes `contexto/README.md`) | la decisión "Pagos no tiene contexto propio en el TO-BE" fue revisada en Entrega 5 |

## 11. Escenarios del journey (cómo se prueba la Entrega 5)

Los 4 escenarios de calidad se probaron **sueltos**, cada uno contra una parte del sistema. Aquí se
prueban **dentro del journey**: el mismo estímulo, pero entrando por el canal real y siguiendo el trabajo
hasta el final. Reglas:

- Cada JRN **hereda sin cambios las medidas de su escenario** en `escenarios_calidad.md` (Regla 3: no se
  baja ningún umbral) y **agrega medidas de journey**, que solo se pueden observar con los servicios conectados.
- Se corren en **GCP**, con los mocks de externos inyectando la falla (`POST /_control/config`), carga con k6
  y el journey con Newman (carpeta "Journey E5"). Se miden con Logs Explorer por `correlation_id` y con Grafana.
- `experimento-runner` produce datos crudos; `validador-hipotesis` da el veredicto. Formato final de cada
  experimento (H1/H0, casos de prueba, criterios): **[PENDIENTE-RÚBRICA]**.

| ID | Journey y estímulo | Escenario base (medidas heredadas) | Medidas nuevas de journey |
|---|---|---|---|
| **JRN-01** | **Marketplace de punta a punta con la certificadora caída.** Un proveedor se registra con la certificadora `caido`; el dueño pide un trabajo de su categoría y zona | **DISP-03**: disponibilidad del proceso de verificación ≥ 99,9 %; 100 % de las verificaciones fallidas trazables en la DLQ y reprocesables en < 24 h | (a) 0 trabajos asignados a un proveedor con verificación pendiente o en DLQ (no aparece en `ElegiblesPublicados`); (b) tras el reproceso, ese proveedor aparece en la siguiente lista; (c) el trabajo llega a `PAGADO` y queda calificable; (d) 100 % del journey visible con un solo `correlation_id` |
| **JRN-02** | **Pico 4x de siniestros por granizada.** k6 envía 4x el volumen de `SiniestroAprobado` por la API de Siniestros (SP6), mientras Marketplace recibe su carga normal | **ESC-01**: aceptación < 2 s en pico; ≥ 99,9 % aceptadas; < 5 % de variación en la latencia de aceptación de Marketplace; por cada consumidor de `trabajos.finalizado`: lag ≤ 120 s, backlog drenado ≤ 15 min, p95 de procesamiento < 2 s (p99 < 5 s), 0 % de mensajes perdidos | (a) Aplica a los **6** consumidores de `trabajos.finalizado`, no solo a 2; (b) 0 trabajos sin elegibles durante el pico (A12: nunca lista vacía); (c) 0 dobles reservas de la misma franja de un técnico (A14); (d) línea base comparable: la misma corrida con el atajo `POST /trabajos` (A15) |
| **JRN-03** | **Novedades en ráfaga con el CRM limitado.** Durante JRN-02, los proveedores reportan novedades en ráfaga (incluye no-shows) y el CRM (`mocks-crm`) limita la tasa | **DISP-02**: ≥ 99,9 % de trabajos sin pérdida por rate limiting; ≥ 99 % de webhooks entregados en < 15 min y 100 % en < 1 h; disponibilidad de GT ≥ 99,9 % independiente del CRM | (a) 100 % de los no-shows terminan reasignados a otro proveedor elegible con franja libre; (b) en trabajos de siniestro, 0 resoluciones aplicadas sin `DecisionPartner(APROBADA)` (A11); (c) la reputación del proveedor que falló baja (A10) |
| **JRN-04** | **Pago en Brasil y disputa.** Un trabajo de región BR finaliza, se paga, y luego el dueño abre una disputa de garantía | **MOD-02**: la regla de Brasil y MercadoPago se agregan sin modificar Colombia, Stripe ni el core (0 regresiones en la suite) | (a) Región y moneda del pago tomadas del Trabajo, no del request; (b) `PagoRetenido` al confirmar la agenda y `PagoLiberado` → `PAGADO` al finalizar; (c) disputa → `PagoCompensado` → `CANCELADO`; (d) monto compensado = monto retenido, y los estados de GT y Pagos coinciden al final (saga consistente) |
| **JRN-05** | **Suscripción mensual.** Un cliente contrata aseo los lunes en la mañana por un mes; otro cliente pide la misma franja | **MOD-03**: el dominio nuevo se integra sin PRs sobre los productores existentes | (a) Suscripciones consume `trabajos.finalizado` con **0 cambios** en GT (diff vacío en `gestion-de-trabajos/`); (b) mismo proveedor en todos los ciclos del mes (A13); (c) ese proveedor no aparece para la franja ocupada en ningún canal (A14) |

Estos escenarios salen de las decisiones A9-A15. Si una medida no se puede sostener, se reporta como
hallazgo: no se ajusta el umbral para que pase.

### 11.1 Escenarios por journey, con estímulo y evidencia en GCP

Cada JRN hereda los umbrales de su escenario (`escenarios_calidad.md`) y suma medidas de journey
(15-…md §11). Los 3 oficiales son JRN-02, JRN-03 y JRN-04; JRN-01 y JRN-05 prueban DISP-03 y MOD-03 (sin regresión).

| JRN | Escenario | Estímulo (cómo se inyecta) | Medidas (umbral heredado + journey) | Evidencia en GCP |
|---|---|---|---|---|
| JRN-01 | DISP-03 | Certificadora `caido` (`POST /_control/config` del mock) mientras un proveedor se registra por el BFF; luego reproceso de la DLQ | Verificación ≥ 99,9 % disponible; 100 % de fallidas trazables en DLQ y reprocesables < 24 h; 0 trabajos asignados a proveedores no verificados; saga `COMPLETADA` | Query por `proveedor_id` (intentos, DLQ, reproceso) + query por `correlation_id` del trabajo |
| JRN-02 | **ESC-01** | k6 con 4x de siniestros por el BFF (API de Siniestros, SP6) + Marketplace con carga normal; línea base con el atajo (A15) | Aceptación p95 < 2 s; ≥ 99,9 % aceptadas; < 5 % de variación en Marketplace; por consumidor de `trabajos.finalizado`: lag ≤ 120 s, drenado ≤ 15 min, p95 < 2 s, 0 perdidos; 0 trabajos sin elegibles; 0 dobles reservas | Grafana: p95 / req/s por servicio, backlog por suscripción de Pulsar, sagas por minuto y duración por paso (Saga Log) |
| JRN-03 | **DISP-02** | Durante JRN-02, ráfaga de novedades (incluye no-shows) con `mocks-crm` limitando la tasa | ≥ 99,9 % sin pérdida; ≥ 99 % webhooks < 15 min y 100 % < 1 h; GT ≥ 99,9 % disponible; 100 % de no-shows reasignados; 0 resoluciones de siniestro sin `DecisionPartner(APROBADA)` | Query de novedades por estado (PENDIENTE/ENTREGADA/AGOTADA) y 429 del CRM; Saga Log con la rama de reasignación |
| JRN-04 | **MOD-02** | Trabajo en región BR pagado con MercadoPago; luego disputa | 0 cambios en Colombia/Stripe/core (diff + suite); región y moneda tomadas del Trabajo; retenido = liberado = compensado; estados de GT y Pagos iguales | Query de Pagos con `patron=Strategy/Adapter`; Saga Log `COMPENSADA` |
| JRN-05 | MOD-03 | Suscripción mensual (lunes mañana) y otro cliente pidiendo la misma franja | 0 cambios en GT para el consumidor nuevo; mismo proveedor todo el mes; franja rechazada para el segundo cliente | Query por `suscripcion_id`; `AgendaRechazada` en el Saga Log |
| — | Saga (ítems 2 y 3) | Pasarela en modo falla durante un JRN-01 | Saga `COMPENSADA` con `LiberarFranja` y Trabajo `CANCELADO` | `consultas-saga-log.sql` en Cloud SQL (cliente psql/DBeaver) y panel del Saga Log en Grafana |

### 11.2 La saga y el Saga Log en los 5 journeys

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

## 12. Respuesta a las observaciones de la Entrega 4 (`ACLARACIONES-entrega-5.md`)

| # | Observación | Respuesta | Dónde |
|---|---|---|---|
| 1 | Evento de integración o con carga de estado | Tipo y porqué de cada mensaje | §7.2 |
| 2 | Versionamiento de esquemas o de APIs ("no esquemas", 2,5/5) | Schema Registry de Pulsar, BACKWARD, tópicos `…v2`; BFF `/v1` | A21, §3.4, §7.3, `asyncapi/` |
| 3 | Descentralizado, híbrido o centralizado; cada micro con su BD ("no conocemos las topologías", 2,9/5) | Descentralizada, comparada con las otras dos | A26, §3.4 |
| 4 | Patrón de almacenamiento por micro (relacional/documental, CRUD/ES) | Postgres en todos; ES en Reputación y Saga Log; CRUD en el resto | A26, §3.4 |
| 5 | Sagas: coreografía u orquestación | Orquestación en GT·Motor de Workflow, coreografía solo en el fan-out | A22, §3.4, §7.1 |
| 6 | BFF como base del API y uno de los servicios | Servicio `bff/` REST | A25, §3.4 |
| 7 | Pub/Sub solo en DISP-03 | Todo en Pulsar | A24 |
| 8 | Comunicación entre módulos y microservicios, y dónde está en el código | §8 (entre módulos), §7 (entre servicios); campo `tipo_comunicacion` en cada log | §8, §13 |
| 9 | Qué es síncrono y qué asíncrono | Síncrono: cliente → BFF → API del servicio (REST), módulo → aplicación del otro módulo, servicio → externo. Asíncrono: comandos y eventos por Pulsar, eventos de dominio por el dispatcher | §8, §7 |

## 13. Observabilidad en GCP: ver cada servicio y el detalle de punta a punta

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

## 14. Contratos, documentación y retrocompatibilidad (síncrono, asíncrono, módulos y datos)

Un contrato por cada frontera, documentado **y** protegido por una prueba o chequeo automático:

| Frontera | Documentación | Versionamiento | Regla de retrocompatibilidad | Cómo se hace cumplir |
|---|---|---|---|---|
| **Asíncrono entre servicios** (comandos y eventos en Pulsar) | **AsyncAPI** (`asyncapi/hda-asyncapi.yaml`): cada canal con productor, consumidores, esquema, tipo (comando / integración con carga de estado / delgado) y versión; HTML generado (`asyncapi/html/`) enlazado desde el documento | Schema Registry de Pulsar; `version_esquema` en las propiedades; cambio que rompe → tópico `…v2` | **BACKWARD**: solo campos nuevos con valor por defecto; no se borra ni renombra un campo ni se cambia su tipo; los consumidores ignoran campos desconocidos (*tolerant reader*); `…v1` y `…v2` conviven hasta que migre el último consumidor | Pulsar rechaza el esquema incompatible; pruebas de contrato contra AsyncAPI (§9 de CONVENCIONES); en el video, un cambio incompatible rechazado |
| **Síncrono: BFF** (actores → sistema) | **OpenAPI/Swagger** en `<bff>/docs` y `openapi.json` exportado a `bff/openapi/` en el repo; colección Postman generada a partir de él | Ruta `/v1/…`; una versión nueva `/v2` convive con la anterior y se anuncia la deprecación con el header `Deprecation` | Dentro de `/v1`: solo se agregan endpoints, campos opcionales de entrada y campos de salida; nunca se quita un campo ni se cambia un código de respuesta | CI con **oasdiff** (`oasdiff breaking`) que compara el `openapi.json` del PR contra `main` y **falla si hay un cambio que rompe** |
| **Síncrono: API de cada servicio** (BFF → servicio) | OpenAPI en `<servicio>/docs` y `openapi.json` exportado a `<servicio>/openapi/`; URLs en `ESTADO-IMPLEMENTACION.md` | Ruta `/v1/…` en todos los servicios (los endpoints actuales sin prefijo se mantienen como alias hasta migrar la colección de la Entrega 4) | Las mismas del BFF | El mismo chequeo oasdiff por servicio; el BFF tiene pruebas de contrato contra el `openapi.json` de cada servicio que consume |
| **Entre módulos del mismo servicio** | Interfaz pública del módulo = sus **comandos, consultas y eventos de dominio** en `application/` (DTOs); documentada en el README del servicio con un diagrama de módulos | No se versiona: se cambia en el mismo PR que sus usuarios (mismo servicio, mismo despliegue) | Ningún módulo importa `domain/` ni `infrastructure/` de otro; si una firma cambia, se actualizan todos sus usuarios en el mismo PR | Prueba de arquitectura por servicio (`tests/unit/test_arquitectura.py`) que revisa los imports prohibidos entre módulos y del dominio hacia afuera |
| **Datos** (BD por servicio) | **Topología descentralizada** justificada frente a centralizada e híbrida (A26, §3.4) y **modelo de datos por servicio** (tablas o event store, qué agregado guarda cada una, CRUD o ES y por qué) en el documento | Migraciones versionadas por servicio (`alembic`, o scripts `sql/NNN_*.sql` si el servicio no usa alembic) | Migraciones **expand/contract**: primero se agrega la columna o tabla nueva, se migra el código y después se quita la vieja; nunca un cambio destructivo en la misma versión | La suite de integración corre las migraciones desde cero contra el Postgres del compose |

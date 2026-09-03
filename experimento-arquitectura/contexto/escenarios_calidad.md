# Escenarios de Calidad — Hogar de los Alpes

## Escalabilidad · Prioridad: H

| Campo | ESC-01 | ESC-02 | ESC-03 |
|---|---|---|---|
| **Fuente** | Evento climático estacional | Partner B2B2C recién integrado (aseguradora/banco) | Negocio / Crecimiento orgánico sostenido por expansión LATAM |
| **Estímulo** | Pico de hasta 4x en el volumen de siniestros en 48h; +25M requests/día en crecimiento hacia 100M+ | Incremento súbito de llamadas concurrentes a la API tras el onboarding o una campaña comercial (hasta 5x el tráfico habitual de un solo partner) | El volumen total de la plataforma crece de ~12.000 a 36.000 trabajos/día (×3) y de +45.000 a +100.000 proveedores registrados en 3 años, por la entrada simultánea a México, Brasil y Argentina |
| **Artefacto** | Servicio de Gestión de Trabajos + colas de eventos | API Gateway / BFF de recepción de canales | Bus de Eventos particionado (configuración de infraestructura del despliegue, transversal a los 7 contextos core — ver SP5 en Vista de Módulos) + Servicios stateless con auto-scaling + Bases de datos por microservicio |
| **Ambiente** | Operación normal / pico estacional | Producción, fase de crecimiento de integraciones B2B2C (camino a 100M+ requests) | Producción, crecimiento sostenido durante 3 años (no un pico puntual) |
| **Respuesta** | El sistema procesa de forma asíncrona sin bloquear escritura en BD ni afectar otros dominios | El Gateway aplica rate limiting por partner y las réplicas stateless de los servicios de ingesta escalan automáticamente (auto-scaling) sin afectar a otros partners | El sistema absorbe el crecimiento agregado añadiendo réplicas y particiones de forma horizontal, sin cambios estructurales al diseño de dominios ni migración de datos |
| **Medida de la respuesta** | Latencia de aceptación < 2s en pico; ≥ 99.9% de solicitudes aceptadas en pico; < 5% de variación en latencia de los demás dominios durante el pico | Auto-escalamiento activo en < 60s; p95 de latencia < 300ms incluso con 5x de tráfico de un solo partner; 0% de rate limiting aplicado a partners no involucrados en el pico; < 5% de variación en p95 de otros partners | El sistema sostiene 36.000 trabajos/día y +100.000 proveedores manteniendo el mismo SLA de latencia (p95 < 300ms) que hoy con 12.000 trabajos/día |

---

## Modificabilidad · Prioridad: H

| Campo | MOD-01 | MOD-02 | MOD-03 |
|---|---|---|---|
| **Fuente** | Equipo de ingeniería / negocio | Equipo de producto / legal | Equipo de arquitectura / negocio |
| **Estímulo** | Alta/onboarding de un nuevo partner (aseguradora/banco/comercio) o apertura de un nuevo país | Se requiere adaptar reglas fiscales, de moneda y regulatorias para el lanzamiento en Brasil (2027) sin afectar México ni Argentina | Se necesita lanzar un nuevo dominio de negocio (ej. Fintech/Suscripciones/Agentes IA) que consume eventos existentes sin afectar los 8 dominios actuales |
| **Artefacto** | Siniestros y Partners (Reglas y SLA por partner) — componente marcado como punto de sensibilidad en la Vista de Contexto (HDA-001); en la Vista de Información corresponde al ObjetoValor `ReglaDeAprobación` dentro del agregado `Partner` | Módulo de reglas regionales (patrón Strategy) dentro de Gestión de Trabajos; para el componente de moneda/pasarela específicamente, el patrón Adapter en Pasarelas (submódulo de Pagos — ver TP3 en Vista de Módulos: Stripe → MercadoPago sin tocar Liberación y Compensación) | Bus de Eventos + Arquitectura Hexagonal por contexto acotado |
| **Ambiente** | Tiempo de desarrollo | Tiempo de diseño/desarrollo, previo al lanzamiento regional | Tiempo de diseño, fase de extensión de la plataforma |
| **Respuesta** | Se integra vía configuración/adaptador nuevo sin modificar el core de Gestión de Trabajos ni el de otros dominios | *(Prerrequisito de modelo, una sola vez)* Se extiende el ObjetoValor `Monto` con un atributo `Moneda` (y `Partner`/`Trabajo` con `Pais`) en la Vista de Información — hoy el modelo no distingue moneda ni país. Una vez hecha esa extensión, un desarrollador agrega el nuevo conjunto de reglas del país mediante configuración/estrategia, sin recompilar ni redesplegar los demás países ni el core | El nuevo contexto acotado se suscribe a los eventos publicados por el core sin requerir cambios en los productores existentes, gracias al desacoplamiento Pub/Sub |
| **Medida de la respuesta** | Onboarding completo en < 5 días-persona; 0 líneas de código modificadas en el core; 0 regresiones detectadas por la suite automatizada (gate de release) | Extensión de modelo (`Moneda`/`Pais`) completada una única vez, antes del primer país adicional; a partir de ahí, cambio implementado y desplegado en < 5 días-persona; 0 regresiones detectadas por la suite automatizada (gate de release); 0 pipelines de CI/CD disparados para módulos de otros países o del core | Nuevo dominio integrado y desplegado en < 1 sprint (2 semanas); 0 pull requests sobre el código de los 8 dominios existentes |

> **Nota de alcance (MOD-01/02/03):** las medidas de "0 líneas/0 PRs/0 redespliegues" aplican al caso general descrito en cada escenario — partners y dominios que encajan en los patrones ya establecidos (ACL para partners, Strategy para reglas regionales, Pub/Sub para nuevos dominios). No son una garantía absoluta ante un partner o dominio futuro con un modelo de negocio fundamentalmente incompatible con el core actual, caso en el que sí sería esperable tocar el dominio central.

---

## Disponibilidad · Prioridad: H

| Campo | DISP-01 | DISP-02 | DISP-03 |
|---|---|---|---|
| **Fuente** | SaaS externo (pasarela de pagos, entidad certificadora) | Pico estacional de granizada (evento climático) | Entidades certificadoras externas (ej. CONTE) durante la verificación de proveedores — hoy con tiempo de respuesta de 24-48h según el enunciado (a diferencia de Policía Nacional y Cámara de Comercio/RUES, que responden en línea) |
| **Estímulo** | Caída o timeout de un sistema externo | El submódulo Novedades (dentro de Gestión de Trabajos) intenta publicar miles de webhooks/segundo hacia Gestión de Agentes (CRM SaaS externo), que impone rate limiting y podría tumbar la integración — ver SP2 en Vista de Módulos | Un sistema externo de verificación no responde o falla durante el registro, aprobación por servicio/zona o re-validación de un proveedor |
| **Artefacto** | Orquestador de Gestión de Trabajos | Sidecar / Embajador (Ambassador) de salida desde Novedades hacia Gestión de Agentes (CRM SaaS) | Verificación (submódulo de Proveedores — ver nota en Vista de Módulos: "hoy la ejecutan agentes humanos... candidato a IA") + Bus de Eventos / Dead Letter Queue |
| **Ambiente** | Operación 24/7 | Operación en pico estacional (4x) | Operación 24/7, fase de verificación/re-validación de proveedores |
| **Respuesta** | El core sigue aceptando y orquestando trabajos con consistencia eventual hasta que el externo se recupere | El Sidecar dosifica (throttling) el envío de webhooks respetando el límite del proveedor y encola el excedente para reintento, sin bloquear el hilo principal de Gestión de Trabajos | La verificación pendiente queda en espera sin bloquear al resto de la cola; tras agotar reintentos, el evento se enruta a la DLQ para revisión manual, sin detener la coreografía global |
| **Medida de la respuesta** | Disponibilidad del core ≥ 99.9% aun con el externo caído; ≥ 99.99% de los trabajos afectados se reconcilian automáticamente al restablecerse el servicio, sin pérdida de datos | ≥ 99.9% de trabajos sin pérdida por rate limiting (dentro de capacidad configurada de la cola); ≥ 99% de los webhooks entregados en < 15 min, 100% en < 1h; disponibilidad de Gestión de Trabajos ≥ 99.9% independiente del estado de Gestión de Agentes | Disponibilidad del proceso de verificación ≥ 99.9%; 100% de las verificaciones fallidas quedan trazables en la DLQ y reprocesables en < 24h |

*Todos los escenarios corresponden a la Versión 1.0.*

> **Pendientes en tus diagramas (tú los ajustas del lado del diseño):**
> 1. DISP-03 depende de "Verificación" (Policía, RUES, certificadoras), pero esa caja no está marcada con el ícono de Punto de Sensibilidad (!) en tu Vista de Contexto (HDA-001).
> 2. "Operación de Agentes" (Vista de Contexto, interna) vs. "Gestión de Agentes" (Vista de Módulos y C&C, externa/SaaS) — dos nombres y clasificaciones distintas para el mismo componente; unifica con el de Módulos/C&C, que es más específico.
> 3. **MOD-02**: el modelo de información no tiene hoy ningún ObjetoValor de `Moneda` ni `Pais` — lo estás agregando tú; en cuanto quede reflejado en el diagrama, quito la nota de "prerrequisito de modelo" que dejé en MOD-02 y el escenario vuelve a ser 100% configuración pura.
> 4. **MOD-03**: la Vista de Módulos marca "Suscripciones" como *"pendiente... estructura interna no definida"*, pero la Vista de Información ya tiene el agregado completo (`Suscripción`, `TipoServicioRecurrente`, `Frecuencia`, `EstadoSuscripción`) — vale la pena que ambos diagramas digan lo mismo sobre qué tan avanzado está este dominio.
> 5. **DISP-03**: pendiente en la Vista de Componentes y Conectores (C&C) — actualmente no respalda el escenario. Falta:
>    - El sistema externo de verificación (Policía Nacional, RUES, entidades certificadoras) representado en su propia caja de "Contexto Externo".
>    - El DLQ (o el mecanismo de reintento que elijas) conectado al contexto de Proveedores/Verificación, no solo al de Gestión de Trabajos.
>    - Que todo quede coherente con lo que ya dice DISP-03 en este markdown — o si cambias el nombre de algún componente, lo ajusto para que el escenario hable el mismo idioma que el diagrama.
> 6. **MOD-02**: pendiente en la Vista de Información — agregar `Moneda` (y quizás `Pais`) al modelo antes de la entrega final, para que MOD-02 quede completamente respaldado como cambio 100% de configuración. Mientras tanto, el escenario en este markdown deja explícito el prerrequisito de extender `Monto` con `Moneda`.

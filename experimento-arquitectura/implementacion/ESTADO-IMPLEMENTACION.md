# Estado real de la implementación

**Para quién:** cualquier persona o asistente de IA que vaya a **desplegar, probar o seguir
construyendo**. Este archivo dice **qué existe de verdad hoy**. El diseño objetivo (lo que se va a
construir en la Entrega 5) está en [`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md).
Si los dos no coinciden, no es un error: el diseño va adelante de la implementación.

- **Para desplegar**, manda este archivo: despliega solo lo marcado como desplegable, con la receta marcada como probada.
- **Para construir**, manda el diseño (15-…md) más [`CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md).
- **Regla:** todo PR que implemente, despliegue o destruya algo **actualiza este archivo en el mismo PR**
  (fila del servicio + "Última verificación").

**Última verificación: 2026-09-21** (rama `feature/entrega-5-journey-saga`; cambios de infra respecto a `main`: backend GCS en los 9 stacks, namespaces automáticos en la VM de Pulsar, `scripts/`, CI ampliado).

## 1. Qué hay desplegado en GCP ahora mismo

**Nada.** Verificado el 2026-09-21 en el proyecto `hogaralpes`: 0 servicios de Cloud Run y 0 VMs, y los
states locales de Terraform de los 8 stacks tienen 0 recursos. Todo se destruyó después de la última demo.

Desde el 2026-09-21 el state de Terraform vive en **`gs://<PROYECTO>-tfstate`** (un bucket por proyecto,
lo crea `scripts/desplegar-todo.sh`): cualquiera con acceso al proyecto puede desplegar o destruir lo que
desplegó otro. Otro proyecto (por ejemplo, si se acaban los créditos) parte de cero con su propio bucket.
Los `terraform.tfstate` locales que queden en las carpetas de los stacks son de antes del cambio (0 recursos)
y se ignoran.

## 2. Servicios y stacks

| Carpeta | Qué hace **hoy** (no lo que hará) | Pruebas | ¿Desplegable en GCP? | Limitaciones conocidas |
|---|---|---|---|---|
| `gestion-de-trabajos/` | `POST /trabajos` crea **y finaliza** en una llamada (atajo de ESC-01) y publica `TrabajoFinalizado` en Pulsar. `POST /novedades` + Throttler hacia el CRM (DISP-02). Agregados `Trabajo` (2 estados) y `Novedad` | 21 unitarias OK (2026-09-21) | **Sí**, stack `gestion-de-trabajos/infra`, receta probada | Sin módulos Ciclo de Vida/Motor/Integraciones; no consume nada de Pulsar; `POST /trabajos` todavía **no** está detrás de `HABILITAR_ATAJO_CARGA` (A15, por hacer) |
| `proveedores/` | **Solo el módulo Verificación** (DISP-03): `POST /verificaciones` (202), worker con cola **Pub/Sub** (push), reintento con backoff, DLQ, `POST /dlq/{id}/reprocesar`, mocks de Policía/RUES/Certificadora. Publica `proveedor.habilitado` (nadie lo consume) | 17 unitarias OK (2026-09-21); CP-1..CP-7 de integración (ver su README) | **Sí**, stack `proveedores/infra` (recursos `disp03-poc-*`), receta probada | No existe el agregado `Proveedor` (el proveedor es un id de texto); sin Registro/Elegibilidad/Agenda; su consumidor de `trabajos.finalizado` **no se despliega** y apunta a un namespace equivocado (`hda/trabajos`) |
| `pagos/` | REST: `POST /pagos`, `GET /pagos/{id}`, `POST /pagos/{id}/compensar`. Strategy `ReglaRegional` (Colombia, Brasil) + Adapter `PasarelaDePago` (Stripe, MercadoPago) (MOD-02) | 19 unitarias OK (2026-09-21) | **Sí**, stack `pagos/infra`, receta probada | No publica ni consume eventos; no retiene; lo llama el cliente directo |
| `reputacion/` | `POST /calificaciones`, `GET /reputacion/{id}` (Event Sourcing). Consumidor de `trabajos.finalizado` que **solo audita** | 9 unitarias OK (2026-09-21) | **Solo la API**, stack `reputacion/infra` | El consumidor Pulsar **no se despliega** en Cloud Run (no tiene HTTP; ver CONVENCIONES §5); no publica `ReputacionPublicada` |
| `marketplace/`, `siniestros/`, `suscripciones/`, `scoring/` | **No existen** | — | No | Diseñados en 15-…md; se construyen en la Entrega 5 |
| `mocks-pagos/` | Dobles de Stripe y MercadoPago con inyección de fallas | — | **Sí**, stack `mocks-pagos/infra` | Respuesta síncrona; no manda webhook de confirmación |
| `mocks-crm/` | Doble del CRM de Gestión de Agentes con rate limit configurable | — | **Sí**, stack `mocks-crm/infra` | No devuelve "novedad resuelta" (webhook de vuelta, necesario para E5) |
| `pulsar-infra/` | Cluster Pulsar (ZK + BookKeeper + broker). Local: docker-compose. GCP: 1 VM (`pulsar-infra/gcp`) | — | **Sí**, receta probada | En GCP la VM crea sola el tenant y los 8 namespaces (sin probar aún); en local, `scripts/pulsar-namespaces-local.sh` |
| `observabilidad/` | Grafana en Cloud Run con dashboard de p95 / throughput / 5xx | — | **Sí**, receta probada | Sin panel "Journey" |
| `k6/` | Script de carga ESC-01 (`esc-01.js`) + VM de carga (`k6/infra`) | Resultados en `RESULTADOS-ESCALABILIDAD-GCP.md` | Opcional | Pega a `POST /trabajos` (el atajo) |
| `postman/` | Colecciones por escenario (ESC-01, DISP-03, DISP-02, MOD-02) y por servicio | Ensayo: 62/62, 11/11, 5/5, 12/12 aserciones | — | Sin carpeta "Journey E5" |

## 3. Cómo levantar lo que existe hoy

**Con los scripts** (recomendado): `cd scripts && PROJECT=<proyecto> ./desplegar-todo.sh`; para apagar,
`./destruir-todo.sh`; para comprobar, `./verificar-nada-facturando.sh`. State en `gs://<PROYECTO>-tfstate`.

| Script | Estado |
|---|---|
| `verificar-nada-facturando.sh` | **Probado** contra `hogaralpes` (2026-09-21): 0 recursos, código 0 |
| `desplegar-todo.sh`, `destruir-todo.sh` | Validados (bash -n, shellcheck, `terraform validate` de los 10 stacks); **no corridos todavía contra GCP**. Reproducen la receta probada |
| Namespaces de Pulsar en GCP | Automáticos en el arranque de la VM (antes eran a mano); no probado aún en una VM real |

Receta completa, **probada** de punta a punta (despliegue y destroy) en `hogaralpes`:
[`DESPLIEGUE-GCP-INTEGRAL.md`](DESPLIEGUE-GCP-INTEGRAL.md), sección **"Receta vigente"**. Orden: imágenes →
Pulsar → mocks → servicios → Grafana. Destroy en orden inverso.

El bloque **"Entrega 5: lo que cambia en esta receta"** del mismo archivo **todavía no está probado**:
describe stacks que no existen. No lo ejecutes hasta que la fila del servicio en la tabla de arriba
diga "desplegable".

Antes de desplegar en un proyecto nuevo:
1. Facturación activa, `gcloud auth login` y `gcloud auth application-default login`.
2. Cuota de 20 vCPU por región como mínimo (GT usa 2 vCPU × 9 instancias).
3. Terraform ≥ 1.5 y Python 3.12 (las pruebas unitarias también corren con 3.11).
4. Al terminar de medir: `scripts/destruir-todo.sh`. Cloud SQL factura aunque no haya tráfico.

## 4. Resultados medidos (Entregas 3-4, con cada escenario suelto)

| Escenario | Resultado | Evidencia |
|---|---|---|
| ESC-01 | p95 de aceptación 5,2 s con 0 % de fallo tras 10 corridas; **no cumple** el umbral de < 2 s | `RESULTADOS-ESCALABILIDAD-GCP.md` |
| DISP-02 | 2000/2000 novedades entregadas, 0 agotadas | `RESULTADOS-DISP02.md` |
| DISP-03 | H1 validada a escala de PoC en GCP real | `proveedores/RESULTADOS-DISP03.md` |
| MOD-02 | 17/17 pruebas de extensión Brasil/MercadoPago sin tocar Colombia/Stripe | `RESULTADOS-MOD02.md` |

En la Entrega 5 se vuelven a medir **dentro del journey** (JRN-01..05, 15-…md §11). Todavía no hay
ninguna medición de journey.

## 5. CI (`.github/workflows/pr-quality-gate.yml`)

Corre en cada PR hacia `main`: lint + formato + compose + pytest de **Proveedores** (obligatorio) y de
**Gestión de Trabajos, Reputación y Pagos** (opcionales: pasar a obligatorios tras su primera corrida verde);
`terraform fmt/validate` de **los 10 stacks**; `bash -n` + shellcheck de `scripts/`; higiene (conflictos,
secretos). No despliega nada: desplegar es manual con los scripts.

## 6. Pendientes que siguen vivos

- `../contexto/escenarios_calidad.md`: 6 de 9 escenarios sin los campos 7-11 (decisión, sensibilidad,
  tradeoffs, riesgos, rationale + diagrama). Tienen los 11 campos: ESC-01, DISP-02 y DISP-03.
- `k6/README.md`: la tabla de resultados tiene placeholders `TBD`.
- Imágenes de las vistas: ver `../contexto/diagramas/entrega-5/CORRECCIONES.md`.
- Validar `../contexto/03-contextos-acotados-TO-BE.cml` con Context Mapper.
- Diseño cerrado (A21-A27) y plan en `../contexto/16-plan-entrega-5.md`. La Etapa 1 **no está cerrada**: ver
  el §7 (avance por paso de `../contexto/18-guia-paso-a-paso-entrega-5.md`).

## 7. Avance de la Entrega 5, Etapa 1 (paso a paso)

Estado por paso de la guía, contra su punto de control. **Última verificación: 2026-09-21.** El CI en verde solo
prueba lint, arranque y las pruebas que existen; no valida estos puntos de control.

| Paso | Estado | Qué falta para el punto de control |
|---|---|---|
| 1.1 Base común | **Hecho** (2026-09-21) | AsyncAPI con los 29 canales (válido con `@asyncapi/cli`); plantilla de mensajería (propiedades §3, `JsonSchema` en el registry, idempotencia por `id_evento`, DLQ nativa) probada contra Pulsar local; worker estándar con `/salud`; campos de log del §13; reglas de retrocompatibilidad (CONVENCIONES §3.1); `scripts/exportar-openapi.sh`; prueba de arquitectura. Falta que los demás servicios copien la plantilla (pasos 1.2-1.9) y `terraform validate` de los stacks nuevos (con cada uno) |
| 1.2 Gestión de Trabajos + saga | **Hecho** | Layout por módulos, máquina de estados §6 completa, handlers de todos los pasos de §7.1, plazos, idempotencia, `saga_log` con las columnas de §7.1, consultas SQL, worker |
| 1.3 Proveedores | En curso | Reserva de agenda real y atómica, elegibilidad (A9, A10, A12), namespace de `TOPIC_TRABAJOS_FINALIZADO`, cola de Verificación en Pulsar |
| 1.4 Pagos | **Hecho** | Retener/liberar/compensar con eventos, modo de falla en `mocks-pagos`, worker |
| 1.5 Reputación | **Hecho** | Reputación compuesta (A10), `ReputacionPublicada`, worker |
| 1.6 Marketplace | **Hecho** | Esqueleto existe; sin el contrato del AsyncAPI, sin pruebas que colecten |
| 1.7 Siniestros | En curso | Ídem |
| 1.8 Suscripciones | En curso | Ídem |
| 1.9 Scoring | En curso | Esqueleto existe; sin Dockerfile ni `requirements.txt` |
| 1.10 BFF | En curso | Rutas por actor, `/v1/trabajos`, `openapi.json`, pruebas |
| 1.11 Journey local | Pendiente | Los 5 tests actuales aceptan `404`/`500`; hay que reescribirlos con aserciones reales |
| 1.12 Auditoría | Pendiente | Correr `rubrica-auditor` al terminar 1.2-1.11 |

Etapa 2 en paralelo (solo lo que no depende del código): 2.1 (`journey/PLAN-EXPERIMENTOS.md`) y borrador de 2.3
(`QUERIES-GCP-JOURNEYS.md`, sin probar contra GCP). 2.2 y 2.5-2.7 esperan a que 1.11 esté en verde.

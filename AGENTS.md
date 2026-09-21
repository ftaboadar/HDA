# Hogar de los Alpes — guía para cualquier asistente de IA

Este equipo usa herramientas distintas (Claude Code, Gemini CLI, Codex CLI, u otras). Este archivo
es el punto de entrada **agnóstico de herramienta**: `AGENTS.md` en la raíz del repo es una
convención que varias de estas herramientas leen automáticamente al abrir el proyecto; si la tuya no
lo hace, pégale este archivo al inicio de la conversación. No dupliques su contenido en otro lado:
si algo cambia, se actualiza aquí y todas las herramientas quedan al día.

## Qué es este repo

Proyecto de curso **Hogar de los Alpes (HdA)**, MISO 2026-14 (Maestría en Ingeniería de Software).
Marketplace de servicios para el hogar (B2C, B2B2C con aseguradoras/bancos, suscripciones) migrando
de monolito a microservicios orientados a eventos, desplegado en GCP.

- Entregas 1-4: **completas** (dominio DDD, diseño táctico y atributos de calidad, diseño de
  experimentación, transacción larga con Pulsar y 4 escenarios medidos en GCP).
- **Hoy no hay nada desplegado en GCP** (todo se destruyó; ver `implementacion/ESTADO-IMPLEMENTACION.md`).
- **Entrega 5: en curso.** Cerrar la saga: conectar los 4 escenarios implementados (ESC-01, DISP-03,
  DISP-02, MOD-02) en **un solo journey de negocio** entre 8 microservicios, con comunicación entre
  servicios (Pulsar) y entre módulos (dentro de cada servicio). Rama: `feature/entrega-5-journey-saga`.

## Estructura del repo: dos carpetas, dos propósitos

```
experimento-arquitectura/
├── contexto/          Todo lo que hay que LEER: dominio (DDD estratégico, .cml), vistas de arquitectura
│   │                   (.puml + diagramas/), escenarios de calidad, reglas de rúbrica, planes de entrega,
│   │                   y los PDFs/pptx fuente del curso (en contexto/utils/). Nada ejecutable vive aquí.
│   ├── diagramas/entrega-5/   imágenes de las 4 vistas del equipo — PENDIENTES DE CORREGIR (ver CORRECCIONES.md)
│   └── historico/             entregas anteriores: NO es fuente para implementar ni desplegar
│
└── implementacion/    Todo lo que hay que CORRER: un subdirectorio por microservicio o pieza de infra,
                        cada uno con su README, app/, tests/, infra/ (Terraform) y docker-compose.
```

Regla al agregar algo nuevo: si es explicación, decisión, diagrama o rúbrica → `contexto/`. Si es
código que se ejecuta (API, tests, IaC, scripts) → `implementacion/<servicio>/`.

## Dos reglas antes de cualquier cosa

1. **Diseño ≠ implementación.** `contexto/15-arquitectura-entrega-5.md` es el **diseño objetivo** (lo que
   se va a construir). `implementacion/ESTADO-IMPLEMENTACION.md` es **lo que existe de verdad hoy**. Si no
   coinciden, no inventes ni "completes" en silencio: **para desplegar manda el estado real; para
   construir manda el diseño.** Si implementas, despliegas o destruyes algo, actualiza
   `ESTADO-IMPLEMENTACION.md` en el mismo cambio.
2. **Para desplegar o destruir en GCP, usa `implementacion/scripts/`** (`desplegar-todo.sh`,
   `destruir-todo.sh`, `verificar-nada-facturando.sh`, con `PROJECT=<proyecto>`), que siguen la receta probada
   de `DESPLIEGUE-GCP-INTEGRAL.md`, y solo para lo que `ESTADO-IMPLEMENTACION.md` marca como desplegable. El
   state de Terraform está en `gs://<PROYECTO>-tfstate`: nunca borres ese bucket con recursos vivos.
   Nada de `contexto/historico/` ni de las imágenes pendientes de corregir es fuente.

## Leer en este orden antes de tocar nada

1. **`experimento-arquitectura/contexto/15-arquitectura-entrega-5.md`**: la **fuente de verdad** de
   la Entrega 5. Qué servicios hay, el journey completo, la máquina de estados del Trabajo, el
   **catálogo de eventos** (tópicos, productores, consumidores, campos) y las decisiones cerradas y
   abiertas. Si otro documento lo contradice, gana este.
   **`experimento-arquitectura/contexto/16-plan-entrega-5.md`**: el plan de implementación por fases, con
   el reparto por integrante y la definición de terminado.
   **`experimento-arquitectura/contexto/18-guia-paso-a-paso-entrega-5.md`**: el orden de trabajo paso a paso, con el
   prompt de cada paso y su punto de control.
2. **`experimento-arquitectura/implementacion/ESTADO-IMPLEMENTACION.md`**: qué existe hoy, qué se puede
   desplegar, qué está desplegado (hoy: nada) y las limitaciones conocidas de cada servicio.
3. **`experimento-arquitectura/implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`**: **cómo** se
   construye y despliega cualquier servicio (layout por módulos, reglas DDD, Pulsar, worker en
   Cloud Run, Terraform, CI). Síguelo al pie de la letra para que todos los servicios queden iguales.
4. **La rúbrica vigente: `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-5.md`** (saga ≥ 4
   servicios con compensación, Saga Log con coordinador, BFF, despliegue, Postman, resultados, refinamiento
   de vistas, contribución equitativa). PDFs fuente en `contexto/utils/`. `REGLAS-DURAS-rubrica-entrega-3.md`
   sigue valiendo para los criterios DDD (Regla 5) y de volúmenes (Regla 3).
5. Las vistas: `contexto/04-vista-contexto.puml`, `05-vista-modulo.puml`, `06-vista-cyc.puml`,
   `07-vista-informacion.puml`: son las fuentes de texto **ya corregidas**. Sus imágenes en
   `contexto/diagramas/entrega-5/` están **pendientes de corregir**: no las uses como fuente.
6. `experimento-arquitectura/implementacion/DESPLIEGUE-GCP-INTEGRAL.md`: receta para montar y apagar
   **todo** en un proyecto GCP propio, con los bugs reales ya resueltos.
7. `experimento-arquitectura/contexto/10-estructura-multiagente.md`: los 6 roles de equipo y por qué
   el trabajo está separado como está.
8. Solo como historia: `contexto/historico/` (planes de las Entregas 1-4 y las imágenes viejas de las
   vistas). Muchos comentarios del código citan `12-plan-entrega-4.md`: está en esa carpeta. **Sus
   decisiones fueron revisadas en la Entrega 5** (ver 15-…md §10). `implementacion/proveedores/plan.md`
   sigue siendo la especificación del experimento DISP-03.

## Restricciones duras del proyecto (decisiones de equipo: no reabrir sin acuerdo)

- **Nube objetivo: GCP** (`southamerica-east1`). Todo patrón/táctica debe tener traducción concreta a
  servicios GCP (Cloud Run, Cloud SQL Postgres, Pub/Sub, VM con Pulsar, Secret Manager, Artifact
  Registry, Cloud Logging/Monitoring), y en la Entrega 5 **se despliega y se valida en GCP**.
- **Stack: Python 3.12** (FastAPI, SQLAlchemy, pydantic-settings, pulsar-client), **Terraform** para
  infraestructura, docker-compose para local.
- **Bus entre servicios: Apache Pulsar.** Única excepción: la cola interna de Verificación de
  Proveedores (DISP-03) sigue en Cloud Pub/Sub. No hay Kafka en este proyecto.
- **Cada microservicio es su propio Bounded Context**, con su BD, su seedwork y su stack de Terraform.
  Entre servicios solo hay eventos de integración (y REST hacia externos). Nunca se comparte BD.
- **Gestión de Pagos es un contexto propio** (`implementacion/pagos/`); el externo es la **pasarela**
  (Stripe, MercadoPago). Documentos anteriores que digan "Pagos es externo" están desactualizados.

## Estado actual de la implementación

| Servicio (`implementacion/…`) | Estado | Escenario |
|---|---|---|
| `gestion-de-trabajos/` | existe (Trabajo mínimo + Novedades/Throttler); **E5: módulos Ciclo de Vida, Motor, Novedades, Integraciones Externas + estados + consumidores** | ESC-01, DISP-02 |
| `proveedores/` | existe, pero en la práctica **solo el módulo Verificación** (DDD, DLQ, Pub/Sub; recursos `disp03-poc-*`); **E5: módulos Registro, Elegibilidad y Agenda + ampliar Verificación a técnicos/empresa + consumidores; prefijo `proveedores-poc`** | DISP-03 |
| `pagos/` | existe (Strategy regional + Adapter de pasarela, solo REST); **E5: retener al confirmar agenda, liberar al finalizar, compensar en disputa, todo por eventos** | MOD-02 |
| `reputacion/` | existe (Event Sourcing; `TrabajoFinalizado` solo se audita); **E5: habilitar calificación, publicar `ReputacionPublicada`, consumir scoring** | — |
| `marketplace/` | **no existe, E5** | entrada del journey |
| `siniestros/` | **no existe, E5** | fuente del pico (ESC-01) |
| `suscripciones/` | **no existe, E5** (módulo Ciclo de Suscripción) | MOD-03 |
| `scoring/` | **no existe, E5** | — |
| `pulsar-infra/`, `mocks-*`, `observabilidad/`, `infra-modules/`, `k6/`, `postman/`, `asyncapi/` | infraestructura, dobles externos, carga y contratos | — |

Resultados medidos de las Entregas 3-4 (ESC-01, DISP-02, DISP-03, MOD-02): ver
`implementacion/README.md` y los `RESULTADOS-*.md`. En la Entrega 5 hay que **volver a medirlos
dentro del journey**, y quien corre (`experimento-runner`) no es quien da el veredicto
(`validador-hipotesis`).

## Los 6 roles del equipo (herramienta-agnósticos por diseño)

Viven como archivos completos en **`.claude/agents/*.md`**: markdown plano con una pequeña cabecera
YAML al inicio. Cualquier asistente los puede leer y seguir, tenga o no soporte nativo de
"subagentes"; la cabecera YAML solo la usa Claude Code para registrarlos.

| Rol | Archivo | Cuándo usarlo |
|---|---|---|
| Auditor de rúbrica | `.claude/agents/rubrica-auditor.md` | Verificar cumplimiento contra la rúbrica vigente, en cualquier punto de control |
| Diseñador de escenarios | `.claude/agents/disenador-escenarios.md` | Completar/extender los escenarios de calidad y mantener coherentes las vistas |
| Implementador DDD | `.claude/agents/implementador-ddd.md` | Construir o completar cualquiera de los 8 microservicios según 15-…md y CONVENCIONES |
| Experto GCP | `.claude/agents/experto-gcp.md` | Terraform, despliegue, Pulsar en GCP, costo/cuota, portabilidad |
| Ejecutor de experimentos | `.claude/agents/experimento-runner.md` | Correr el journey y los escenarios (local/GCP), producir datos crudos |
| Validador de hipótesis | `.claude/agents/validador-hipotesis.md` | Juzgar de forma independiente y escéptica si cada hipótesis se valida o se refuta |

**Si tu asistente soporta subagentes nativos** (Claude Code sí, ver `CLAUDE.md`), regístralos
apuntando a esos mismos archivos en vez de reescribirlos. **Si no** (ver `GEMINI.md`): antes de una
tarea que calce con un rol, abre su archivo y trátalo como el system prompt de esa tarea, sin saltarte
la separación entre roles (en particular: quien ejecuta un experimento no decide si la hipótesis se
valida).

## Convención para insumos que llegan de fuera del repo (rúbricas, diagramas, PDFs)

Si el usuario comparte un archivo desde `~/Downloads` u otra carpeta fuera del repo, **cópialo dentro**
antes de trabajar con él y de citarlo en cualquier documento (rúbricas → `contexto/`, diagramas →
`contexto/diagramas/…`, fuentes del curso → `contexto/utils/`). Un archivo que solo vive fuera del
repo rompe la referencia para cualquier sesión o herramienta futura.

## Cómo mantener esto coherente

- Cambias una decisión de arquitectura → primero `15-arquitectura-entrega-5.md`, luego la `.puml`
  afectada y, si aplica, `diagramas/entrega-5/CORRECCIONES.md`; al final el código.
- Cambias cómo se construye o despliega algo → `CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md` y la receta
  de `DESPLIEGUE-GCP-INTEGRAL.md`.
- Agregas un servicio → fila en la tabla "Estado actual" de este archivo, matriz del CI
  (`.github/workflows/pr-quality-gate.yml`) y su stack en la receta de despliegue.

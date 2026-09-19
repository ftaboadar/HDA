# Hogar de los Alpes — guía para cualquier asistente de IA

Este equipo usa herramientas distintas (Claude Code, Gemini CLI, Codex CLI, u otras). Este archivo
es el punto de entrada **agnóstico de herramienta** — `AGENTS.md` en la raíz del repo es una
convención que varias de estas herramientas leen automáticamente al abrir el proyecto; si la tuya no
lo hace, pégale este archivo al inicio de la conversación. No dupliques su contenido en otro lado:
si algo cambia, se actualiza aquí y todas las herramientas quedan al día.

## Qué es este repo

Proyecto de curso **Hogar de los Alpes (HdA)**, MISO 2026-14 (Maestría en Ingeniería de Software).
Entregas 1 y 2 (dominio estratégico DDD, diseño táctico y atributos de calidad) ya están completas.
Entrega 3 (Diseño de Experimentación) está en cierre — ver estado detallado abajo. Trabajo en
planificación: **Entrega 4 — transacción larga no monolítica** (`12-plan-entrega-4.md` y
`13-guia-entrega-4-pasos.md`).

## Estructura del repo — dos carpetas, dos propósitos distintos

`experimento-arquitectura/` se divide en exactamente dos cosas, para que nunca se mezcle "para
entender el proyecto" con "para correrlo":

```
experimento-arquitectura/
├── contexto/          Todo lo que hay que LEER: dominio (DDD estratégico), atributos de calidad,
│                       escenarios, reglas de la rúbrica, vistas de arquitectura (C4/C&C/módulo),
│                       event storming, la estructura de equipo multiagéntica, y los PDFs/pptx
│                       fuente del curso (en contexto/utils/). Nada de código ejecutable vive aquí.
│
└── implementacion/    Todo lo que hay que CORRER: un subdirectorio por experimento (ej. proveedores/),
    └── proveedores/    cada uno con su propio plan.md/README.md (el contexto específico de ESE
                         experimento — no del proyecto general) junto al código real: app/, tests/,
                         infra/ (Terraform), cli/ (herramientas de aprovisionamiento GCP).
```

Regla al agregar algo nuevo: si es explicación, decisión, diagrama o rúbrica → `contexto/`. Si es
código que se ejecuta (API, tests, IaC, scripts) → `implementacion/<experimento>/`. El `plan.md` y el
`README.md` de un experimento se quedan junto a su propio código (no en `contexto/`) porque son la
documentación operativa de ESE experimento, no contexto general del proyecto.

## Leer en este orden antes de tocar nada

1. `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md` — lo que la rúbrica del
   curso exige, con puntaje. Es la fuente de verdad de qué se está calificando; no relajar ni
   reinterpretar.
2. `experimento-arquitectura/contexto/10-estructura-multiagente.md` — los 6 roles de equipo (ver
   abajo) y por qué el flujo de trabajo está separado como está.
3. `experimento-arquitectura/implementacion/proveedores/plan.md` y `.../README.md` — el experimento de
   Entrega 3: qué se planeó, qué se implementó, qué se validó de verdad (7/7 pruebas pasando contra
   el stack real, incluida una corrida contra GCP real) y qué falta.
4. `experimento-arquitectura/contexto/12-plan-entrega-4.md` y `13-guia-entrega-4-pasos.md` — plan y
   runbook de la **próxima** entrega (transacción larga Gestión de Trabajos → Proveedores → Pagos +
   Reputación, sobre un cluster de Apache Pulsar). Léelos antes de tocar algo que suene a "Pulsar",
   "Gestión de Trabajos", "Pagos" o "Reputación" — ninguno de esos microservicios existe todavía en
   `implementacion/`.

## Restricciones duras del proyecto (decisiones de equipo — no reabrir sin acuerdo del equipo)

- **Nube objetivo: GCP.** Cualquier patrón/táctica propuesta debe tener traducción concreta a
  servicios GCP (ver mapeos en `.claude/agents/experto-gcp.md`), no quedarse en nombre genérico.
- **Stack de implementación: Python.**

## Los 6 roles del equipo — herramienta-agnósticos por diseño

Viven como archivos completos en **`.claude/agents/*.md`** — son markdown plano con una pequeña
cabecera YAML al inicio; cualquier asistente los puede leer y seguir, tenga o no soporte nativo de
"subagentes". La cabecera YAML es metadata que solo Claude Code usa para registrarlos como
subagentes invocables — el resto del archivo es la instrucción real, y esa parte es 100% portable.

| Rol | Archivo | Cuándo usarlo |
|---|---|---|
| Auditor de rúbrica | `.claude/agents/rubrica-auditor.md` | Verificar cumplimiento contra las reglas duras, en cualquier punto de control |
| Diseñador de escenarios | `.claude/agents/disenador-escenarios.md` | Completar/extender los 9 escenarios de calidad |
| Implementador DDD | `.claude/agents/implementador-ddd.md` | Construir el servicio con DDD + hexagonal + eventos + CQS (Regla 5, 45pt — ya implementada en Verificación de Proveedores; para Entrega 4 construye Gestión de Trabajos/Pagos/Reputación) |
| Experto GCP | `.claude/agents/experto-gcp.md` | Traducir decisiones a servicios GCP concretos, IaC, portabilidad del PoC |
| Ejecutor de experimentos | `.claude/agents/experimento-runner.md` | Construir/correr el PoC de fault-injection, producir datos crudos |
| Validador de hipótesis | `.claude/agents/validador-hipotesis.md` | Juzgar de forma independiente y escéptica si H1 se valida o refuta |

**Si tu asistente soporta subagentes/personas nativos** (Claude Code sí — ver `CLAUDE.md`),
regístralos apuntando a esos mismos archivos en vez de reescribirlos, para que no haya dos copias
que se desalineen con el tiempo.

**Si tu asistente no soporta subagentes nativos** (o no estás seguro): antes de trabajar en algo que
calce con uno de estos roles, abre el archivo correspondiente y trátalo como el system prompt de esa
tarea — léelo completo, sigue sus instrucciones de "qué leer primero" y "qué NO hacer", y no te
saltes la separación entre roles (en particular: quien ejecuta el experimento no es quien decide si
la hipótesis se valida — ver `experimento-runner.md` y `validador-hipotesis.md`).

## Convención para insumos que llegan de fuera del repo (rúbricas, escenarios en PDF/MD)

Si el usuario comparte un archivo desde `~/Downloads` u otra carpeta fuera del repo, cópialo dentro
antes de trabajar con él y de citarlo en cualquier documento — los roles de arriba referencian rutas
relativas al repo (ej. `experimento-arquitectura/contexto/escenarios_calidad.md`); un archivo que solo vive
fuera del repo rompe esa referencia para cualquier sesión o herramienta futura que no tenga el
contexto de la conversación original en la que se compartió.

## Estado actual (resumen — el detalle vivo está en los archivos citados arriba)

- Entregas 1 y 2: completas.
- Escenarios de calidad (`escenarios_calidad.md`): existen los 9. Los 5 campos que la rúbrica exige
  por escenario (decisión arquitectural, puntos de sensibilidad, tradeoffs, riesgos,
  rationale+diagrama) ya están completos en **DISP-03**; siguen pendientes en los otros 8
  (DISP-01/02, MOD-01/02/03, ESC-01/02/03). Le corresponde a `disenador-escenarios`.
- Experimento DISP-03: implementado y validado — localmente (Docker + pytest, 7/7 casos pasan) y
  **contra un proyecto GCP real** (`hda-projectt`, 2026-09-06; H1 validada a escala de PoC, 3 bugs de
  producción encontrados y corregidos que nunca aparecieron en local). La infra real se destruyó al
  cerrar esa sesión (costo detenido); el código quedó commiteado en `main`.
- Regla 5 de la rúbrica (45pt, implementación DDD del servicio elegido — Verificación de Proveedores):
  implementada y verificada (13/13 pruebas de dominio, hexagonal confirmado por imports, CQS
  explícito). Ver `implementacion/proveedores/README.md`.
- Falta conseguir el template oficial de presentación de la Entrega 3 (no está en el repo) — único
  punto de Entrega 3 aún sin cerrar aparte de los campos 7-11 de los 8 escenarios restantes.
- **Entrega 4 (siguiente):** plan y runbook recién integrados en `12-plan-entrega-4.md` /
  `13-guia-entrega-4-pasos.md` — construir **3** microservicios propios (Gestión de Trabajos,
  Proveedores, Reputación) más migrar Proveedores de Pub/Sub a **Apache Pulsar**, para revalidar
  ESC-01/DISP-03(+02)/MOD-02 sobre la cadena completa. **Pagos NO es un 4to microservicio propio** —
  es un `GENERIC_SUBDOMAIN` externo desde Entrega 1 (`01-dominios-subdominios.cml`,
  `03-contextos-acotados-TO-BE.cml`, `05-vista-modulo.puml` lo marcan `<<externo>>` los tres,
  independientemente entre sí); su Strategy/Adapter (MOD-02) viven como módulo ACL dentro de Gestión
  de Trabajos, ver `12-plan-entrega-4.md` sección 0.1. Nada de esto existe todavía en
  `implementacion/`; la migración de Proveedores invalida la evidencia de GCP-real citada arriba hasta
  que se re-ejecute contra Pulsar.

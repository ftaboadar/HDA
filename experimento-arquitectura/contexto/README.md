# Hogar de los Alpes (HdA) — Entrega 1: Diseño y Arquitectura de Dominio

Maestría en Ingeniería de Software (MISO) — Proyecto 2026-14

## Estructura del proyecto

```
entregables/
├── README.md                                          (este archivo)
├── 01-dominios-subdominios.cml                         Dominios y sub-dominios (DSL ContextMapper)
├── 02-contextos-acotados-AS-IS.cml                      Contextos acotados AS-IS (DSL ContextMapper)
├── 03-contextos-acotados-TO-BE.cml                      Contextos acotados TO-BE (DSL ContextMapper)
├── diagramas/
│   ├── 02-contextos-acotados-AS-IS_ContextMap.png       Imagen generada del Context Map AS-IS
│   ├── 02-contextos-acotados-AS-IS_ContextMap.svg       (misma imagen, vectorial)
│   ├── 02-contextos-acotados-AS-IS_ContextMap.gv        (fuente Graphviz, generada automáticamente)
│   ├── 03-contextos-acotados-TO-BE_ContextMap.png       Imagen generada del Context Map TO-BE
│   ├── 03-contextos-acotados-TO-BE_ContextMap.svg       (misma imagen, vectorial)
│   └── 03-contextos-acotados-TO-BE_ContextMap.gv        (fuente Graphviz, generada automáticamente)
├── event-storming-AS-IS.png                             Lenguaje ubicuo AS-IS (entregable, PNG)
├── event-storming-AS-IS.html                            Fuente editable del PNG anterior (no es el entregable en sí)
├── event-storming-TO-BE.png                             Lenguaje ubicuo TO-BE (entregable, PNG)
└── event-storming-TO-BE.html                            Fuente editable del PNG anterior (no es el entregable en sí)
```

Los archivos `.gv` y `.svg` dentro de `diagramas/` son subproductos de la generación automática del `.png`
a partir del `.cml` — no hace falta abrirlos, están incluidos por transparencia (para que se pueda verificar
que el `.png` sí sale del `.cml` y no fue dibujado a mano). Lo mismo aplica a los `.html` de Event Storming:
son la fuente desde la que se generó el `.png` (una plantilla estilo post-its renderizada con un navegador
en modo headless), incluidos únicamente como evidencia de trazabilidad.

**Este proyecto no fue desarrollado en Gitpod**, por lo que no aplica incluir un archivo `.gitpod.yml`.

## Cómo abrir y validar este proyecto

Requisitos:
- Java 17 o superior.
- La extensión de VS Code **"Context Mapper Modeling Toolkit"** (`contextmapper.context-mapper-vscode-extension`),
  o el [Context Mapper CLI oficial](https://github.com/ContextMapper/context-mapper-cli) si se prefiere línea de comandos.
- [Graphviz](https://graphviz.org/download/) instalado y en el `PATH`, solo si se desea **regenerar** las imágenes de `diagramas/` (no es necesario para solo leerlas, ya están generadas).

Para validar la sintaxis de cualquier archivo `.cml` con el CLI:
```bash
cm validate -i 01-dominios-subdominios.cml
cm validate -i 02-contextos-acotados-AS-IS.cml
cm validate -i 03-contextos-acotados-TO-BE.cml
```

Para regenerar un diagrama de Context Map a partir del `.cml`:
```bash
cm generate -i 03-contextos-acotados-TO-BE.cml -g context-map -o diagramas
```

Los tres archivos `.cml` fueron validados sin errores con esta misma herramienta antes de esta entrega.
`02-` y `03-` importan `01-dominios-subdominios.cml` (`import "./01-dominios-subdominios.cml"`), así que
los tres archivos deben mantenerse en la misma carpeta.

## Mapeo a los ítems de calificación

### 1. Documentación de dominios y sub-dominios — 15pt

| Ítem de la rúbrica | Valor | Dónde encontrarlo |
|---|---|---|
| Dominios y sub-dominios identificados y documentados con el DSL | 10pt | `01-dominios-subdominios.cml` — 1 `Domain` (`ServiciosParaElHogar`) + 9 `Subdomain` |
| Vision statement para todos los dominios | 2.5pt | Mismo archivo, campo `domainVisionStatement` en el dominio raíz y en cada uno de los 9 sub-dominios (10 en total) |
| Tipo de sub-dominio (núcleo/soporte/genérico) | 2.5pt | Mismo archivo, campo `type` en cada `Subdomain`: 6 `CORE_DOMAIN`, 2 `SUPPORTING_DOMAIN`, 1 `GENERIC_SUBDOMAIN` |

### 2. Documentación del lenguaje ubicuo — 40pt

Flujo documentado: **Marketplace** — desde que un dueño de hogar solicita un trabajo hasta que lo paga y
califica al proveedor. Es el flujo que el propio enunciado del proyecto describe explícitamente en 5 pasos,
dentro de la sección *"Flujo de trabajo"*.

> **Nota para el tutor:** la plantilla de rúbrica de este documento menciona el flujo *"Marketing de
> Afiliados"*, que no existe en el enunciado de Hogar de los Alpes (2026-14) — no aparece ni una vez en
> todo el proyecto. Ese nombre corresponde a una plantilla de rúbrica no actualizada para este caso. En su
> lugar se documentó el flujo **Marketplace**, por ser el único flujo que el enunciado describe explícito
> y completo, paso a paso, en la sección *"Flujo de trabajo"*.

| Ítem de la rúbrica | Valor | Dónde encontrarlo |
|---|---|---|
| Actores, eventos, comandos, modelo de lectura, sistemas externos y definiciones — AS-IS | 20pt | `event-storming-AS-IS.png` |
| Actores, eventos, comandos, modelo de lectura, sistemas externos y definiciones — TO-BE | 20pt | `event-storming-TO-BE.png` |

Ambas imágenes usan el mismo código de colores (leyenda incluida en la propia imagen): Actor (amarillo),
Sistema externo (rosa), Comando (azul), Evento de dominio (naranja), Regla de negocio (morado), Modelo de
lectura (verde), Definición (blanco/gris). En el TO-BE, los eventos con borde rojo son *pivotales*: cruzan
la frontera de un contexto acotado.

### 3. Documentación de contextos acotados — 45pt

| Ítem de la rúbrica | Valor | Dónde encontrarlo |
|---|---|---|
| Todos los contextos — AS-IS | 15pt | `02-contextos-acotados-AS-IS.cml` — 6 `BoundedContext`; imagen en `diagramas/02-contextos-acotados-AS-IS_ContextMap.png` |
| Relaciones y tipos de integración — AS-IS | 7.5pt | Mismo archivo, bloque `ContextMap HogarDeLosAlpesASIS { ... }` — 5 relaciones `[SK]<->[SK]` (Shared Kernel) |
| Todos los contextos — TO-BE | 15pt | `03-contextos-acotados-TO-BE.cml` — 8 `BoundedContext`; imagen en `diagramas/03-contextos-acotados-TO-BE_ContextMap.png` |
| Relaciones y tipos de integración — TO-BE | 7.5pt | Mismo archivo, bloque `ContextMap HogarDeLosAlpesTOBE { ... }` — 11 relaciones `[OHS,PL] -> [ACL]`, cada una con `implementationTechnology` explícita |

## Decisiones de diseño relevantes (resumen para sustentación)

- **AS-IS modelado como Shared Kernel en estrella** alrededor de `ContextoGestionDeTrabajos`: refleja
  textualmente el monolito descrito en el enunciado (una misma fuente de código, equipos bloqueados entre sí).
- **`GestionDeTrabajos` es el motor de orquestación central**, agnóstico a si el trabajo viene de Marketplace,
  Siniestros o Suscripciones — estos últimos solo *parametrizan* el motor (reglas de partner, ciclo de
  facturación), no duplican lógica de flujo propia.
- **`Pagos` (genérico) cubre todo el flujo de dinero por trabajo** —cobro, retención, liberación, disputas,
  facturación diferenciada por partner y la ejecución de la transacción en sí— y **no tiene contexto acotado
  propio en el TO-BE**: se resuelve comprando una plataforma de pagos para marketplace (ej. Stripe Connect),
  que ya ofrece eso como funcionalidad estándar. En AS-IS sí vive dentro de `ContextoFintech`, porque hoy se
  construye todo internamente en el monolito en vez de comprarse.
- **`ScoringYCredito` es de soporte, no núcleo**: es una apuesta de crecimiento nueva; el negocio
  transaccional de HdA no depende de ella para operar hoy.
- **`GestionDeSuscripciones` solo existe en el TO-BE** (contexto *greenfield*, sin equivalente en el AS-IS):
  es una línea de negocio nueva mencionada en "Estrategia y visión", no una capacidad actual del monolito.

## Sustentación

Es **obligatorio sustentar esta entrega con el tutor asignado al grupo**. Agendar usando los horarios de
atención que el tutor comparta por Slack o el canal oficial del curso.

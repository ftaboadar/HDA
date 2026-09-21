# Cómo armamos la Entrega 4 — paso a paso, como equipo

> **⚠ Revisado en Entrega 5 (2026-09-21).** Runbook **histórico** de la Entrega 4. Donde trate a Pagos como ACL interno de Gestión de Trabajos, está desactualizado. Vigente: [`15-arquitectura-entrega-5.md`](../15-arquitectura-entrega-5.md) y `../../implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`.

### Complementa a `12-plan-entrega-4.md` (ese es el "qué" y "por qué" técnico; este es el "en qué orden" y "quién hace qué")

> **Nota de integración (2026-09-13):** copiado desde `~/Downloads/COMOENTREGARNOMONOLITICASE4.md`
> siguiendo la convención de `AGENTS.md` para insumos externos. Todas las referencias a
> `plan_entrega_parcial.md` del original se actualizaron a `12-plan-entrega-4.md`, su nueva ubicación
> dentro de `experimento-arquitectura/contexto/`.

---

## Las 5 fases, en orden — no te saltes ninguna

```
FASE 0          FASE 1              FASE 2            FASE 3               FASE 4            FASE 5
Preparación  →  Construcción     →  Integración    →  Experimentación  →  Documentación  →  Sustentación
(todos)         (cada quien,        (PRs + revisión    (con el sistema      (README,          (con el tutor)
                 su rama)            cruzada + CI)      YA integrado)        ACTIVIDADES,
                                                                              resultados)
```

**El error más común a evitar:** correr las pruebas de los escenarios (Fase 3) contra tu rama aislada, antes de integrar. No sirve — ESC-01 necesita a Gestión de Trabajos, Proveedores, Pagos y Reputación corriendo **juntos**, y eso solo existe después del merge.

---

## FASE 0 — Preparación (todo el equipo, 15-20 min)

| Qué | Cómo | ¿IA o manual? |
|---|---|---|
| Confirmar el reparto (Frans / Johan / Daniel) | Leer `12-plan-entrega-4.md` sección 8 juntos — ya tiene los 3 nombres reales y la carpeta de la que cada quien es dueño único | Manual — es coordinación de equipo |
| Cada quien configura su `.claude/settings.local.json` | Comando ya dado en sección 8 del plan | Manual, 1 vez |

---

## FASE 1 — Construcción individual (en paralelo, cada quien en su rama)

Ya está completamente detallado en `12-plan-entrega-4.md`, sección 8 — cada persona corre su bloque (rama, prompt al agente, commit, push) en su propia máquina.

| Qué | ¿IA o manual? |
|---|---|
| Escribir el código (comandos, queries, tablas, tópicos) | **IA**, con el prompt ya armado en el plan |
| Revisar lo que generó el agente antes de comitear | **Manual** — no comitees a ciegas, léelo |
| El commit y el push | Manual (lo ejecutas tú, desde tu cuenta) |

---

## FASE 2 — Integración (cuando las 3 ramas ya tienen su PR abierto)

| Paso | ¿IA o manual? |
|---|---|
| Abrir el Pull Request de cada rama hacia `main` | Manual |
| **Revisión cruzada — otra persona revisa el PR, no quien lo escribió** | **100% manual, no delegable a IA.** Es lo que demuestra que el equipo entendió el trabajo del otro, no solo que el código existe |
| CI corre automático (`pr-quality-gate.yml`) | Automático, ya configurado — bloquea el merge si algo falla |
| Aprobar y mergear a `main` | Manual, después de que el CI pase y alguien más haya revisado |

**Orden sugerido de merge:** primero el PR de **Daniel** (cluster de Pulsar — todos lo necesitan para probar contra algo real, aunque Reputación siga en progreso en el mismo PR), después **Johan** (ajustes a Proveedores + mocks de Stripe/MercadoPago + CI extendido), al final **Frans** (Gestión de Trabajos + módulo ACL de Pagos, que depende del cluster de Daniel y de los mocks de Johan) — así cada merge tiene lo que necesita del anterior ya en `main`.

> **Nota de integración (2026-09-13):** el reparto original (Persona A/B/C genéricas) se reemplazó por
> los 3 nombres reales del equipo, rebalanceando el trabajo en partes equivalentes por carpeta propia
> (ver `12-plan-entrega-4.md` sección 8, tabla de pesos) — necesario para que la contribución de cada
> persona quede atribuible en el historial de git, no solo declarada en `ACTIVIDADES.md`. También se
> corrigió que Pagos **no** es un microservicio propio (sección 0.1: es un subdominio genérico
> comprado/externo, ya sustentado en Entrega 1) — su Strategy/Adapter viven dentro de Gestión de
> Trabajos (Frans), y quien antes iba a construir un servicio `Pagos` completo ahora aporta solo los
> mocks de Stripe/MercadoPago (Johan) más el resto de su carga (Proveedores + CI).

---

## FASE 3 — Experimentación real (con el sistema ya integrado en `main`)

Esto se hace **después** del merge, con alguien (o el equipo completo) levantando todo junto desde `main`.

| Escenario | Qué se ejecuta | ¿IA o manual? |
|---|---|---|
| ESC-01 | `pulsar-perf produce/consume` generando carga sobre `trabajos.finalizado` | Manual ejecutar el comando; la IA puede ayudarte a armar el comando exacto o interpretar el `.hdr` en Histogram Plotter |
| DISP-03/02 | Inyectar falla en el mock (`/_control/config`) o tumbar un broker (`pulsar-admin`), mirar la API de estadísticas mientras pasa | Manual — es correr comandos y observar, no algo que la IA ejecute por ti |
| MOD-02 | `git diff` mostrando que `ReglaColombia`/`Stripe`/el core de Gestión de Trabajos no cambiaron al agregar `ReglaBrasil`/`MercadoPago` en su módulo ACL de Pagos | Manual, un comando |
| **Capturar evidencia** (screenshots, logs, números reales) | **Manual, obligatorio.** Esto es lo que después va en el README/documento — no se inventa, se corre y se guarda lo que salió |

> **Nota de integración:** DISP-03 ya tiene un precedente directo de esto — la sesión del 2026-09-06
> contra GCP real (Pub/Sub) encontró 3 bugs de producción que nunca aparecieron corriendo solo contra
> `docker-compose` local, y obligó a rediseñar 2 métricas de test que tenían umbrales inventados. Es
> evidencia concreta de por qué esta fase no se puede saltar ni simular: correr contra el cluster de
> Pulsar real (o al menos contra el `docker-compose` del cluster, antes del despliegue a GKE) es lo
> que va a sacar a la luz los bugs equivalentes en la migración de Proveedores.

---

## FASE 4 — Documentación

Aquí está tu pregunta específica — te la respondo directo:

### README.md — sí, obligatorio para esta entrega

Plantilla ya está en `12-plan-entrega-4.md` sección 1.6. Se llena con los resultados **reales** de la Fase 3, no con lo que "debería" salir.

| Quién | ¿IA o manual? |
|---|---|
| Redactar el README con la plantilla | **IA puede armar el borrador**, pegándole los números/logs reales de la Fase 3 | 
| Verificar que los números que puso la IA son los que de verdad salieron, no inventados | **Manual, crítico** — no dejes que la IA "complete" un resultado que no corrieron |

### ACTIVIDADES.md — cada quien la propia, sin IA escribiéndola por ti

Esto **no se lo pidas al agente que la redacte por todos** — es literalmente el testimonio de qué hizo cada persona. Cada quien escribe la suya, en su propio PR (ya está indicado en sección 1.2 del plan). El archivo no existe todavía en la raíz del repo — la primera persona en abrirlo lo crea.

### ¿Un documento/pptx explicando la POC, con justificación y resultados?

Aquí tengo que ser preciso con lo que exige el enunciado, porque hay una distinción real:

- **El enunciado original dice explícito**: *"su documento debe presentar los resultados cuantitativos y cualitativos"* es el **punto 10**, y ese punto está en la lista de **"puntos 7 a 11", que son de la entrega FINAL, no de esta parcial** (la parcial cubre puntos 1-6+9). Técnicamente, un pptx pulido de resultados no es obligatorio todavía.
- **Pero** — el enunciado también dice: *"su grupo debe sustentar con el tutor **todos los ítems enumerados anteriormente**"*, y eso aplica a ambas entregas. Necesitas **algo** que mostrarle al tutor en la sustentación de esta semana, aunque no sea el documento pulido de resultados.

**Mi recomendación:** no construyas el pptx completo de resultados todavía (eso sí, para la entrega final, con más tiempo) — pero sí arma una versión corta, 5-6 slides, solo para la sustentación de esta semana:

1. Los 4 microservicios y la cadena de transacción (diagrama simple)
2. Los 3 escenarios que se están validando
3. Decisiones clave con su justificación (Pulsar cluster, Avro, descentralizado — ya están todas escritas en el plan, es copiar y resumir)
4. Lo que corrió en Fase 3, con evidencia (captura de pantalla de Pulsar Perf, de la API de stats, etc.)
5. Qué queda para la entrega final (la Saga, el BFF, el documento completo de resultados)

| Quién | ¿IA o manual? |
|---|---|
| Armar el esqueleto del pptx corto | **IA puede ayudar**, dame la orden cuando lleguemos ahí y te lo armo con el mismo estilo que usamos en la Entrega 3 |
| Las capturas/evidencia de la Fase 3 | Manual — tienen que ser las reales |

---

## FASE 5 — Sustentación con el tutor

- Tener el código corriendo, listo para demo en vivo si el tutor lo pide (*"los tutores están en la potestad de ver su código y solicitar una demostración"*)
- Repartir quién explica qué — igual que hicimos para la sustentación de la Entrega 3, cada persona explica lo que construyó

---

## Resumen de una sola línea por fase

| Fase | Quién | IA o manual (lo que manda) |
|---|---|---|
| 0. Preparación | Todos juntos | Manual |
| 1. Construcción | Cada quien, su rama | IA para el código, manual para revisar antes de comitear |
| 2. Integración | Cruzado (nunca quien lo escribió) | Manual (la revisión), automático (el CI) |
| 3. Experimentación | Con `main` ya integrado | Manual ejecutar y capturar, IA para ayudar a interpretar |
| 4. Documentación | README con IA + datos reales; ACTIVIDADES cada quien; pptx corto opcional para sustentación | Mixto, con el número real siempre verificado a mano |
| 5. Sustentación | Todos | Manual |

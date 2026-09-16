# Pendientes al cierre de esta sesión (2026-09-16)

Nota de handoff para que otra sesión retome sin tener que re-derivar el estado desde cero.
Rama de trabajo: `feature/entrega-parcial-pagos-disp02-mod02-esc01` (no mergeada a `main`, sin PR
abierto todavía — GitHub deja el link listo en el output de `git push`). Último commit al cierre:
`007779d`.

## 1. Estado de las 5 tareas del plan de corrección (`1_prompt_final_enfocado.md`)

| Tarea | Estado |
|---|---|
| 0 — Quitar ESC-02/ESC-03 | ✅ Completa (commit `c0d3fa0`) |
| 1 — Separar Pagos en microservicio | ✅ Completa (commit `567604e`) |
| 2 — DISP-02 (throttler → CRM) | ✅ Completa y **pasa** su umbral (ver `RESULTADOS-DISP02.md`, veredicto global) |
| 3 — MOD-02 (reglas regionales) | ✅ Completa y **pasa** (ver `RESULTADOS-MOD02.md`) |
| 4 — ESC-01 (<2s) | ⚠️ **No pasa todavía** — ver sección 2 abajo. No es un blocker de "proyecto roto", es un umbral documentado honestamente sin forzar el resultado (así lo permite la propia Tarea 4, punto 4). |

Tests unitarios de los 4 microservicios verificados el 2026-09-16 y **todos pasan**:
`gestion-de-trabajos` 21/21, `pagos` 17/17, `DISP-03` 17/17, `reputacion` 9/9.

## 2. ESC-01 — qué falta para que pase

- Última corrida local completa (~10.9min, no la versión corta): p95 **7,869ms** vs. umbral
  **<2,000ms**, 2.08% de fallo HTTP. En GCP real (2026-09-14): 9,717ms. Ambas ya con el pool de
  conexiones subido a 50/50 y hecho configurable por env var (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`/
  `DB_POOL_TIMEOUT`, ver `gestion-de-trabajos/app/common/db.py`).
- El pool ya no es sospechoso como único cuello de botella (subirlo no cerró la brecha). Candidatos
  sin confirmar, en orden de sospecha (ver `RESULTADOS-ESCALABILIDAD-GCP.md` sección 3, punto 1 y
  `k6/README.md` "Qué falta"):
  1. Tier de Cloud SQL `db-custom-1-3840` saturado bajo el pico real.
  2. `max_instance_count=10` / `containerConcurrency=80` del módulo Cloud Run insuficientes.
- Próximo paso concreto: perfilar métricas nativas de Cloud SQL (conexiones activas, CPU) durante
  una corrida de ESC-01 real contra GCP, y/o subir `containerConcurrency`/`max_instance_count` antes
  de gastar más esfuerzo en el pool.
- `k6/README.md` (tabla de resultados al final) **sigue con placeholders `TBD`** y con una tabla de
  "GCP real" que no incluye la corrida local completa post-pool-fix — quedó desincronizado, no se
  tocó en esta sesión por alcance. Actualizarlo junto con la próxima corrida real.

## 3. Documentos pedidos pero no generados (a propósito)

El propio `1_prompt_final_enfocado.md` dice explícitamente que README y `ACTIVIDADES.md` "van en 2
prompts separados — pídelos aparte", así que no se generaron sin pedido explícito:

- **`ACTIVIDADES.md`** (raíz del repo) — spec completa en `2_prompt_solo_actividades.md`. Atribuye
  trabajo real a personas por nombre vía `git log`/`gh pr list`; conviene correrlo con `gh`
  autenticado y confirmar antes de comitear algo que le asigna trabajo a compañeros.
- **`experimento-arquitectura/implementacion/README.md`** — spec en `3_prompt_solo_readme.md`. Ese
  prompt asume que las tareas 0-4 ya están aplicadas en `main`; hoy siguen solo en esta rama sin
  mergear, así que conviene decidir si se genera contra la rama o se espera al merge.

## 4. Otros pendientes previos, no tocados en esta sesión (heredados de sesiones anteriores)

- `escenarios_calidad.md`: **6 de 9 escenarios** (ESC-02*, ESC-03*, MOD-01, MOD-03, DISP-01, DISP-02)
  siguen sin los campos 7-11 de la Regla 2 (decisión arquitectural, puntos de sensibilidad,
  tradeoffs, riesgos, rationale+diagrama) — solo ESC-01 y DISP-03 los tienen completos. (*ESC-02/03
  fuera de alcance del proyecto, pero la fila puede seguir en el documento histórico — confirmar si
  toca borrarla también ahí.)
- `06-vista-cyc.puml` todavía nombra el tópico `trabajo.completado` (`T4`) con consumidores
  `Reputación`/`Scoring` — nomenclatura vieja; el plan de Entrega 4 lo renombra a
  `trabajos.finalizado` con consumidores **Proveedores** y **Reputación**. Ver pendiente #7 en
  `escenarios_calidad.md`.
- `07-vista-informacion.puml` no tiene `Moneda`/`Pais` explícitos aunque el código de `pagos/` ya
  los resolvió de facto (`Dinero.moneda`, `Region`) — ver "Veredicto" de `RESULTADOS-MOD02.md`.
- DISP-02: brechas 1-7 documentadas en el cierre de `RESULTADOS-DISP02.md` (carga sostenida real en
  vez de ráfaga desde pytest, modo caído/timeout en `mocks-crm`, coordinación del token bucket entre
  réplicas, etc.) — no bloquean el veredicto actual mientras se quede a escala de PoC.

## 5. Para retomar rápido

1. Leer este archivo primero.
2. Si vas a atacar ESC-01: empieza por `RESULTADOS-ESCALABILIDAD-GCP.md` sección 3 y
   `k6/README.md` "Qué falta" — no repitas el pool, ya se subió y se hizo configurable sin cerrar
   la brecha.
3. Si vas a generar `ACTIVIDADES.md` o el README: usa los prompts 2/3 tal cual están en
   `Downloads/`, decide primero si corren contra esta rama o contra `main` post-merge.
4. Borra este archivo (o su contenido ya resuelto) cuando los pendientes que lista queden cerrados
   — es una nota de traspaso, no documentación permanente del proyecto.

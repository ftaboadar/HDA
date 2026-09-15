# Pruebas de carga k6 — Escenarios de Escalabilidad (ESC-01, ESC-02, ESC-03)

Hogar de los Alpes (HdA) — Entrega 4, MISO 2026-14.

Fuente de los 3 escenarios: `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla
"Escalabilidad" (ESC-01/ESC-02/ESC-03). Regla de volúmenes: `REGLAS-DURAS-rubrica-entrega-3.md`,
Regla 3 (usar el mismo volumen del enunciado o mayor, compresión temporal permitida si se declara
el factor — mismo criterio ya usado en `DISP-03/plan.md` §5.4 y `DISP-03/RESULTADOS-DISP03.md`).

**Estado de este documento: código y smoke tests locales verificados; los valores de la tabla de
resultados al final son placeholders — no se ha corrido ninguna prueba a la escala real contra GCP
todavía.** Mismo estándar de honestidad que `DISP-03/RESULTADOS-DISP03.md`.

## Estructura

```
k6/
  lib/config.js   URLs base + umbrales/tasas de cada ESC-XX (una sola fuente de verdad)
  esc-01.js       ESC-01 — pico 4x en 48h (Gestión de Trabajos)
  esc-02.js       ESC-02 — 5x tráfico de un solo partner (DISP-03 / Verificación)
  esc-03.js       ESC-03 — crecimiento sostenido 3x (Gestión de Trabajos + DISP-03)
  results/        JSON crudo por corrida (`handleSummary`, uno por script, se sobrescribe)
```

## Qué mide cada script (resumen — el detalle completo y las derivaciones numéricas están en
el comentario de cabecera de cada archivo `.js`, léanlo antes de correr nada)

| Script | Contra | Mide | Sección fuente en `escenarios_calidad.md` |
|---|---|---|---|
| `esc-01.js` | `gestion-de-trabajos` (`POST /trabajos`) + `DISP03_URL/salud` como proxy de "otro dominio" | Latencia de aceptación <2s y ≥99.9% aceptación durante un pico 4x; variación de latencia de "otro dominio" (medida manual post-hoc, ver abajo) | Tabla Escalabilidad, columna ESC-01 |
| `esc-02.js` | DISP-03 (`POST /verificaciones`) | p95<300ms con 5x de tráfico en un `tipo_verificador` (proxy de "un partner"), sin degradar los otros dos | Tabla Escalabilidad, columna ESC-02 |
| `esc-03.js` | `gestion-de-trabajos` (`POST /trabajos`) + DISP-03 (`POST /verificaciones`) | p95<300ms sostenido durante un `ramp-up` gradual hasta 3x | Tabla Escalabilidad, columna ESC-03 |

## Factor de compresión temporal y derivación de tasas — por script

- **ESC-01**: escenario real de 48h → prueba de 12 minutos (factor ≈240x). Tasas: 289 req/s base →
  1157 req/s pico (derivadas de "+25M requests/día" → "100M+" = 25M×4, ver cabecera de `esc-01.js`
  para la justificación completa de esa lectura). La tasa NO se reduce, solo el tiempo total de
  exposición al pico.
- **ESC-02**: sin ventana de tiempo real que comprimir (es un pico "súbito"). Baseline de 10 req/s
  es un **supuesto explícito, no una cifra del enunciado** (el enunciado no da un volumen absoluto
  de "tráfico habitual de un partner") — lo fiel al enunciado es el multiplicador ×5 y el umbral
  p95<300ms. Ver cabecera de `esc-02.js`.
- **ESC-03**: escenario real de 3 años → prueba de 16 minutos (factor ≈98.550x). El piso literal
  del enunciado (12.000→36.000 trabajos/día ≈ 0,139→0,417 req/s) es real pero casi inmedible en
  minutos; se usa una tasa de prueba amplificada (5→15 req/s) que preserva el factor ×3 exacto y
  siempre queda por ENCIMA del piso (nunca por debajo — Regla 3). El crecimiento de proveedores
  (+45.000→+100.000 en 3 años) no tiene una tasa de solicitudes/segundo en el enunciado (son
  totales acumulados); se usa el mismo par 5→15 req/s como supuesto explícito. Ver cabecera de
  `esc-03.js`.

## Brechas documentadas (no rellenadas con decisiones de diseño ocultas)

1. **ESC-02 — "partner" no existe en la API de DISP-03.** `VerificacionCreate` solo tiene
   `proveedor_id` y `tipo_verificador` (`policia`/`rues`/`certificadora`); no hay `partner_id` ni
   rate limiting por partner en ningún Gateway del repo (DISP-01/DISP-02 en `escenarios_calidad.md`
   tienen su "Decisión arquitectural" marcada `*Pendiente*`). `esc-02.js` usa `tipo_verificador`
   como proxy de aislamiento (el mecanismo que sí existe: partición por tipo de verificador), no
   como una simulación real de rate limiting por partner de un Gateway. Detalle completo en la
   cabecera de `esc-02.js`.
2. **"< 5% de variación en latencia de otros dominios/partners durante el pico"** (ESC-01 y ESC-02)
   no se puede expresar como un `threshold` nativo de k6 — requiere comparar el p95 de una ventana
   "antes del pico" contra una ventana "durante el pico" en el JSON exportado a `results/`. Los
   scripts loguean todas las requests con timestamp (`console.log` JSON) y exportan el resumen
   completo para que ese cálculo se haga después; no es un veredicto automático.
3. **ESC-02 — "auto-escalamiento activo en <60s"** no se puede medir con k6 solo (k6 no lee el
   conteo de instancias de Cloud Run). La rampa a 5x en `esc-02.js` dura 45s a propósito (estímulo),
   pero confirmar el auto-escalamiento real requiere cruzar con métricas/logs de Cloud Run en
   paralelo a la corrida contra GCP.
4. **`gestion-de-trabajos` no tiene `docker-compose.yml` todavía** (confirmado en su propio
   README, sección "Cómo correrlo") — por instrucción explícita de este ejercicio, no se creó uno.
   Esto significa que `esc-01.js` y `esc-03.js` (que dependen de `gestion-de-trabajos`) solo se
   validaron por **sintaxis/lógica en modo `SMOKE`** (contra un puerto sin servidor arriba,
   confirmando que el script compila y su lógica de payloads/checks corre sin errores), NO contra
   una instancia real corriendo. `esc-02.js` sí se validó end-to-end contra DISP-03 real vía
   `docker-compose` (ver "Qué se validó de verdad" más abajo).

## Cómo correrlo — local (contra `docker-compose`)

```bash
# DISP-03 (sí tiene docker-compose.yml — API en :8000):
cd experimento-arquitectura/implementacion/DISP-03
docker compose up -d --build

# gestion-de-trabajos (NO tiene docker-compose.yml hoy — requiere Postgres/Pulsar
# accesibles a mano y `uvicorn app.api.main:app --port 8001`, ver su propio README).

cd experimento-arquitectura/implementacion/k6

# Smoke test (pocos VUs/segundos, valida sintaxis/lógica, NO el escenario real):
k6 run -e SMOKE=true -e DISP03_URL=http://localhost:8000 -e GESTION_TRABAJOS_URL=http://localhost:8001 \
  --vus 2 --duration 10s esc-02.js

# Corrida real del escenario completo (usa las tasas/duraciones reales de cada ESC-XX,
# ignora --vus/--duration porque el script define sus propios `scenarios`):
k6 run -e DISP03_URL=http://localhost:8000 esc-02.js
k6 run -e GESTION_TRABAJOS_URL=http://localhost:8001 -e DISP03_URL=http://localhost:8000 esc-01.js
k6 run -e GESTION_TRABAJOS_URL=http://localhost:8001 -e DISP03_URL=http://localhost:8000 esc-03.js
```

## Cómo correrlo — contra GCP real

Mismas variables de entorno, apuntando a las URLs de Cloud Run desplegadas (ver
`DISP-03/infra/outputs.tf` → `terraform output api_url`, y el output equivalente del servicio
`gestion-de-trabajos` cuando su infra esté desplegada — gestionada aparte, no forma parte de este
ejercicio):

```bash
DISP03_URL=$(cd ../DISP-03/infra && terraform output -raw api_url)

k6 run -e DISP03_URL="$DISP03_URL" -e GESTION_TRABAJOS_URL="https://<cloud-run-url-gestion-trabajos>" \
  esc-01.js
k6 run -e DISP03_URL="$DISP03_URL" esc-02.js
k6 run -e DISP03_URL="$DISP03_URL" -e GESTION_TRABAJOS_URL="https://<cloud-run-url-gestion-trabajos>" \
  esc-03.js
```

Recomendado: correr con `--out json=results/esc-XX-raw.jsonl` además del `handleSummary` que ya
exporta cada script, para tener el detalle punto-a-punto de cada request si se necesita
diagnosticar un umbral incumplido.

## Qué se validó de verdad en esta sesión (smoke test local)

- **`esc-02.js` contra DISP-03 real** (`docker compose up -d --build` en `DISP-03/`, API sana en
  `GET /salud`): corrido con `k6 run -e SMOKE=true --vus 2 --duration 10s -e
  DISP03_URL=http://localhost:8000 esc-02.js` — 3896 iteraciones completas, **100% `202` en
  `POST /verificaciones`** para los 3 `tipo_verificador` (`policia`, `rues`, `certificadora`), sin
  errores de payload ni de ruta. Esto confirma que el contrato HTTP real (`VerificacionCreate`) y
  la lógica del script coinciden.
- **`esc-01.js` y `esc-03.js`**: validados solo en modo `SMOKE` contra puertos sin servidor arriba
  (`connection refused` esperado) — confirma que el JS compila, que `handleSummary` genera el JSON
  de salida, y que la lógica de checks/logs no lanza excepciones. **No** se validó su comportamiento
  contra una instancia real de `gestion-de-trabajos`, por la brecha #4 de arriba.
- No se corrió ninguna prueba a la escala/tasa real (289–1157 req/s, etc.) contra ningún entorno —
  eso es explícitamente trabajo de una corrida real posterior (local a baja escala primero, luego
  GCP), no de este smoke test.

## Plantilla de resultados (placeholders — llenar después de correr de verdad)

> Todos los valores de abajo son `TBD`. No reemplazar por números inventados; dejar `TBD` hasta
> tener una corrida real registrada, con fecha, entorno y comando exacto usado — mismo estándar que
> `DISP-03/RESULTADOS-DISP03.md`.

### ESC-01 — Pico 4x en 48h

| Entorno | Fecha | p95 aceptación medido | Throughput medido (req/s) | % aceptación medido | Variación p95 "otro dominio" | Veredicto cumple/no-cumple |
|---|---|---|---|---|---|---|
| Local (docker-compose) | TBD | TBD | TBD | TBD | TBD | *(responsabilidad de `validador-hipotesis`, no de este documento)* |
| GCP real | TBD | TBD | TBD | TBD | TBD | *(idem)* |

### ESC-02 — 5x tráfico de un partner

| Entorno | Fecha | p95 partner en pico | p95 otros partners | Auto-scaling medido (s) | % rate limiting a otros | Veredicto cumple/no-cumple |
|---|---|---|---|---|---|---|
| Local (docker-compose) | TBD | TBD | TBD | N/A (sin auto-scaling local) | TBD | *(responsabilidad de `validador-hipotesis`)* |
| GCP real | TBD | TBD | TBD | TBD | TBD | *(idem)* |

### ESC-03 — Crecimiento sostenido 3x

| Entorno | Fecha | p95 trabajos (1x → 3x) | p95 proveedores (1x → 3x) | Throughput sostenido medido | Veredicto cumple/no-cumple |
|---|---|---|---|---|---|
| Local (docker-compose) | TBD | TBD | TBD | TBD | *(responsabilidad de `validador-hipotesis`)* |
| GCP real | TBD | TBD | TBD | TBD | *(idem)* |

## Referencias

- Escenarios fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`
- Regla de volúmenes: `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3
- Precedente de compresión temporal declarada: `experimento-arquitectura/implementacion/DISP-03/plan.md` §5.4
- Decisión de reincorporar observabilidad (Prometheus/Grafana) a raíz de esta estrategia de pruebas:
  `experimento-arquitectura/contexto/14-estrategia-pruebas-carga-k6.md`

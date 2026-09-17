# Pruebas de carga k6 — Escenario de Escalabilidad (ESC-01)

Hogar de los Alpes (HdA) — Entrega 4, MISO 2026-14.

Fuente del escenario: `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla
"Escalabilidad", columna ESC-01. Regla de volúmenes: `REGLAS-DURAS-rubrica-entrega-3.md`,
Regla 3 (usar el mismo volumen del enunciado o mayor, compresión temporal permitida si se declara
el factor — mismo criterio ya usado en `DISP-03/plan.md` §5.4 y `DISP-03/RESULTADOS-DISP03.md`).

**Nota de alcance**: ESC-02 y ESC-03 se quitaron del alcance acordado del equipo — solo ESC-01
forma parte de la entrega. Sus scripts y resultados fueron removidos de este directorio.

**Estado de este documento: código y smoke tests locales verificados; los valores de la tabla de
resultados al final son placeholders — no se ha corrido ninguna prueba a la escala real contra GCP
todavía.** Mismo estándar de honestidad que `DISP-03/RESULTADOS-DISP03.md`.

## Estructura

```
k6/
  lib/config.js   URLs base + umbrales/tasas de ESC-01 (una sola fuente de verdad)
  esc-01.js       ESC-01 — pico 4x en 48h (Gestión de Trabajos)
  results/        JSON crudo por corrida (`handleSummary`, se sobrescribe)
```

## Qué mide el script (resumen — el detalle completo y las derivaciones numéricas están en
el comentario de cabecera de `esc-01.js`, léanlo antes de correr nada)

| Script | Contra | Mide | Sección fuente en `escenarios_calidad.md` |
|---|---|---|---|
| `esc-01.js` | `gestion-de-trabajos` (`POST /trabajos`) + `DISP03_URL/salud` como proxy de "otro dominio" | Latencia de aceptación <2s y ≥99.9% aceptación durante un pico 4x; variación de latencia de "otro dominio" (medida manual post-hoc, ver abajo) | Tabla Escalabilidad, columna ESC-01 |

## Factor de compresión temporal y derivación de tasas

- **ESC-01**: escenario real de 48h → prueba de 12 minutos (factor ≈240x). Tasas: 289 req/s base →
  1157 req/s pico (derivadas de "+25M requests/día" → "100M+" = 25M×4, ver cabecera de `esc-01.js`
  para la justificación completa de esa lectura). La tasa NO se reduce, solo el tiempo total de
  exposición al pico.

## Brechas documentadas (no rellenadas con decisiones de diseño ocultas)

1. **"< 5% de variación en latencia de otros dominios durante el pico"** (ESC-01) no se puede
   expresar como un `threshold` nativo de k6 — requiere comparar el p95 de una ventana "antes del
   pico" contra una ventana "durante el pico" en el JSON exportado a `results/`. El script loguea
   todas las requests con timestamp (`console.log` JSON) y exporta el resumen completo para que ese
   cálculo se haga después; no es un veredicto automático.
2. **`gestion-de-trabajos` no tiene `docker-compose.yml` todavía** (confirmado en su propio
   README, sección "Cómo correrlo") — por instrucción explícita de este ejercicio, no se creó uno.
   Esto significa que `esc-01.js` solo se validó por **sintaxis/lógica en modo `SMOKE`** (contra un
   puerto sin servidor arriba, confirmando que el script compila y su lógica de payloads/checks
   corre sin errores), NO contra una instancia real corriendo.

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
  --vus 2 --duration 10s esc-01.js

# Corrida real del escenario completo (usa las tasas/duración reales de ESC-01,
# ignora --vus/--duration porque el script define sus propios `scenarios`):
k6 run -e GESTION_TRABAJOS_URL=http://localhost:8001 -e DISP03_URL=http://localhost:8000 esc-01.js
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
```

Recomendado: correr con `--out json=results/esc-01-raw.jsonl` además del `handleSummary` que ya
exporta el script, para tener el detalle punto-a-punto de cada request si se necesita
diagnosticar un umbral incumplido.

### Por qué correr k6 desde una VM y no en local

`esc-01.js` usa el executor `ramping-arrival-rate` con `preAllocatedVUs: 200`/`maxVUs: 2000`
(modelo abierto: sostiene la tasa objetivo, hasta 1157 req/s en el pico, sin importar cuánto
tarden en responder las requests en vuelo). Con las latencias ya observadas contra GCP real bajo
el escenario sin corregir (p95 de varios segundos, picos de hasta ~60s), sostener esa tasa exige
mantener miles de conexiones TCP/TLS concurrentes abiertas. Corrido desde una laptop en una red
doméstica, ese volumen de conexiones satura la tabla de NAT/conntrack (y la CPU) del router de
consumo — tumba la conectividad de **toda** la red, no solo la de k6. Confirmado en esta sesión:
correrlo en local contra las URLs de Cloud Run dejó sin red al resto de dispositivos de la casa.

La corrida **local contra `docker-compose`** (sección de arriba) no tiene este problema — ese
tráfico nunca sale de la máquina/red Docker interna. El problema es específico de apuntar
`esc-01.js` a URLs públicas de Cloud Run desde una conexión residencial.

**Solución**: `infra/` en este mismo directorio provisiona una VM de Compute Engine en
`southamerica-east1` (misma región que el resto de los stacks) con k6 preinstalado y
`esc-01.js`/`lib/config.js` embebidos tal cual — la carga sale desde la red de Google directo
hacia Cloud Run, sin pasar por ningún router doméstico, y de paso da una medición más realista
(sin la latencia/jitter de la conexión del desarrollador metida en el resultado).

```bash
cd infra
terraform init
terraform apply -var project_id=hda-projectt   # recursos facturables — confirmar antes de aplicar

# entrar y correr la prueba:
$(terraform output -raw ssh_iap_command)
#   dentro de la VM:
#   cd /opt/k6-runner
#   k6 run -e DISP03_URL="..." -e GESTION_TRABAJOS_URL="..." --out json=results/esc-01-raw.jsonl esc-01.js

# traer los resultados de vuelta:
$(terraform output -raw scp_resultados_command)

terraform destroy -var project_id=hda-projectt   # apagar la VM cuando ya no se necesite
```

## Qué se validó de verdad en esta sesión (smoke test local)

- **`esc-01.js`**: validado solo en modo `SMOKE` contra un puerto sin servidor arriba
  (`connection refused` esperado) — confirma que el JS compila, que `handleSummary` genera el JSON
  de salida, y que la lógica de checks/logs no lanza excepciones. **No** se validó su comportamiento
  contra una instancia real de `gestion-de-trabajos`, por la brecha #2 de arriba.
- No se corrió ninguna prueba a la escala/tasa real (289–1157 req/s) contra ningún entorno —
  eso es explícitamente trabajo de una corrida real posterior (local a baja escala primero, luego
  GCP), no de este smoke test.

## Resultados (última actualización: 2026-09-17)

Mismo estándar que `DISP-03/RESULTADOS-DISP03.md`: solo números de corridas reales, nunca
inventados. Detalle completo, diagnóstico en cadena y la anomalía sin resolver del tier de Cloud
SQL: `../RESULTADOS-ESCALABILIDAD-GCP.md`, sección 1.1.1.

### ESC-01 — Pico 4x en 48h

| Entorno | Fecha | p95 aceptación medido | Throughput medido (req/s) | % aceptación medido | Veredicto cumple/no-cumple |
|---|---|---|---|---|---|
| Local (docker-compose, duración completa ~10.9min, pool 50/50) | 2026-09-16 | 7869ms | 333 req/s | 97.9% | *(responsabilidad de `validador-hipotesis`, no de este documento)* |
| GCP real (2026-09-14, 1ª corrida, antes del fix de concurrencia) | 2026-09-14 | 14208ms | 216 req/s | 79.9% | No cumple |
| GCP real (2026-09-14, 2ª corrida, después del fix `asyncio.to_thread`) | 2026-09-14 | 9717ms | 326 req/s | 88.1% | No cumple |
| GCP real, corrida desde `k6-runner-poc-vm` (2026-09-16, concurrency=15/15/15 sincronizado, sin `min_instance_count`) | 2026-09-16 | 9991ms | 543 req/s | 85.8% | No cumple |
| **GCP real, + `min_instance_count=10`** (2026-09-16) | 2026-09-16 | **5646ms** | 544 req/s | **100%** | No cumple, pero es la mejor corrida real — 0% de fallo |
| GCP real, + Cloud SQL 4 vCPU (2026-09-17, ver anomalía) | 2026-09-17 | 7521ms | 668 req/s | 96.3% | No cumple — tier más grande empeoró, sin causa confirmada |

**Qué falta (ESC-01, honesto a propósito):** con la sobresuscripción de conexiones y el cold-start
del autoscaler ya resueltos (ver `RESULTADOS-ESCALABILIDAD-GCP.md` sección 1.1.1), la mejor corrida
real sigue en 5.6s de p95 contra un umbral de 2s. Cloud SQL (2 vCPU) queda al 99.5% de CPU en esa
corrida — el cuello de botella real hoy. Subir a 4 vCPU debería ayudar y en cambio empeoró de forma
reproducible (3 corridas), por una causa no confirmada. Queda para quien retome esto: instrumentar
latencia interna del código (no solo métricas de infra) para aislar por qué más cómputo en Postgres
empeora el resultado en Cloud Run.

## Referencias

- Escenarios fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`
- Regla de volúmenes: `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3
- Precedente de compresión temporal declarada: `experimento-arquitectura/implementacion/DISP-03/plan.md` §5.4
- Decisión de reincorporar observabilidad (Prometheus/Grafana) a raíz de esta estrategia de pruebas:
  `experimento-arquitectura/contexto/14-estrategia-pruebas-carga-k6.md`

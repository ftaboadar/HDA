# 14 — Estrategia de pruebas de carga (k6) para los escenarios de Escalabilidad

Hogar de los Alpes (HdA) — Entrega 4, MISO 2026-14. Versión resumida para el equipo; el detalle
completo (derivaciones numéricas, factores de compresión temporal, limitaciones por script) vive en
`experimento-arquitectura/implementacion/k6/README.md` y en el comentario de cabecera de cada
`esc-XX.js`.

## Qué se decidió

- **Herramienta**: k6, para instrumentar los 3 escenarios de Escalabilidad (ESC-01, ESC-02, ESC-03
  de `escenarios_calidad.md`) con carga real, no solo con la descripción textual del atributo de
  calidad.
- **Por qué k6**: scripting en JavaScript (fácil de mantener por el equipo sin herramienta nueva de
  infraestructura), soporte nativo de `thresholds` que mapean 1:1 contra las "medidas de la
  respuesta" ya redactadas en `escenarios_calidad.md` (p95, tasas de aceptación/fallo), y
  ejecutores (`ramping-arrival-rate`, `constant-arrival-rate`) que permiten modelar tanto un pico
  (ESC-01, ESC-02) como un `ramp-up` gradual (ESC-03) sin escribir el driver de carga a mano.
- **Quién lo pidió**: decisión de equipo para Entrega 4, ejecutada en la rama
  `feature/k6-y-gcp-integral` (ver `experimento-arquitectura/implementacion/k6/`).

## Qué mide cada script (resumen — detalle completo en `k6/README.md`)

| Script | Escenario | Servicio bajo prueba | Qué valida |
|---|---|---|---|
| `k6/esc-01.js` | ESC-01 | `gestion-de-trabajos` (`POST /trabajos`) | Pico 4x en 48h (comprimido a 12 min de prueba): latencia de aceptación <2s y ≥99.9% de solicitudes aceptadas |
| `k6/esc-02.js` | ESC-02 | DISP-03 / Verificación (`POST /verificaciones`) | 5x de tráfico de un solo "partner" (proxy: `tipo_verificador`, ver brecha documentada abajo): p95<300ms sin degradar los otros tipos |
| `k6/esc-03.js` | ESC-03 | `gestion-de-trabajos` + DISP-03 | Crecimiento sostenido 3x (comprimido a 16 min de prueba), con `ramp-up` gradual de 4 escalones: p95<300ms sostenido |

Los 3 scripts comparten `k6/lib/config.js` (URLs base parametrizables por variable de entorno y
umbrales/tasas como constantes, una sola fuente de verdad) y soportan un modo `SMOKE=true` para
validar sintaxis/lógica con muy pocos VUs/segundos sin correr el escenario a escala real.

## Brecha explícita de ESC-02 — "partner" no existe en la API de DISP-03 hoy

El contrato HTTP real (`VerificacionCreate`) no tiene un campo `partner_id`, y ningún servicio del
repo implementa rate limiting por partner en un Gateway (DISP-01/DISP-02 en `escenarios_calidad.md`
tienen su "Decisión arquitectural" pendiente). `esc-02.js` usa el mecanismo de aislamiento que sí
existe hoy — partición por `tipo_verificador` — como proxy, y lo documenta explícitamente como una
aproximación, no como una simulación real de un Gateway con rate limiting por partner. Antes de
reportar resultados de ESC-02 como concluyentes, esa brecha debería cerrarse en el diseño (un
Gateway/BFF real con noción de partner) o aceptarse formalmente como parte del alcance del PoC.

## Volúmenes y compresión temporal (Regla 3)

Cada script usa el volumen del enunciado como piso (nunca uno menor), con compresión temporal
declarada explícitamente cuando el escenario real dura más de lo práctico para una corrida de
prueba — mismo criterio ya aplicado en `proveedores/plan.md` §5.4:

- ESC-01: 48h reales → 12 min de prueba (factor ≈240x), tasa objetivo sin reducir (289→1157 req/s).
- ESC-02: sin ventana temporal que comprimir (pico súbito); baseline de tráfico "habitual de un
  partner" es un supuesto explícito (el enunciado no da esa cifra absoluta), el multiplicador ×5 y
  el umbral p95<300ms sí son fieles al enunciado.
- ESC-03: 3 años reales → 16 min de prueba (factor ≈98.550x), con una tasa de prueba amplificada
  por encima del piso literal del enunciado (que es casi inmedible en minutos), preservando el
  factor de crecimiento ×3 exacto.

## Prometheus/Grafana vuelven a estar en alcance

En la Entrega 3, `REGLAS-DURAS-rubrica-entrega-3.md` (Regla 5) dejaba registrado explícitamente:
*"Kafka/Prometheus/Postman/JMeter de la propuesta original quedaron fuera de alcance a propósito
(no los exige la rúbrica)"*. Esta decisión se **revierte** a partir de esta estrategia de pruebas de
carga: correr los 3 escenarios ESC-XX contra infraestructura real (local y GCP) sin poder observar
métricas de sistema (CPU, memoria, conteo de instancias, latencia por servicio) deja las brechas
#2 y #3 documentadas en `k6/README.md` (variación de latencia entre dominios/partners,
auto-escalamiento medido) sin forma de cerrarse solo con los `thresholds` de k6.

La infraestructura de observabilidad (Prometheus/Grafana) que cierra esa brecha la documenta y
construye otro agente en paralelo — este documento solo referencia dónde vive:
`experimento-arquitectura/implementacion/observabilidad/`. No se detallan aquí decisiones de
despliegue, dashboards ni scraping que no fueron tomadas en esta sesión.

## Referencias

- Escenarios fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`
- Regla de volúmenes: `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3
- Nota revertida de "fuera de alcance": `REGLAS-DURAS-rubrica-entrega-3.md`, fila "Implementación de
  un servicio DDD + eventos (Regla 5)"
- Código y detalle completo: `experimento-arquitectura/implementacion/k6/`
- Observabilidad (Prometheus/Grafana): `experimento-arquitectura/implementacion/observabilidad/`
  (construida en paralelo, fuera del alcance de este documento)

/**
 * ESC-01 — Pico climático 4x en 48h (Gestión de Trabajos)
 * Fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla
 * "Escalabilidad", columna ESC-01.
 *
 * Qué mide:
 *   - Escenario `pico_siniestros`: ráfaga de `POST /trabajos` contra
 *     `gestion-de-trabajos`, simulando el ingreso de siniestros que crean
 *     trabajos, con un perfil de carga que sube de tráfico normal a 4x pico
 *     y vuelve a bajar (no un escalón instantáneo).
 *   - Escenario `otros_dominios_baseline`: tráfico constante y bajo contra
 *     `GET {DISP03_URL}/salud`, corriendo en paralelo durante TODA la prueba,
 *     como proxy de "otro dominio" para poder comparar su latencia
 *     antes/durante/después del pico (ver limitación abajo).
 *
 * Mapeo a ESC-01 (medida de la respuesta, textual):
 *   "Latencia de aceptación < 2s en pico; ≥ 99.9% de solicitudes aceptadas
 *   en pico; < 5% de variación en latencia de los demás dominios durante
 *   el pico".
 *   - Latencia de aceptación < 2s  → threshold `http_req_duration{scenario:pico_siniestros}`.
 *   - ≥ 99.9% aceptadas            → threshold `http_req_failed{scenario:pico_siniestros}` (rate < 0.001).
 *   - < 5% variación otros dominios → NO se puede expresar como threshold nativo de k6
 *     (requiere comparar el p95 de `otros_dominios_baseline` en la ventana
 *     "antes del pico" vs. "durante el pico", algo que k6 no calcula solo).
 *     Este script exporta el resumen completo (`handleSummary`) y logs con
 *     timestamp por request (`console.log` JSON) para que ese cálculo se
 *     haga después, comparando ventanas de tiempo — no es un veredicto
 *     automático de este script.
 *
 * Factor de compresión temporal (Regla 3, ver también DISP-03 §5.4 como
 * precedente ya aceptado en el proyecto):
 *   El escenario real dura 48h. Esta prueba comprime esas 48h a 12 minutos
 *   de duración total (2m subida + 3m rampa a pico + 5m sostenido en pico +
 *   2m bajada), factor de compresión ≈ (48h × 60) / 12min = 240x.
 *   Lo que NO se comprime es el volumen/tasa instantánea exigida: las tasas
 *   de arribo (289 req/s base, 1157 req/s pico) son las mismas que exige el
 *   enunciado (ver `lib/config.js`, derivación completa), no una fracción
 *   reducida de ellas. Es razonable comprimir el tiempo total de exposición
 *   (nadie necesita sostener el pico real durante 48 horas para validar que
 *   el mecanismo de aceptación asíncrona sostiene la tasa objetivo) sin
 *   comprimir la tasa misma, que es la variable que el escenario protege.
 *
 * Lectura de "+25M requests/día en crecimiento hacia 100M+" (documentada
 * explícitamente porque no es la única lectura posible del texto):
 *   Se interpreta que 25M req/día es el tráfico total de PLATAFORMA hoy, y
 *   que el pico de 4x citado en el mismo estímulo lleva ese tráfico a 100M
 *   req/día (25M × 4 = 100M, coincide exactamente con el "100M+" que el
 *   propio estímulo usa como destino del crecimiento) — no dos cifras
 *   independientes. `POST /trabajos` de `gestion-de-trabajos` es el
 *   artefacto explícito de ESC-01 y se usa aquí como el endpoint
 *   representativo de ese tráfico total, aunque en la arquitectura real ese
 *   tráfico se reparta entre varios servicios/endpoints — brecha de
 *   representatividad documentada, no oculta.
 *
 * LIMITACIÓN DE ESCALA DEL POC (análoga a la ya aceptada en
 * `DISP-03/RESULTADOS-DISP03.md`): 1157 req/s sostenidos requiere
 * infraestructura con auto-scaling real (Cloud Run) y una base de datos que
 * soporte esa concurrencia; contra un solo contenedor de `uvicorn` en
 * docker-compose local, es esperable que el PoC no sostenga esa tasa y que
 * el cuello de botella aparezca en la app o en Postgres antes que en el
 * mecanismo de aceptación asíncrona en sí. Eso es exactamente lo que este
 * script debe revelar al correr contra GCP real vs. local — no se ocultó
 * bajando la tasa objetivo.
 */

import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';
import {
  GESTION_TRABAJOS_URL,
  DISP03_URL,
  ESC01,
  buildOptions,
} from './lib/config.js';

const aceptacionOk = new Rate('esc01_aceptacion_ok');

const REGIONES = ['CO', 'BR'];

const scenarios = {
  pico_siniestros: {
    executor: 'ramping-arrival-rate',
    startRate: 0,
    timeUnit: '1s',
    preAllocatedVUs: 200,
    maxVUs: 2000,
    stages: [
      { target: ESC01.BASE_RPS, duration: '2m' }, // sube a tráfico normal
      { target: ESC01.PEAK_RPS, duration: '3m' }, // ráfaga hacia el pico 4x
      { target: ESC01.PEAK_RPS, duration: '5m' }, // sostiene el pico (48h reales comprimidas, ver cabecera)
      { target: ESC01.BASE_RPS, duration: '2m' }, // vuelve a tráfico normal
    ],
    exec: 'crearTrabajo',
  },
  otros_dominios_baseline: {
    executor: 'constant-arrival-rate',
    rate: 1,
    timeUnit: '1s',
    duration: '12m', // misma duración total que pico_siniestros
    preAllocatedVUs: 5,
    maxVUs: 20,
    exec: 'probarOtroDominio',
  },
};

const thresholds = {
  'http_req_duration{scenario:pico_siniestros}': [`p(95)<${ESC01.P95_ACEPTACION_MS}`],
  'http_req_failed{scenario:pico_siniestros}': [
    `rate<${(1 - ESC01.TASA_ACEPTACION_MIN).toFixed(4)}`,
  ],
  esc01_aceptacion_ok: [`rate>=${ESC01.TASA_ACEPTACION_MIN}`],
};

export const options = buildOptions(scenarios, thresholds);

// Usado solo en modo SMOKE (`-e SMOKE=true`), donde `options` no define
// `scenarios` y k6 exige una función `default`. Fuera de modo smoke, la
// carga real usa `exec: 'crearTrabajo'` / `exec: 'probarOtroDominio'` desde
// `scenarios`, y esta función no se ejecuta.
export default function () {
  crearTrabajo();
  probarOtroDominio();
}

export function crearTrabajo() {
  const payload = JSON.stringify({
    proveedor_id: `prov-${__VU}-${__ITER}`,
    monto: (Math.random() * 500 + 10).toFixed(2),
    region: REGIONES[Math.floor(Math.random() * REGIONES.length)],
  });
  const params = { headers: { 'Content-Type': 'application/json' } };

  const inicio = Date.now();
  const res = http.post(`${GESTION_TRABAJOS_URL}/trabajos`, payload, params);
  const latenciaMs = Date.now() - inicio;

  const ok = check(res, {
    'trabajo aceptado (201)': (r) => r.status === 201,
  });
  aceptacionOk.add(ok);

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-01',
      caso: 'pico_siniestros',
      status: res.status,
      latencia_ms: latenciaMs,
      aceptado: ok,
    })
  );
}

export function probarOtroDominio() {
  const inicio = Date.now();
  const res = http.get(`${DISP03_URL}/salud`);
  const latenciaMs = Date.now() - inicio;

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-01',
      caso: 'otros_dominios_baseline',
      status: res.status,
      latencia_ms: latenciaMs,
    })
  );
}

export function handleSummary(data) {
  // No usamos textSummary de jslib.k6.io a propósito (evita depender de red
  // externa durante la corrida) — imprimimos solo las métricas clave y
  // dejamos el JSON completo en `results/` para análisis posterior.
  const m = data.metrics;
  const resumen = {
    escenario: 'ESC-01',
    p95_aceptacion_ms: m['http_req_duration{scenario:pico_siniestros}']
      ? m['http_req_duration{scenario:pico_siniestros}'].values['p(95)']
      : null,
    tasa_fallo_pico: m['http_req_failed{scenario:pico_siniestros}']
      ? m['http_req_failed{scenario:pico_siniestros}'].values.rate
      : null,
    iteraciones_totales: m.iterations ? m.iterations.values.count : null,
  };
  console.log(`\n[ESC-01] Resumen: ${JSON.stringify(resumen)}\n`);
  return {
    'results/esc-01-summary.json': JSON.stringify(data, null, 2),
  };
}

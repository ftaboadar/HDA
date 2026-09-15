/**
 * ESC-03 — Crecimiento sostenido 3x por expansión LATAM (Gestión de Trabajos + Verificación)
 * Fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla
 * "Escalabilidad", columna ESC-03.
 *
 * Qué mide:
 *   - Escenario `trabajos_crecimiento`: `POST /trabajos` contra
 *     `gestion-de-trabajos`, con un `ramp-up` de 4 escalones (no un salto
 *     instantáneo) que refleja la entrada gradual y simultánea a México,
 *     Brasil y Argentina citada en el estímulo, hasta sostener 3x el
 *     tráfico base.
 *   - Escenario `proveedores_crecimiento`: `POST /verificaciones` contra
 *     DISP-03, con el mismo perfil de `ramp-up` en paralelo, como proxy del
 *     crecimiento de +45.000 → +100.000 proveedores registrados.
 *
 * Mapeo a ESC-03 (medida de la respuesta, textual):
 *   "El sistema sostiene 36.000 trabajos/día y +100.000 proveedores
 *   manteniendo el mismo SLA de latencia (p95 < 300ms) que hoy con 12.000
 *   trabajos/día".
 *   - p95 < 300ms sostenido durante y después de la rampa a 3x → thresholds
 *     `http_req_duration{scenario:trabajos_crecimiento}` y
 *     `http_req_duration{scenario:proveedores_crecimiento}`.
 *   - "mismo SLA que hoy" → se compara el p95 de la primera etapa (tráfico
 *     base, 1x) contra el de la última etapa (3x sostenido) en el JSON de
 *     `handleSummary`; k6 no calcula esa comparación de ventanas por sí
 *     solo, queda para análisis posterior (mismo patrón que ESC-01/ESC-02).
 *
 * Derivación de tasas y AMPLIFICACIÓN documentada (Regla 3 — "igual o mayor
 * volumen que el enunciado", nunca menor; ver `lib/config.js` para el
 * detalle numérico completo):
 *   - Piso literal del enunciado (trabajos): 12.000/día ≈ 0,139 req/s base,
 *     36.000/día ≈ 0,417 req/s en pico (×3). Estas tasas son reales pero
 *     casi inmedibles en una ventana de prueba de minutos.
 *   - Tasa de prueba usada en este script: 5 req/s base → 15 req/s pico
 *     (también ×3, mismo factor de crecimiento del enunciado), muy por
 *     ENCIMA del piso literal — cumple Regla 3 sin necesidad de estirar la
 *     prueba a una duración poco práctica para poder medir 0,139 req/s de
 *     forma confiable.
 *   - Para "+45.000 → +100.000 proveedores en 3 años" NO hay una tasa de
 *     solicitudes/segundo en el enunciado (son totales acumulados, no un
 *     flujo diario) — se usa el mismo par 5→15 req/s como SUPUESTO
 *     documentado, no como una cifra derivada matemáticamente del dato de
 *     proveedores. Ver `lib/config.js`, bloque `ESC03`.
 *
 * Factor de compresión temporal (Regla 3, mismo criterio que DISP-03 §5.4):
 *   El escenario real ocurre a lo largo de 3 años. Esta prueba comprime esos
 *   3 años a 16 minutos de duración total (4 escalones de 3 min cada uno +
 *   4 min sostenidos en el pico), factor de compresión ≈
 *   (3 años × 365 × 24 × 60 min) / 16 min ≈ 98.550x. Es razonable: lo que
 *   ESC-03 protege es que el SISTEMA soporte el volumen agregado sin
 *   degradar el SLA, no que la prueba dure literalmente 3 años — igual que
 *   DISP-03 no esperó 24-48h reales por cada verificación para validar el
 *   mecanismo de la DLQ.
 */

import http from 'k6/http';
import { check } from 'k6';
import {
  GESTION_TRABAJOS_URL,
  DISP03_URL,
  ESC03,
  buildOptions,
} from './lib/config.js';

const REGIONES = ['CO', 'BR'];
const TIPOS_VERIFICADOR = ['policia', 'rues', 'certificadora'];

// 4 escalones graduales: base (1x) -> ~1.67x -> ~2.33x -> pico (3x), reflejando
// la entrada simultánea y progresiva a México, Brasil y Argentina, no un salto
// instantáneo de 1x a 3x.
function stagesCrecimiento(base, pico) {
  const paso = (pico - base) / 3;
  return [
    { target: Math.round(base), duration: '3m' },
    { target: Math.round(base + paso), duration: '3m' },
    { target: Math.round(base + 2 * paso), duration: '3m' },
    { target: Math.round(pico), duration: '3m' },
    { target: Math.round(pico), duration: '4m' }, // sostiene el pico (crecimiento "sostenido")
  ];
}

const scenarios = {
  trabajos_crecimiento: {
    executor: 'ramping-arrival-rate',
    startRate: 0,
    timeUnit: '1s',
    preAllocatedVUs: 50,
    maxVUs: 300,
    stages: stagesCrecimiento(
      ESC03.TRABAJOS_BASE_RPS_PRUEBA,
      ESC03.TRABAJOS_PEAK_RPS_PRUEBA
    ),
    exec: 'crearTrabajo',
  },
  proveedores_crecimiento: {
    executor: 'ramping-arrival-rate',
    startRate: 0,
    timeUnit: '1s',
    preAllocatedVUs: 50,
    maxVUs: 300,
    stages: stagesCrecimiento(
      ESC03.PROVEEDORES_BASE_RPS_PRUEBA,
      ESC03.PROVEEDORES_PEAK_RPS_PRUEBA
    ),
    exec: 'crearVerificacion',
  },
};

const thresholds = {
  'http_req_duration{scenario:trabajos_crecimiento}': [`p(95)<${ESC03.P95_MS}`],
  'http_req_duration{scenario:proveedores_crecimiento}': [`p(95)<${ESC03.P95_MS}`],
  'http_req_failed{scenario:trabajos_crecimiento}': ['rate<0.01'],
  'http_req_failed{scenario:proveedores_crecimiento}': ['rate<0.01'],
};

export const options = buildOptions(scenarios, thresholds);

// Usado solo en modo SMOKE (`-e SMOKE=true`) — ver comentario equivalente en esc-01.js.
export default function () {
  crearTrabajo();
  crearVerificacion();
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

  check(res, { 'trabajo aceptado (201)': (r) => r.status === 201 });

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-03',
      caso: 'trabajos_crecimiento',
      status: res.status,
      latencia_ms: latenciaMs,
    })
  );
}

export function crearVerificacion() {
  const tipo = TIPOS_VERIFICADOR[Math.floor(Math.random() * TIPOS_VERIFICADOR.length)];
  const payload = JSON.stringify({
    proveedor_id: `prov-nuevo-${__VU}-${__ITER}`,
    tipo_verificador: tipo,
  });
  const params = { headers: { 'Content-Type': 'application/json' } };

  const inicio = Date.now();
  const res = http.post(`${DISP03_URL}/verificaciones`, payload, params);
  const latenciaMs = Date.now() - inicio;

  check(res, { 'verificacion aceptada (202)': (r) => r.status === 202 });

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-03',
      caso: 'proveedores_crecimiento',
      tipo_verificador: tipo,
      status: res.status,
      latencia_ms: latenciaMs,
    })
  );
}

export function handleSummary(data) {
  const m = data.metrics;
  const resumen = {
    escenario: 'ESC-03',
    p95_trabajos_ms: m['http_req_duration{scenario:trabajos_crecimiento}']
      ? m['http_req_duration{scenario:trabajos_crecimiento}'].values['p(95)']
      : null,
    p95_proveedores_ms: m['http_req_duration{scenario:proveedores_crecimiento}']
      ? m['http_req_duration{scenario:proveedores_crecimiento}'].values['p(95)']
      : null,
  };
  console.log(`\n[ESC-03] Resumen: ${JSON.stringify(resumen)}\n`);
  return {
    'results/esc-03-summary.json': JSON.stringify(data, null, 2),
  };
}

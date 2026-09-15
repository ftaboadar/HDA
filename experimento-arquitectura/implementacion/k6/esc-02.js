/**
 * ESC-02 — 5x tráfico súbito de un solo partner B2B2C (API de Verificación / DISP-03)
 * Fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla
 * "Escalabilidad", columna ESC-02.
 *
 * Qué mide:
 *   - Escenario `partner_pico`: ráfaga de `POST /verificaciones` que sube de
 *     tráfico habitual a 5x en menos de 60s y lo sostiene, simulando el
 *     onboarding/campaña de un partner.
 *   - Escenario `otros_partners_baseline`: tráfico constante y bajo,
 *     corriendo en paralelo durante toda la prueba, como proxy de "otros
 *     partners no involucrados en el pico".
 *
 * BRECHA DOCUMENTADA — "partner" no existe como concepto en la API de DISP-03:
 *   `VerificacionCreate` (`app/common/schemas.py`) solo tiene `proveedor_id` y
 *   `tipo_verificador` (`policia` | `rues` | `certificadora`); no hay un campo
 *   `partner_id` en el contrato HTTP, ni rate limiting por partner en el
 *   Gateway (de hecho, DISP-01/DISP-02 en `escenarios_calidad.md` marcan la
 *   "Decisión arquitectural" y el "Rationale" como `*Pendiente*` — el Gateway
 *   con rate limiting por partner que ESC-02 exige, en la fila "Respuesta",
 *   no está implementado en ningún servicio de este repo hoy).
 *
 *   Esta prueba NO inventa un campo `partner_id` que no existe en el
 *   contrato real (violaría la instrucción de no rellenar huecos con
 *   decisiones de diseño no declaradas). En su lugar, usa el mecanismo de
 *   aislamiento que SÍ existe hoy en DISP-03 — partición/routing key por
 *   `tipo_verificador` (ver `escenarios_calidad.md`, fila "Decisión
 *   arquitectural" de DISP-03: "aislamiento por routing key/partición por
 *   tipo de verificador... para que la degradación de uno no compita por
 *   recursos con los otros dos") — como PROXY de "un partner" vs. "otros
 *   partners":
 *     - `certificadora` → tráfico del partner que recibe el pico de 5x.
 *     - `policia` y `rues` → tráfico de "otros partners", que debería
 *       mantenerse estable.
 *
 *   Esto prueba el AISLAMIENTO POR TIPO DE VERIFICADOR (que sí existe),
 *   NO rate limiting por partner en un API Gateway (que no existe). Son
 *   mecanismos distintos aunque el objetivo de negocio ("que un partner no
 *   afecte a otro") sea el mismo. Cualquier lectura de estos resultados
 *   como validación de "rate limiting por partner" sería incorrecta — el
 *   veredicto real sobre qué tan válida es esta aproximación le corresponde
 *   a `validador-hipotesis`, no a este script.
 *
 * Mapeo a ESC-02 (medida de la respuesta, textual):
 *   "Auto-escalamiento activo en < 60s; p95 de latencia < 300ms incluso con
 *   5x de tráfico de un solo partner; 0% de rate limiting aplicado a
 *   partners no involucrados en el pico; < 5% de variación en p95 de otros
 *   partners".
 *   - p95 < 300ms con 5x           → threshold `http_req_duration{scenario:partner_pico}`.
 *   - Auto-escalamiento < 60s      → LIMITACIÓN: k6 no puede leer el conteo
 *     de instancias de Cloud Run. La rampa a 5x en esta prueba dura 45s
 *     (`< 60s`) a propósito, como estímulo; que el p95 se mantenga estable
 *     durante y después de esa rampa es evidencia INDIRECTA de que hubo
 *     autoscaling a tiempo, no una medición directa. Confirmar con
 *     `gcloud run services describe` / métricas de Cloud Run en paralelo
 *     al correr esto contra GCP real.
 *   - 0% rate limiting a otros partners → threshold de tasa de error del
 *     escenario `otros_partners_baseline` (no hay un código de estado
 *     específico "429 por rate limiting" que devolver, porque DISP-03 no
 *     implementa rate limiting — ver brecha arriba; el threshold aquí solo
 *     confirma que `otros_partners_baseline` no ve errores/caídas de
 *     latencia durante el pico del otro tipo de verificador).
 *   - < 5% variación en p95 de otros partners → igual que en ESC-01, esto
 *     requiere comparar ventanas de tiempo (antes/durante el pico) en el
 *     JSON exportado por `handleSummary`; no es un threshold nativo de k6.
 *
 * Baseline de tráfico "habitual de un partner" — SUPUESTO explícito:
 *   El enunciado y `escenarios_calidad.md` NO dan una cifra absoluta de
 *   tráfico habitual por partner (a diferencia de ESC-01/ESC-03, que sí
 *   traen cifras absolutas). Se usa `BASE_RPS=10` (`lib/config.js`) como
 *   supuesto de trabajo, documentado ahí — lo que sí es fiel al enunciado es
 *   el multiplicador ×5 y el umbral p95<300ms.
 *
 * No se documenta un factor de compresión temporal aquí porque ESC-02 no
 * define una ventana de tiempo real a comprimir (a diferencia de ESC-01
 * -48h- y ESC-03 -3 años-) — es un pico "súbito", y esta prueba lo trata
 * como tal (rampa corta, sostenida unos minutos).
 */

import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';
import { DISP03_URL, ESC02, buildOptions } from './lib/config.js';

const rateLimitOtrosPartners = new Rate('esc02_rate_limit_otros_partners');

const scenarios = {
  partner_pico: {
    executor: 'ramping-arrival-rate',
    startRate: ESC02.BASE_RPS,
    timeUnit: '1s',
    preAllocatedVUs: 20,
    maxVUs: 200,
    stages: [
      { target: ESC02.BASE_RPS, duration: '30s' }, // tráfico habitual
      { target: ESC02.PEAK_RPS, duration: '45s' }, // rampa a 5x en < 60s
      { target: ESC02.PEAK_RPS, duration: '3m' }, // sostiene el pico
      { target: ESC02.BASE_RPS, duration: '30s' }, // vuelve a tráfico habitual
    ],
    exec: 'verificacionPartnerConPico',
  },
  otros_partners_baseline: {
    executor: 'constant-arrival-rate',
    rate: ESC02.BASE_RPS,
    timeUnit: '1s',
    duration: '5m30s', // cubre toda la duración de partner_pico
    preAllocatedVUs: 20,
    maxVUs: 100,
    exec: 'verificacionOtroPartner',
  },
};

const thresholds = {
  'http_req_duration{scenario:partner_pico}': [`p(95)<${ESC02.P95_MS}`],
  'http_req_duration{scenario:otros_partners_baseline}': [
    `p(95)<${Math.round(ESC02.P95_MS * (1 + ESC02.VARIACION_OTROS_PARTNERS_MAX))}`,
  ],
  'http_req_failed{scenario:otros_partners_baseline}': ['rate<0.01'],
  esc02_rate_limit_otros_partners: [
    `rate<=${ESC02.RATE_LIMIT_OTROS_PARTNERS_MAX}`,
  ],
};

export const options = buildOptions(scenarios, thresholds);

// Usado solo en modo SMOKE (`-e SMOKE=true`) — ver comentario equivalente en esc-01.js.
export default function () {
  verificacionPartnerConPico();
  verificacionOtroPartner();
}

function postVerificacion(tipoVerificador) {
  const payload = JSON.stringify({
    proveedor_id: `prov-${tipoVerificador}-${__VU}-${__ITER}`,
    tipo_verificador: tipoVerificador,
  });
  const params = { headers: { 'Content-Type': 'application/json' } };
  return http.post(`${DISP03_URL}/verificaciones`, payload, params);
}

export function verificacionPartnerConPico() {
  const inicio = Date.now();
  const res = postVerificacion('certificadora'); // proxy del partner en pico
  const latenciaMs = Date.now() - inicio;

  check(res, { 'verificacion aceptada (202)': (r) => r.status === 202 });

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-02',
      caso: 'partner_pico',
      tipo_verificador: 'certificadora',
      status: res.status,
      latencia_ms: latenciaMs,
    })
  );
}

export function verificacionOtroPartner() {
  // Alterna policia/rues como proxy de "otros partners" no involucrados en el pico.
  const tipo = __ITER % 2 === 0 ? 'policia' : 'rues';
  const inicio = Date.now();
  const res = postVerificacion(tipo);
  const latenciaMs = Date.now() - inicio;

  const rateLimited = res.status === 429;
  rateLimitOtrosPartners.add(rateLimited);
  check(res, { 'verificacion aceptada (202)': (r) => r.status === 202 });

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      escenario: 'ESC-02',
      caso: 'otros_partners_baseline',
      tipo_verificador: tipo,
      status: res.status,
      latencia_ms: latenciaMs,
      rate_limited: rateLimited,
    })
  );
}

export function handleSummary(data) {
  const m = data.metrics;
  const resumen = {
    escenario: 'ESC-02',
    p95_partner_pico_ms: m['http_req_duration{scenario:partner_pico}']
      ? m['http_req_duration{scenario:partner_pico}'].values['p(95)']
      : null,
    p95_otros_partners_ms: m['http_req_duration{scenario:otros_partners_baseline}']
      ? m['http_req_duration{scenario:otros_partners_baseline}'].values['p(95)']
      : null,
    rate_limit_otros_partners: m.esc02_rate_limit_otros_partners
      ? m.esc02_rate_limit_otros_partners.values.rate
      : null,
  };
  console.log(`\n[ESC-02] Resumen: ${JSON.stringify(resumen)}\n`);
  return {
    'results/esc-02-summary.json': JSON.stringify(data, null, 2),
  };
}

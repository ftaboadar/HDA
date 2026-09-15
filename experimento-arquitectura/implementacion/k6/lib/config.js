/**
 * Configuración compartida de las pruebas de carga k6 — Escenarios de Escalabilidad
 * (ESC-01, ESC-02, ESC-03), ver `experimento-arquitectura/contexto/escenarios_calidad.md`.
 *
 * TODAS las URLs y umbrales viven aquí para no repetirlos en cada script (`esc-01.js`,
 * `esc-02.js`, `esc-03.js` solo importan de este módulo).
 *
 * Convención de modo "smoke" (validación de sintaxis/lógica, NO del escenario real):
 * si se define la variable de entorno k6 `SMOKE=true`, cada script devuelve un objeto
 * `options` SIN `scenarios` (usa el ejecutor por defecto de k6), de forma que los flags
 * de línea de comandos `--vus`/`--duration`/`--iterations` sí tienen efecto — así se
 * cumple el pedido explícito de poder correr
 * `k6 run --vus 2 --duration 10s -e SMOKE=true esc-01.js`.
 * Sin `SMOKE=true`, cada script usa sus propios `scenarios` (con las tasas/duraciones
 * reales derivadas del escenario), que SÍ ignoran los flags `--vus`/`--duration` de k6
 * (comportamiento nativo de k6 cuando hay `scenarios` explícitos).
 */

// ---------------------------------------------------------------------------
// URLs base — parametrizables por variable de entorno k6 (-e NOMBRE=valor).
// Defaults apuntan a los puertos de docker-compose / uvicorn local documentados
// en los README de cada servicio.
// ---------------------------------------------------------------------------
export const DISP03_URL = (__ENV.DISP03_URL || 'http://localhost:8000').replace(/\/$/, '');
export const GESTION_TRABAJOS_URL = (__ENV.GESTION_TRABAJOS_URL || 'http://localhost:8001').replace(/\/$/, '');

export const SMOKE = (__ENV.SMOKE || '').toLowerCase() === 'true';

/**
 * Construye el objeto `options` de un script, aplicando el modo smoke cuando
 * corresponde (ver comentario de cabecera).
 *
 * @param {object} scenarios - objeto `scenarios` de k6 con la carga real del escenario.
 * @param {object} thresholds - objeto `thresholds` de k6 (se aplica siempre, en ambos modos,
 *   para que hasta el smoke test deje ver si algo está roto de raíz — aunque con 2 VUs/10s
 *   no se espera que cumpla los umbrales reales, eso no es lo que el smoke test evalúa).
 */
export function buildOptions(scenarios, thresholds) {
  if (SMOKE) {
    // Sin `scenarios`: k6 usa el ejecutor implícito (`vus`/`duration`/`iterations`),
    // que SÍ acepta override por CLI (--vus, --duration, --iterations).
    return {
      vus: 2,
      duration: '10s',
      thresholds,
    };
  }
  return { scenarios, thresholds };
}

// ---------------------------------------------------------------------------
// ESC-01 — Pico climático 4x en 48h (Gestión de Trabajos)
// Fuente: escenarios_calidad.md, tabla Escalabilidad, columna ESC-01.
// Estímulo: "Pico de hasta 4x en el volumen de siniestros en 48h; +25M
// requests/día en crecimiento hacia 100M+".
// Medida de la respuesta: "Latencia de aceptación < 2s en pico; ≥ 99.9% de
// solicitudes aceptadas en pico; < 5% de variación en latencia de los demás
// dominios durante el pico".
//
// Derivación de tasas (Regla 3 — usar el volumen del enunciado, no uno menor):
//   base:  25.000.000 req/día  / 86.400 s/día ≈ 289  req/s
//   pico:  100.000.000 req/día / 86.400 s/día ≈ 1157 req/s  (= base × 4, y
//          coincide con el "100M+" que el propio escenario cita como destino
//          del pico, no como una cifra aparte — ver comentario de cabecera
//          de esc-01.js para la justificación completa de esta lectura).
// ---------------------------------------------------------------------------
export const ESC01 = {
  BASE_RPS: 289,
  PEAK_RPS: 1157, // 289 × 4
  P95_ACEPTACION_MS: 2000,
  TASA_ACEPTACION_MIN: 0.999, // ≥ 99.9%
  VARIACION_OTROS_DOMINIOS_MAX: 0.05, // < 5% — ver limitación documentada en esc-01.js
};

// ---------------------------------------------------------------------------
// ESC-02 — 5x tráfico de un solo partner B2B2C (DISP-03 / Verificación)
// Fuente: escenarios_calidad.md, tabla Escalabilidad, columna ESC-02.
// Estímulo: "hasta 5x el tráfico habitual de un solo partner" (SIN cifra
// absoluta de tráfico "habitual" en el enunciado ni en escenarios_calidad.md
// — a diferencia de ESC-01/ESC-03, que sí traen cifras absolutas).
//
// LIMITACIÓN DOCUMENTADA (no rellenada con una decisión de diseño oculta):
// el baseline de 10 req/s de abajo NO viene del enunciado del proyecto — es
// un supuesto explícito de esta prueba, necesario porque el enunciado no fija
// un volumen absoluto para "el tráfico habitual de un solo partner". Lo que
// SÍ es fiel al enunciado es el multiplicador ×5 (la variable que el
// escenario realmente mide) y el umbral p95<300ms (medida de la respuesta,
// textual). Antes de reportar resultados de este escenario como concluyentes,
// alguien del equipo con datos reales de tráfico por partner debería
// reemplazar BASE_RPS por la cifra real.
// ---------------------------------------------------------------------------
export const ESC02 = {
  BASE_RPS: 10, // SUPUESTO — no viene del enunciado, ver comentario arriba
  PEAK_RPS: 50, // 10 × 5
  AUTOSCALING_MAX_S: 60,
  P95_MS: 300,
  RATE_LIMIT_OTROS_PARTNERS_MAX: 0.0, // 0% de rate limiting a partners no involucrados
  VARIACION_OTROS_PARTNERS_MAX: 0.05, // < 5% de variación en p95 de otros partners
};

// ---------------------------------------------------------------------------
// ESC-03 — Crecimiento sostenido 3x (Gestión de Trabajos + Verificación)
// Fuente: escenarios_calidad.md, tabla Escalabilidad, columna ESC-03.
// Estímulo: "el volumen total de la plataforma crece de ~12.000 a 36.000
// trabajos/día (×3) y de +45.000 a +100.000 proveedores registrados en 3
// años".
//
// Derivación de tasas LITERALES del enunciado (piso, Regla 3):
//   trabajos base: 12.000/día / 86.400 s/día ≈ 0.139 req/s
//   trabajos pico: 36.000/día / 86.400 s/día ≈ 0.417 req/s  (×3)
// Estas tasas literales son demasiado bajas para ejercer el sistema de forma
// medible en una ventana de prueba de minutos (compresión temporal, ver
// esc-03.js) — por eso el script usa una tasa de prueba AMPLIFICADA que
// preserva el factor de crecimiento ×3 exacto del enunciado, pero en un
// orden de magnitud mayor (nunca menor) al piso literal, cumpliendo Regla 3
// ("igual o mayor", nunca "o menor"). Ambas cifras (piso literal y tasa de
// prueba amplificada) quedan documentadas explícitamente, ninguna oculta.
// ---------------------------------------------------------------------------
export const ESC03 = {
  TRABAJOS_BASE_RPS_LITERAL: 0.139, // piso real del enunciado — documentado, no usado directo
  TRABAJOS_PEAK_RPS_LITERAL: 0.417,
  TRABAJOS_BASE_RPS_PRUEBA: 5, // tasa amplificada usada en el script (> piso literal)
  TRABAJOS_PEAK_RPS_PRUEBA: 15, // 5 × 3 — mantiene el factor ×3 del enunciado
  // Proxy de crecimiento de proveedores (+45.000 → +100.000 en 3 años) contra
  // DISP-03 — no hay una tasa de "verificaciones/segundo" en el enunciado
  // para ese crecimiento (son totales acumulados, no un flujo diario), así
  // que se usa el mismo par base/pico amplificado ×3 que trabajos, como
  // SUPUESTO explícito documentado en esc-03.js, no como cifra derivada.
  PROVEEDORES_BASE_RPS_PRUEBA: 5,
  PROVEEDORES_PEAK_RPS_PRUEBA: 15,
  P95_MS: 300, // "mismo SLA de latencia (p95 < 300ms) que hoy"
};

/**
 * Configuración compartida de las pruebas de carga k6 — Escenario de Escalabilidad
 * ESC-01, ver `experimento-arquitectura/contexto/escenarios_calidad.md`.
 *
 * TODAS las URLs y umbrales viven aquí para no repetirlos en el script (`esc-01.js`
 * solo importa de este módulo).
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

"""Prueba de carga end-to-end de DISP-02 (Sidecar/Throttler hacia el CRM
"Gestión de Agentes") — ver `experimento-arquitectura/contexto/
escenarios_calidad.md`, fila DISP-02.

A diferencia de `tests/unit/aplicacion/test_throttler_crm.py` (fakes en
memoria, sin red ni Postgres reales), esta prueba corre contra el mock REAL
del CRM (`implementacion/mocks-crm/`, con rate limiting real vía ventana
deslizante de 1s) y la API real de `gestion-de-trabajos` con Postgres real
— todo levantado por `docker-compose.disp02.yml` (ver ese archivo). Esta
prueba NO levanta nada: asume que

    docker compose -f docker-compose.disp02.yml up -d --build

ya corrió — mismo patrón que `DISP-03/tests/test_escenarios_disp03.py`
(asume `docker compose up -d` externo, no lo orquesta pytest).

Cada test:
  1. Configura el límite de tasa real del mock del CRM vía
     `POST /_control/config`.
  2. Dispara una ráfaga real de `POST /novedades` contra la API real.
  3. Sondea `GET /novedades/{id}` hasta que el Throttler drena la cola (o
     se agota la ventana de 1h) y mide la métrica que exige DISP-02.
  4. Registra los datos crudos vía `tests/integracion/resultados.registrar`
     Y hace un `assert` de pytest sobre esa misma medida — verificación
     MECÁNICA de umbral (pytest pasa/falla), no el veredicto de hipótesis
     global: eso lo hace el agente `validador-hipotesis`, que además revisa
     amenazas a la validez y posibles sesgos (mismo criterio explícito que
     `DISP-03/tests/test_escenarios_disp03.py`).

Factor de sobrecarga (Regla 3 de `REGLAS-DURAS-rubrica-entrega-3.md`: nunca
reducir el volumen del enunciado por debajo de lo real): el estímulo de
DISP-02 en `escenarios_calidad.md` dice literalmente "intenta publicar
MILES de webhooks/segundo" hacia un CRM que impone rate limiting.
`N_NOVEDADES = 2000` es la lectura literal de "miles" (plural, ≥2000) de
ese estímulo, disparadas de forma CONCURRENTE (no paceadas — el propio test
las dispara tan rápido como el cliente HTTP puede) contra un CRM mock
configurado a `CRM_LIMITE_RPS = 20` req/s. Eso es una ráfaga total ~25x el
"piso mínimo" que exige el criterio de diseño de la cola del Throttler
("más de 4x el límite configurado", ver `FACTOR_MINIMO_SOBRE_LIMITE`,
verificado mecánicamente por la fixture `_verificar_burst_excede_umbral`
antes de correr nada).

Brecha declarada, no oculta: no se intentó sostener una tasa de LLEGADA a
la API HTTP de miles de req/s de forma indefinida — eso requeriría
infraestructura de generación de carga distribuida (tipo k6 contra Cloud
Run con auto-scaling), fuera de alcance de este PoC local de un solo
contenedor `uvicorn`/Postgres (mismo tipo de brecha ya aceptada en
`../../k6/README.md` para ESC-01). Lo que sí se prueba de punta a punta es
que el VOLUMEN total de novedades a entregar excede holgadamente el umbral
de diseño del Throttler, y que el mecanismo (cola + backoff + reintentos)
las entrega todas sin pérdida dentro de los umbrales de tiempo reales de
DISP-02.

Compresión de escala temporal: NINGUNA (a diferencia de DISP-03/ESC-01).
Los umbrales de DISP-02 son minutos/horas REALES (≥99% en <15min, 100% en
<1h) y el drenado real de esta prueba toma del orden de decenas de segundos
a pocos minutos en un laptop — se mide el tiempo de pared real, sin
comprimir, y se compara directo contra esos umbrales sin ningún factor de
conversión."""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

from tests.integracion.resultados import registrar

API_URL = "http://localhost:8003"
MOCK_CRM_URL = "http://localhost:9200"

# --- Parámetros finales de esta corrida (ver README/RESULTADOS-DISP02.md
# para el historial de ajustes hechos tras iterar sobre corridas previas que
# no cumplían el umbral) ---
CRM_LIMITE_RPS = 20
N_NOVEDADES = 2000
FACTOR_MINIMO_SOBRE_LIMITE = 4  # criterio de diseño: ráfaga > 4x el límite del CRM

UMBRAL_PCT_SIN_PERDIDA = 0.999
UMBRAL_PCT_ENTREGADO_15MIN = 0.99
VENTANA_15MIN_S = 15 * 60
VENTANA_1H_S = 60 * 60

# Poll cada 1s -- suficientemente fino frente a una ventana de hasta 1h,
# sin saturar la API con polling.
INTERVALO_POLL_S = 1.0


@pytest.fixture(scope="module", autouse=True)
def _verificar_burst_excede_umbral():
    """Verificación mecánica de que el diseño del propio caso de prueba
    respeta Regla 3 (no reducir el volumen por debajo del criterio de "más
    de 4x") -- falla ruidosamente si alguien reduce N_NOVEDADES sin querer,
    en vez de dejar pasar en silencio una ráfaga insuficiente."""
    minimo = FACTOR_MINIMO_SOBRE_LIMITE * CRM_LIMITE_RPS
    assert N_NOVEDADES > minimo, (
        f"N_NOVEDADES={N_NOVEDADES} debe superar {FACTOR_MINIMO_SOBRE_LIMITE}x "
        f"el límite del CRM ({minimo}), ver docstring del módulo"
    )


async def _configurar_mock_crm(cliente: httpx.AsyncClient, limite_rps: int) -> None:
    resp = await cliente.post(
        f"{MOCK_CRM_URL}/_control/config", json={"limite_rps": limite_rps}
    )
    resp.raise_for_status()


async def _crear_novedad(
    cliente: httpx.AsyncClient, trabajo_id: str, i: int, semaforo: asyncio.Semaphore
) -> str:
    # Semáforo del lado del cliente de prueba (no del throttler bajo
    # prueba): limita cuántas `POST /novedades` están en vuelo a la vez.
    # Ajuste real de esta tarea (ver `common/db.py` y `api/main.py`,
    # docstrings de la 1ª corrida) — sin este límite, disparar las 2000 de
    # una sola vez con `asyncio.gather` saturaba el pool HTTP del cliente
    # (`httpx.PoolTimeout`) antes de siquiera llegar al mecanismo de
    # throttling hacia el CRM, que es lo que este caso de prueba busca
    # medir.
    async with semaforo:
        resp = await cliente.post(
            "/novedades",
            json={"trabajo_id": trabajo_id, "descripcion": f"novedad de carga DISP-02 #{i}"},
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def _obtener_estado(cliente: httpx.AsyncClient, novedad_id: str) -> dict:
    resp = await cliente.get(f"/novedades/{novedad_id}")
    resp.raise_for_status()
    return resp.json()


@pytest.mark.asyncio
async def test_disp02_rafaga_mayor_a_4x_sin_perdida_por_rate_limiting():
    async with httpx.AsyncClient(timeout=10) as control:
        await _configurar_mock_crm(control, CRM_LIMITE_RPS)

    limites = httpx.Limits(max_connections=150, max_keepalive_connections=150)
    semaforo = asyncio.Semaphore(150)  # concurrencia acotada del cliente, ver docstring de _crear_novedad
    async with httpx.AsyncClient(base_url=API_URL, timeout=60, limits=limites) as api:
        trabajo_id_comun = str(uuid.uuid4())

        t0 = time.time()
        ids = await asyncio.gather(
            *[_crear_novedad(api, trabajo_id_comun, i, semaforo) for i in range(N_NOVEDADES)]
        )
        t_fin_encolado = time.time()

        # --- Polling hasta drenar la cola o agotar la ventana de 1h ---
        pendientes = set(ids)
        terminales: dict[str, dict] = {}
        marca_15min: dict[str, dict] | None = None

        while pendientes and (time.time() - t0) < VENTANA_1H_S:
            lote = list(pendientes)
            resultados = await asyncio.gather(
                *[_obtener_estado(api, nid) for nid in lote], return_exceptions=True
            )
            for nid, resultado in zip(lote, resultados):
                if isinstance(resultado, Exception):
                    continue
                if resultado["estado"] in ("ENTREGADA", "AGOTADA"):
                    terminales[nid] = resultado
                    pendientes.discard(nid)

            if marca_15min is None and (time.time() - t0) >= VENTANA_15MIN_S:
                marca_15min = dict(terminales)

            if pendientes:
                await asyncio.sleep(INTERVALO_POLL_S)

        duracion_total_drenado_s = time.time() - t0

        if marca_15min is None:
            # el drenado terminó (o se agotó la ventana de 1h) antes de
            # llegar a los 15min reales de pared -- el corte de los 15min
            # coincide con el estado final.
            marca_15min = dict(terminales)

    total = len(ids)
    entregadas = sum(1 for r in terminales.values() if r["estado"] == "ENTREGADA")
    agotadas = sum(1 for r in terminales.values() if r["estado"] == "AGOTADA")
    sin_estado_terminal_1h = total - len(terminales)

    pct_sin_perdida = entregadas / total
    pct_entregado_15min = (
        sum(1 for r in marca_15min.values() if r["estado"] == "ENTREGADA") / total
    )
    pct_entregado_1h = entregadas / total

    registrar(
        "DISP-02",
        "pct_sin_perdida_por_rate_limiting",
        pct_sin_perdida,
        UMBRAL_PCT_SIN_PERDIDA,
        pct_sin_perdida >= UMBRAL_PCT_SIN_PERDIDA,
        detalle=(
            f"entregadas={entregadas} agotadas={agotadas} "
            f"sin_estado_terminal_tras_1h={sin_estado_terminal_1h} total={total} "
            f"crm_limite_rps={CRM_LIMITE_RPS} n_novedades={N_NOVEDADES}"
        ),
    )
    registrar(
        "DISP-02",
        "pct_entregado_dentro_15min",
        pct_entregado_15min,
        UMBRAL_PCT_ENTREGADO_15MIN,
        pct_entregado_15min >= UMBRAL_PCT_ENTREGADO_15MIN,
    )
    registrar(
        "DISP-02",
        "pct_entregado_dentro_1h",
        pct_entregado_1h,
        1.0,
        pct_entregado_1h == 1.0,
    )
    registrar(
        "DISP-02",
        "cantidad_agotadas",
        agotadas,
        0,
        agotadas == 0,
        detalle="idealmente 0 AGOTADA si el diseño del throttler es correcto",
    )
    registrar(
        "DISP-02",
        "cantidad_sin_estado_terminal_tras_1h",
        sin_estado_terminal_1h,
        0,
        sin_estado_terminal_1h == 0,
    )
    registrar(
        "DISP-02",
        "duracion_total_drenado_s",
        duracion_total_drenado_s,
        VENTANA_1H_S,
        duracion_total_drenado_s < VENTANA_1H_S,
    )
    registrar(
        "DISP-02",
        "tiempo_encolado_rafaga_s",
        t_fin_encolado - t0,
        None,
        True,
        detalle="tiempo que tomó aceptar (202) las N POST /novedades, no su entrega real al CRM",
    )

    assert pct_sin_perdida >= UMBRAL_PCT_SIN_PERDIDA, (
        f"{pct_sin_perdida:.4%} entregadas sin pérdida por rate limiting, "
        f"se exige >= {UMBRAL_PCT_SIN_PERDIDA:.1%} "
        f"(entregadas={entregadas} agotadas={agotadas} "
        f"sin_terminal={sin_estado_terminal_1h} total={total})"
    )
    assert pct_entregado_15min >= UMBRAL_PCT_ENTREGADO_15MIN, (
        f"{pct_entregado_15min:.2%} entregadas dentro de 15min reales, "
        f"se exige >= {UMBRAL_PCT_ENTREGADO_15MIN:.0%}"
    )
    assert pct_entregado_1h == 1.0, (
        f"{pct_entregado_1h:.2%} entregadas dentro de 1h real, se exige 100%"
    )


@pytest.mark.asyncio
async def test_disp02_disponibilidad_api_independiente_del_crm_saturado():
    """Complemento al caso principal: cubre la parte del umbral de DISP-02
    que el caso de arriba no mide directamente -- "disponibilidad de
    Gestión de Trabajos ≥99.9% independiente del estado de Gestión de
    Agentes". Satura el mock del CRM a un límite muy bajo (1 req/s) para
    forzar que el Throttler pase la mayor parte del tiempo reintentando/
    esperando backoff, y confirma que `GET /salud` sigue respondiendo 200
    con baja latencia durante ese tiempo -- evidencia de que la API no se
    bloquea esperando al CRM.

    Alcance declarado: esto NO prueba el caso "CRM completamente caído/sin
    responder" (ese modo de falla no está implementado en
    `mocks-crm/app/main.py`, que solo modela rate limiting real, no
    caída/timeout como sí hacen los mocks de DISP-03/Pagos) -- es una
    medida indicativa de desacople bajo saturación por rate limiting, no
    una prueba exhaustiva de disponibilidad ante una caída dura del CRM."""
    async with httpx.AsyncClient(timeout=10) as control:
        await _configurar_mock_crm(control, limite_rps=1)

    n_novedades_saturacion = 100  # suficiente para mantener al Throttler ocupado varios segundos a 1rps
    limites = httpx.Limits(max_connections=50)
    semaforo = asyncio.Semaphore(50)
    async with httpx.AsyncClient(base_url=API_URL, timeout=30, limits=limites) as api:
        trabajo_id_comun = str(uuid.uuid4())
        await asyncio.gather(
            *[
                _crear_novedad(api, trabajo_id_comun, i, semaforo)
                for i in range(n_novedades_saturacion)
            ]
        )

        latencias_salud_ms: list[float] = []
        fallas_salud = 0
        muestras = 20
        for _ in range(muestras):
            t0 = time.time()
            try:
                resp = await api.get("/salud")
                resp.raise_for_status()
            except httpx.HTTPError:
                fallas_salud += 1
            else:
                latencias_salud_ms.append((time.time() - t0) * 1000)
            await asyncio.sleep(0.5)

    disponibilidad_salud = (muestras - fallas_salud) / muestras
    p95_latencia_salud_ms = (
        sorted(latencias_salud_ms)[int(len(latencias_salud_ms) * 0.95) - 1]
        if latencias_salud_ms
        else None
    )

    registrar(
        "DISP-02",
        "disponibilidad_salud_bajo_crm_saturado",
        disponibilidad_salud,
        0.999,
        disponibilidad_salud >= 0.999,
        detalle=f"{muestras} muestras de GET /salud mientras el CRM está limitado a 1rps",
    )
    registrar(
        "DISP-02",
        "p95_latencia_salud_bajo_crm_saturado_ms",
        p95_latencia_salud_ms,
        None,
        True,
        detalle="métrica informativa, sin umbral absoluto declarado en escenarios_calidad.md",
    )

    assert disponibilidad_salud >= 0.999, (
        f"GET /salud debe seguir disponible independiente del estado del CRM, "
        f"medido {disponibilidad_salud:.2%}"
    )

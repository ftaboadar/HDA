"""Casos de prueba CP-1..CP-7 de DISP-03 (ver plan.md, sección 6).

Cada test:
  1. Inyecta la falla del caso en el mock correspondiente.
  2. Ejecuta el flujo real contra la API/worker (nada se simula fuera del
     mock del sistema externo — la cola, la BD y los reintentos son reales).
  3. Mide la métrica que plan.md define para ese caso y la registra en
     tests/results/resultados_disp03.jsonl vía resultados.registrar().
  4. Además hace un `assert` de pytest sobre esa misma medida — esto es una
     verificación MECÁNICA de umbral (pytest pasa/falla), no el veredicto de
     hipótesis global: eso lo hace el agente validador-hipotesis, que además
     revisa cobertura, amenazas a validez y posibles sesgos entre casos.

Nota de escala: con los volúmenes pequeños de un PoC (N=8..30), un
porcentaje como "99.9%" no es estadísticamente significativo. Por eso los
asserts de disponibilidad/trazabilidad usan invariantes exactas y
alcanzables a esta escala (ej. "0 verificaciones perdidas", "100% terminan
en un estado terminal") en vez del porcentaje literal del escenario — la
generalización de esa invariante al 99.9% real es, precisamente, el tipo de
salto que validador-hipotesis debe señalar como amenaza a la validez, no
algo que este archivo pueda resolver por sí mismo.
"""

import asyncio
import time

import pytest

from tests.conftest import configurar_mock, crear_verificacion, esperar_estado
from tests.resultados import registrar


@pytest.mark.asyncio
async def test_cp1_baseline_todo_disponible(api):
    """CP-1: los 3 externos responden con latencia normal -> 0 en DLQ."""
    tipos = ["policia", "rues", "certificadora"] * 3  # 9 verificaciones mixtas
    creadas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp1-{i}", t) for i, t in enumerate(tipos)]
    )
    resultados = await asyncio.gather(
        *[
            esperar_estado(api, c["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=20)
            for c in creadas
        ]
    )

    completadas = sum(1 for r in resultados if r["estado"] == "COMPLETADA")
    disponibilidad = completadas / len(resultados)

    registrar("CP-1", "disponibilidad_baseline", disponibilidad, 1.0, disponibilidad == 1.0)
    assert disponibilidad == 1.0, f"esperado 100% completadas, obtuvo {disponibilidad:.2%}"


@pytest.mark.asyncio
async def test_cp2_certificadora_lenta_dentro_de_sla(api):
    """CP-2: certificadora responde OK pero lenta (dentro de SLA) -> no
    bloquea verificaciones de policía que llegan al mismo tiempo."""
    await configurar_mock("certificadora", modo="ok", latencia_ms=2000)

    inicio = time.time()
    lenta = await crear_verificacion(api, "prov-cp2-lenta", "certificadora")
    rapidas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp2-rapida-{i}", "policia") for i in range(5)]
    )

    resultados_rapidas = await asyncio.gather(
        *[
            esperar_estado(api, r["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=10)
            for r in rapidas
        ]
    )
    duracion_rapidas_s = time.time() - inicio
    resultado_lenta = await esperar_estado(
        api, lenta["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=15
    )

    todas_policia_ok = all(r["estado"] == "COMPLETADA" for r in resultados_rapidas)

    registrar(
        "CP-2",
        "duracion_verificaciones_rapidas_s",
        duracion_rapidas_s,
        1.5,
        duracion_rapidas_s < 1.5,
        detalle="deben completarse sin esperar a la certificadora lenta",
    )
    registrar(
        "CP-2",
        "certificadora_lenta_completa",
        resultado_lenta["estado"] == "COMPLETADA",
        True,
        resultado_lenta["estado"] == "COMPLETADA",
    )

    assert todas_policia_ok
    assert duracion_rapidas_s < 1.5, "las verificaciones rápidas no deberían esperar a la lenta"
    assert resultado_lenta["estado"] == "COMPLETADA"


@pytest.mark.asyncio
async def test_cp3_certificadora_errores_intermitentes(api):
    """CP-3: 50% de tasa de error transitorio -> los reintentos recuperan la
    mayoría; el 100% de las verificaciones debe terminar en un estado
    terminal (ninguna se queda colgada en PENDIENTE)."""
    await configurar_mock("certificadora", modo="error_parcial", latencia_ms=50, tasa_error=0.5)

    creadas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp3-{i}", "certificadora") for i in range(20)]
    )
    resultados = await asyncio.gather(
        *[
            esperar_estado(api, c["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=30)
            for c in creadas
        ]
    )

    terminales = sum(1 for r in resultados if r["estado"] in {"COMPLETADA", "FALLIDA_DLQ"})
    trazabilidad = terminales / len(resultados)
    fallidas_con_motivo = all(
        r["motivo_falla"] not in (None, "") for r in resultados if r["estado"] == "FALLIDA_DLQ"
    )

    registrar("CP-3", "trazabilidad_terminal", trazabilidad, 1.0, trazabilidad == 1.0)
    registrar(
        "CP-3", "fallidas_con_motivo_registrado", fallidas_con_motivo, True, fallidas_con_motivo
    )

    assert trazabilidad == 1.0, "toda verificación debe llegar a un estado terminal"
    assert fallidas_con_motivo, "toda FALLIDA_DLQ debe tener motivo_falla trazado"


@pytest.mark.asyncio
async def test_cp4_certificadora_caida_dura(api):
    """CP-4: certificadora 100% caída -> todas terminan en DLQ con motivo,
    y ninguna se pierde. El resto del sistema (policía) sigue operando."""
    await configurar_mock("certificadora", modo="caido")

    afectadas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp4-cert-{i}", "certificadora") for i in range(8)]
    )
    no_afectadas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp4-pol-{i}", "policia") for i in range(5)]
    )

    resultados_afectadas = await asyncio.gather(
        *[esperar_estado(api, c["id"], {"FALLIDA_DLQ"}, timeout_s=30) for c in afectadas]
    )
    resultados_no_afectadas = await asyncio.gather(
        *[esperar_estado(api, c["id"], {"COMPLETADA"}, timeout_s=10) for c in no_afectadas]
    )

    todas_en_dlq = all(r["estado"] == "FALLIDA_DLQ" for r in resultados_afectadas)
    todas_con_motivo = all(r["motivo_falla"] for r in resultados_afectadas)
    policia_no_afectada = all(r["estado"] == "COMPLETADA" for r in resultados_no_afectadas)

    dlq_resp = await api.get("/dlq")
    dlq_ids = {item["id"] for item in dlq_resp.json()}
    todas_visibles_en_dlq = all(a["id"] in dlq_ids for a in resultados_afectadas)

    registrar("CP-4", "pct_fallidas_en_dlq", todas_en_dlq, True, todas_en_dlq)
    registrar("CP-4", "pct_con_motivo_trazado", todas_con_motivo, True, todas_con_motivo)
    registrar("CP-4", "policia_no_afectada", policia_no_afectada, True, policia_no_afectada)
    registrar(
        "CP-4", "visibles_en_endpoint_dlq", todas_visibles_en_dlq, True, todas_visibles_en_dlq
    )

    assert todas_en_dlq
    assert todas_con_motivo
    assert policia_no_afectada
    assert todas_visibles_en_dlq


@pytest.mark.asyncio
async def test_cp5_aislamiento_policia_rues_sin_certificadora(api):
    """CP-5: con la certificadora caída, las verificaciones que NO dependen
    de ella (policía, RUES) deben completarse con normalidad — 0% impacto."""
    await configurar_mock("certificadora", modo="caido")

    creadas = await asyncio.gather(
        *[
            crear_verificacion(api, f"prov-cp5-{i}", "policia" if i % 2 == 0 else "rues")
            for i in range(10)
        ]
    )
    resultados = await asyncio.gather(
        *[
            esperar_estado(api, c["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=10)
            for c in creadas
        ]
    )

    impacto = sum(1 for r in resultados if r["estado"] != "COMPLETADA") / len(resultados)

    registrar("CP-5", "pct_impacto_por_certificadora_caida", impacto, 0.0, impacto == 0.0)
    assert impacto == 0.0, "policía/RUES no deben verse afectados por la caída de la certificadora"


@pytest.mark.asyncio
async def test_cp6_recuperacion_y_reproceso_desde_dlq(api):
    """CP-6: tras recuperarse el externo, el reproceso manual desde la DLQ
    completa el 100% de los casos, dentro de la ventana comprimida."""
    await configurar_mock("certificadora", modo="caido")
    afectadas = await asyncio.gather(
        *[crear_verificacion(api, f"prov-cp6-{i}", "certificadora") for i in range(6)]
    )
    en_dlq = await asyncio.gather(
        *[esperar_estado(api, c["id"], {"FALLIDA_DLQ"}, timeout_s=30) for c in afectadas]
    )

    inicio_reproceso = time.time()
    await configurar_mock("certificadora", modo="ok", latencia_ms=50)

    reprocesadas = await asyncio.gather(
        *[api.post(f"/dlq/{item['id']}/reprocesar") for item in en_dlq]
    )
    for r in reprocesadas:
        r.raise_for_status()

    finales = await asyncio.gather(
        *[
            esperar_estado(api, item["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=20)
            for item in en_dlq
        ]
    )
    duracion_reproceso_s = time.time() - inicio_reproceso

    pct_reprocesadas_ok = sum(1 for f in finales if f["estado"] == "COMPLETADA") / len(finales)
    # Ventana comprimida: <24h reales ~ <24 min de experimento (ver plan.md 5.4);
    # en esta ejecución exigimos que el reproceso concluya en segundos.
    umbral_ventana_s = 60

    registrar(
        "CP-6", "pct_reprocesadas_exitosas", pct_reprocesadas_ok, 1.0, pct_reprocesadas_ok == 1.0
    )
    registrar(
        "CP-6",
        "duracion_reproceso_s",
        duracion_reproceso_s,
        umbral_ventana_s,
        duracion_reproceso_s < umbral_ventana_s,
    )

    assert pct_reprocesadas_ok == 1.0
    assert duracion_reproceso_s < umbral_ventana_s


@pytest.mark.asyncio
async def test_cp7_carga_concurrente_con_falla_a_mitad_de_camino(api):
    """CP-7: bajo carga concurrente, la certificadora cae a mitad de la
    ejecución -> la latencia de ACEPTACIÓN de la API (no la de procesamiento)
    debe mantenerse estable, evidencia de que el desacople funciona."""
    latencias_aceptacion_ms: list[float] = []

    async def _crear_y_medir(proveedor_id: str, tipo: str):
        t0 = time.time()
        resultado = await crear_verificacion(api, proveedor_id, tipo)
        latencias_aceptacion_ms.append((time.time() - t0) * 1000)
        return resultado

    primera_mitad = await asyncio.gather(
        *[_crear_y_medir(f"prov-cp7-a-{i}", "certificadora") for i in range(15)]
    )

    await configurar_mock("certificadora", modo="caido")

    segunda_mitad = await asyncio.gather(
        *[_crear_y_medir(f"prov-cp7-b-{i}", "certificadora") for i in range(15)]
    )

    p95_ms = sorted(latencias_aceptacion_ms)[int(len(latencias_aceptacion_ms) * 0.95) - 1]
    umbral_p95_ms = 500

    registrar(
        "CP-7",
        "p95_latencia_aceptacion_ms",
        p95_ms,
        umbral_p95_ms,
        p95_ms < umbral_p95_ms,
        detalle="la aceptación debe seguir siendo rápida aunque el externo esté caído",
    )

    # Limpieza: dejamos que todo llegue a estado terminal antes de terminar el test
    todas = primera_mitad + segunda_mitad
    await asyncio.gather(
        *[esperar_estado(api, c["id"], {"COMPLETADA", "FALLIDA_DLQ"}, timeout_s=30) for c in todas]
    )

    assert p95_ms < umbral_p95_ms, "la API no debe bloquearse por la caída del externo"

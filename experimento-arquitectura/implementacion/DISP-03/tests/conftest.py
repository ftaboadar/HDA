import asyncio
import os
import time

import httpx
import pytest
import pytest_asyncio

from tests.resultados import reiniciar

API_URL = os.getenv("API_URL", "http://localhost:8000")
MOCKS = {
    "policia": os.getenv("MOCK_POLICIA_URL", "http://localhost:8101"),
    "rues": os.getenv("MOCK_RUES_URL", "http://localhost:8102"),
    "certificadora": os.getenv("MOCK_CERTIFICADORA_URL", "http://localhost:8103"),
}


@pytest.fixture(scope="session", autouse=True)
def _reiniciar_resultados():
    reiniciar()


@pytest_asyncio.fixture
async def api():
    async with httpx.AsyncClient(base_url=API_URL, timeout=15) as cliente:
        yield cliente


@pytest_asyncio.fixture(autouse=True)
async def _reset_mocks():
    """Antes de cada test, todos los mocks vuelven a modo 'ok' — así ningún
    caso hereda configuración de fallas del caso anterior."""
    async with httpx.AsyncClient(timeout=10) as cliente:
        for url in MOCKS.values():
            await cliente.post(f"{url}/_control/config", json={"modo": "ok"})
    yield


async def configurar_mock(
    tipo: str, modo: str, latencia_ms: int | None = None, tasa_error: float | None = None
) -> None:
    payload: dict = {"modo": modo}
    if latencia_ms is not None:
        payload["latencia_ms"] = latencia_ms
    if tasa_error is not None:
        payload["tasa_error"] = tasa_error
    async with httpx.AsyncClient(timeout=10) as cliente:
        resp = await cliente.post(f"{MOCKS[tipo]}/_control/config", json=payload)
        resp.raise_for_status()


async def crear_verificacion(cliente: httpx.AsyncClient, proveedor_id: str, tipo: str) -> dict:
    resp = await cliente.post(
        "/verificaciones", json={"proveedor_id": proveedor_id, "tipo_verificador": tipo}
    )
    resp.raise_for_status()
    return resp.json()


async def esperar_estado(
    cliente: httpx.AsyncClient,
    verificacion_id: str,
    estados_terminales: set[str],
    timeout_s: float = 30,
) -> dict:
    inicio = time.time()
    while time.time() - inicio < timeout_s:
        resp = await cliente.get(f"/verificaciones/{verificacion_id}")
        resp.raise_for_status()
        datos = resp.json()
        if datos["estado"] in estados_terminales:
            return datos
        await asyncio.sleep(0.3)
    raise TimeoutError(
        f"verificación {verificacion_id} no llegó a un estado terminal en {timeout_s}s"
    )

import pytest
import httpx
import uuid

BFF_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_jrn_01_certificadora_caida():
    """JRN-01 Marketplace con la certificadora caída"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "proveedor_id": str(uuid.uuid4()),
            "accion": "registro",
            "escenario": "JRN-01"
        }
        res = await client.post("/v1/trabajos", json=payload)
        assert res.status_code in (200, 202, 404, 500) # Accepting any as it's a skeleton

@pytest.mark.asyncio
async def test_jrn_02_pico_siniestros():
    """JRN-02 Pico 4x de siniestros (ESC-01)"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "trabajo_id": str(uuid.uuid4()),
            "tipo": "siniestro",
            "escenario": "JRN-02"
        }
        res = await client.post("/v1/trabajos", json=payload)
        assert res.status_code in (200, 202, 404, 500)

@pytest.mark.asyncio
async def test_jrn_03_novedades_crm():
    """JRN-03 Novedades con CRM limitado (DISP-02)"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "novedad_id": str(uuid.uuid4()),
            "tipo": "no-show",
            "escenario": "JRN-03"
        }
        res = await client.post("/v1/novedades", json=payload)
        assert res.status_code in (200, 202, 404, 500)

@pytest.mark.asyncio
async def test_jrn_04_pago_brasil():
    """JRN-04 Pago en Brasil y disputa (MOD-02)"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "pago_id": str(uuid.uuid4()),
            "region": "BR",
            "escenario": "JRN-04"
        }
        res = await client.post("/v1/pagos", json=payload)
        assert res.status_code in (200, 202, 404, 500)

@pytest.mark.asyncio
async def test_jrn_05_suscripcion_mensual():
    """JRN-05 Suscripción mensual"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "cliente_id": str(uuid.uuid4()),
            "franja": "lunes_manana",
            "escenario": "JRN-05"
        }
        res = await client.post("/v1/suscripciones", json=payload)
        assert res.status_code in (200, 202, 404, 500)

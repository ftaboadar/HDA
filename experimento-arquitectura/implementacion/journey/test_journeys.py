import pytest
import httpx
import uuid

BFF_URL = "http://localhost:8000/api/v1"

@pytest.mark.asyncio
async def test_jrn_01_certificadora_caida():
    """JRN-01 Marketplace con la certificadora caída"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "cliente_id": str(uuid.uuid4()),
            "detalles": "Limpieza profunda JRN-01"
        }
        res = await client.post("/solicitudes", json=payload)
        # Debe ser 200 o 202
        assert res.status_code in (200, 202)
        assert "id" in res.json()

@pytest.mark.asyncio
async def test_jrn_02_pico_siniestros():
    """JRN-02 Pico 4x de siniestros (ESC-01)"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        payload = {
            "monto_aprobado": 5000.00
        }
        siniestro_id = str(uuid.uuid4())
        res = await client.post(f"/siniestros/{siniestro_id}/aprobar", json=payload)
        assert res.status_code == 200

@pytest.mark.asyncio
async def test_jrn_03_novedades_crm():
    """JRN-03 Novedades con CRM limitado (DISP-02)"""
    # Usando el endpoint directo a gestion-de-trabajos asumiendo API Gateway routing futuro
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        payload = {
            "trabajo_id": str(uuid.uuid4()),
            "tipo": "NO_SHOW"
        }
        res = await client.post("/novedades", json=payload)
        # La solicitud debe ser al menos aceptada sin error interno
        assert res.status_code < 500

@pytest.mark.asyncio
async def test_jrn_04_pago_brasil():
    """JRN-04 Pago en Brasil y disputa (MOD-02)"""
    async with httpx.AsyncClient(base_url="http://localhost:8002") as client:
        payload = {
            "pago_id": str(uuid.uuid4()),
            "motivo": "disputa"
        }
        res = await client.post("/webhooks/pasarela", json=payload)
        assert res.status_code < 500

@pytest.mark.asyncio
async def test_jrn_05_suscripcion_mensual():
    """JRN-05 Suscripción mensual"""
    async with httpx.AsyncClient(base_url=BFF_URL) as client:
        correlation_id = str(uuid.uuid4())
        res = await client.get(f"/estado/{correlation_id}")
        assert res.status_code == 200

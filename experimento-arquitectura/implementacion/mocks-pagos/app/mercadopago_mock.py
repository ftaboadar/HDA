"""Doble de MercadoPago (MOD-02, sección 0.1 del plan de Entrega 4) — `POST
/payments`, forma de petición/respuesta deliberadamente estilo MercadoPago
real (montos en UNIDADES completas, no centavos; `id` numérico; `status` en
español `approved`/`rejected`/`pending`, con `status_detail`). Ver
`app/stripe_mock.py` para el mock "equivalente" pero con forma distinta a
propósito — ver el docstring de ese módulo para por qué la diferencia es
intencional.

No es un microservicio de dominio, es un sistema externo simulado — mismo
trato que Policía/RUES/CONTE en `implementacion/DISP-03/app/mocks/`."""

import random

from fastapi import FastAPI, Response
from pydantic import BaseModel

from app.common import ConfigMock, aplicar_config, estado_inicial, simular_latencia_y_fallas

PASARELA = "mercadopago"

app = FastAPI(title="Mock — MercadoPago")
estado = estado_inicial()


class PagoMercadoPago(BaseModel):
    transaction_amount: float  # unidades completas (ej. 15000.0 = $15.000), no centavos
    description: str = ""
    proveedor_id: str


@app.get("/salud")
async def salud():
    return {"estado": "ok", "pasarela": PASARELA}


@app.get("/_control/estado")
async def control_estado():
    return {"pasarela": PASARELA, **estado}


@app.post("/_control/config")
async def control_config(cfg: ConfigMock):
    return {"pasarela": PASARELA, **aplicar_config(estado, cfg)}


@app.post("/payments")
async def crear_pago(payload: PagoMercadoPago, response: Response):
    falla = await simular_latencia_y_fallas(estado, response, PASARELA)
    if falla is not None:
        return falla

    return {
        "id": random.randint(10_000_000, 99_999_999),
        "status": "approved",
        "status_detail": "accredited",
        "transaction_amount": payload.transaction_amount,
        "monto": payload.transaction_amount,
    }

"""Doble de Stripe (MOD-02, sección 0.1 del plan de Entrega 4) — `POST
/charges`, forma de petición/respuesta deliberadamente estilo Stripe real
(montos en CENTAVOS, `id` con prefijo `ch_`, `status` en inglés
`succeeded`/`failed`). Ver `app/mercadopago_mock.py` para el mock
"equivalente" pero con forma distinta a propósito — absorber esa diferencia
es exactamente lo que el Adapter `PasarelaDePago` (dentro del módulo ACL de
Pagos de Gestión de Trabajos) debe hacer.

No es un microservicio de dominio, es un sistema externo simulado — mismo
trato que Policía/RUES/CONTE en `implementacion/DISP-03/app/mocks/`."""

import uuid

from fastapi import FastAPI, Response
from pydantic import BaseModel

from app.common import ConfigMock, aplicar_config, estado_inicial, simular_latencia_y_fallas

PASARELA = "stripe"

app = FastAPI(title="Mock — Stripe")
estado = estado_inicial()


class CobroStripe(BaseModel):
    amount: int  # centavos, como la API real de Stripe (100 = $1.00)
    currency: str = "cop"
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


@app.post("/charges")
async def crear_cobro(payload: CobroStripe, response: Response):
    falla = await simular_latencia_y_fallas(estado, response, PASARELA)
    if falla is not None:
        return falla

    return {
        "id": f"ch_{uuid.uuid4().hex[:24]}",
        "status": "succeeded",
        "amount": payload.amount,
        "currency": payload.currency,
        "monto": payload.amount / 100,
    }

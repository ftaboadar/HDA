"""Doble de un sistema externo de verificación (Policía Nacional, RUES o la
entidad certificadora tipo CONTE). Una sola imagen, parametrizada por la
variable de entorno MOCK_NAME — así docker-compose e infra/mocks.tf reusan el
mismo artefacto para los tres.

Comportamiento controlable en caliente vía POST /_control/config, que es lo
que los casos de prueba (tests/test_escenarios_disp03.py) usan para inyectar
fallas exactamente cuando el caso lo requiere."""

import asyncio
import os
import random
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

MOCK_NAME = os.getenv("MOCK_NAME", "generico")

_DEFAULTS = {
    "policia": {"modo": "ok", "latencia_ms": 50, "tasa_error": 0.0},
    "rues": {"modo": "ok", "latencia_ms": 80, "tasa_error": 0.0},
    "certificadora": {"modo": "ok", "latencia_ms": 300, "tasa_error": 0.0},
}

estado = dict(_DEFAULTS.get(MOCK_NAME, {"modo": "ok", "latencia_ms": 50, "tasa_error": 0.0}))

app = FastAPI(title=f"Mock — {MOCK_NAME}")


class ConfigMock(BaseModel):
    modo: Literal["ok", "error_parcial", "caido", "timeout"]
    latencia_ms: int | None = None
    tasa_error: float | None = None


class SolicitudVerificar(BaseModel):
    proveedor_id: str


@app.get("/salud")
async def salud():
    return {"estado": "ok", "mock": MOCK_NAME}


@app.get("/_control/estado")
async def control_estado():
    return {"mock": MOCK_NAME, **estado}


@app.post("/_control/config")
async def control_config(cfg: ConfigMock):
    estado["modo"] = cfg.modo
    if cfg.latencia_ms is not None:
        estado["latencia_ms"] = cfg.latencia_ms
    if cfg.tasa_error is not None:
        estado["tasa_error"] = cfg.tasa_error
    return {"mock": MOCK_NAME, **estado}


@app.post("/verificar")
async def verificar(payload: SolicitudVerificar, response: Response):
    modo = estado["modo"]
    latencia_ms = estado["latencia_ms"]

    if modo == "caido":
        response.status_code = 503
        return {"error": "servicio no disponible", "mock": MOCK_NAME}

    if modo == "timeout":
        await asyncio.sleep(3600)  # excede cualquier timeout de cliente razonable
        response.status_code = 504
        return {"error": "timeout"}

    await asyncio.sleep(latencia_ms / 1000)

    if modo == "error_parcial" and random.random() < estado["tasa_error"]:
        response.status_code = 500
        return {"error": "fallo transitorio", "mock": MOCK_NAME}

    return {
        "resultado": "verificado",
        "mock": MOCK_NAME,
        "proveedor_id": payload.proveedor_id,
        "latencia_ms": latencia_ms,
    }

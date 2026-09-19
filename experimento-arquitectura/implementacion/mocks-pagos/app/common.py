"""Utilidades compartidas por los dos mocks de pasarela de pago (Stripe y
MercadoPago) — mismo patrón de control de fallas/latencia que
`implementacion/proveedores/app/mocks/main.py` (endpoint `/_control/config`
consumido en caliente por los casos de prueba de MOD-02), factorizado aquí
para no duplicar el comportamiento de inyección de fallas entre los dos
mocks.

Deliberadamente NO se factoriza el endpoint de negocio (`/charges` vs.
`/payments`) ni su forma de petición/respuesta: esa diferencia es justo lo
que el Adapter `PasarelaDePago` (dentro del módulo ACL de Pagos de Gestión
de Trabajos, ver sección 0.1 del plan de Entrega 4) debe absorber para que
MOD-02 tenga sentido. Si los dos mocks respondieran igual, no habría ninguna
diferencia real que el Adapter estuviera absorbiendo."""

import asyncio
import random
from typing import Literal

from fastapi import Response
from pydantic import BaseModel


class ConfigMock(BaseModel):
    modo: Literal["ok", "error_parcial", "caido", "timeout"]
    latencia_ms: int | None = None
    tasa_error: float | None = None


def estado_inicial() -> dict:
    return {"modo": "ok", "latencia_ms": 100, "tasa_error": 0.0}


def aplicar_config(estado: dict, cfg: ConfigMock) -> dict:
    estado["modo"] = cfg.modo
    if cfg.latencia_ms is not None:
        estado["latencia_ms"] = cfg.latencia_ms
    if cfg.tasa_error is not None:
        estado["tasa_error"] = cfg.tasa_error
    return estado


async def simular_latencia_y_fallas(estado: dict, response: Response, nombre: str) -> dict | None:
    """Devuelve un dict de error (y ya fijó `response.status_code`) si el
    modo actual del mock exige simular una falla; devuelve None si la
    llamada debe seguir su curso normal — mismo comportamiento que
    `app/mocks/main.py` de Proveedores (modos ok/error_parcial/caido/timeout),
    para que el módulo ACL de Pagos pueda inyectar fallas exactamente igual
    que Proveedores ya lo hace con Policía/RUES/Certificadora."""
    modo = estado["modo"]
    if modo == "caido":
        response.status_code = 503
        return {"error": "servicio no disponible", "pasarela": nombre}
    if modo == "timeout":
        await asyncio.sleep(3600)  # excede cualquier timeout de cliente razonable
        response.status_code = 504
        return {"error": "timeout"}
    await asyncio.sleep(estado["latencia_ms"] / 1000)
    if modo == "error_parcial" and random.random() < estado["tasa_error"]:
        response.status_code = 500
        return {"error": "fallo transitorio", "pasarela": nombre}
    return None

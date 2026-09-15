"""Contrato de serialización HTTP (Pydantic) — distinto del vocabulario de
dominio en `domain/*/value_objects.py`. `api/main.py` es el único lugar que
traduce entre ambos; ni `application/` ni `domain/` conocen estas clases."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TrabajoCreate(BaseModel):
    proveedor_id: str
    monto: Decimal
    region: str  # "CO" | "BR" — ver domain/trabajo/value_objects.Region


class TrabajoIdOut(BaseModel):
    """Respuesta de un COMANDO (POST /trabajos) — CQS: a lo sumo un id, no
    el estado de negocio completo del agregado."""

    id: uuid.UUID


class TrabajoOut(BaseModel):
    """Respuesta de una QUERY (GET /trabajos/{id}) — solo lectura, sí puede
    exponer el estado completo."""

    id: uuid.UUID
    proveedor_id: str
    estado: str
    monto: Decimal
    moneda: str
    region: str
    fecha_creacion: datetime


class PagoCreate(BaseModel):
    trabajo_id: uuid.UUID
    pasarela: str  # "stripe" | "mercadopago"


class PagoIdOut(BaseModel):
    id: uuid.UUID


class PagoOut(BaseModel):
    id: uuid.UUID
    trabajo_id: uuid.UUID
    monto: Decimal
    moneda: str
    region: str
    pasarela: str
    estado: str
    referencia_externa: str | None = None
    motivo_falla: str | None = None

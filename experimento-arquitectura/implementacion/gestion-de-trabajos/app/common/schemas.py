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


class NovedadCreate(BaseModel):
    """Body de `POST /novedades` (DISP-02, ver `escenarios_calidad.md`)."""

    trabajo_id: str
    descripcion: str


class NovedadIdOut(BaseModel):
    """Respuesta de un COMANDO (POST /novedades) — CQS: a lo sumo un id,
    nunca el estado de negocio completo del agregado. Se responde
    `202 Accepted` (ver api/main.py): la Novedad queda PENDIENTE y encolada
    en el Throttler, no se espera la entrega real al CRM."""

    id: uuid.UUID


class NovedadOut(BaseModel):
    """Respuesta de una QUERY (GET /novedades/{id}) — sí expone el estado de
    negocio completo (CQS), a diferencia de `NovedadIdOut`. Agregada para la
    prueba de carga de DISP-02
    (`tests/integracion/test_disp02_throttler.py`), que necesita sondear el
    estado del agregado desde fuera del proceso."""

    id: uuid.UUID
    trabajo_id: uuid.UUID
    descripcion: str
    estado: str
    intentos: int
    creado_en: datetime

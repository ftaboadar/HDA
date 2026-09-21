"""Contrato de serialización HTTP (Pydantic) — distinto del vocabulario de
dominio en `domain/pagos/value_objects.py`. `api/main.py` es el único lugar
que traduce entre ambos; ni `application/` ni `domain/` conocen estas
clases.

`PagoCreate` incluye los campos de `RegistroTrabajoElegible`
(`trabajo_id`, `proveedor_id`, `monto`, `moneda`, `region`) además de
`pasarela` — antes de la separación en microservicios, ese registro lo
poblaba `application/dispatcher_eventos_dominio.py` reaccionando al evento
de dominio `TrabajoFinalizado` dentro del mismo proceso que Gestión de
Trabajos; ahora que Pagos es un microservicio aparte, el cliente HTTP de
`POST /pagos` debe aportar esos datos explícitamente (ver README.md,
sección "Frontera del API")."""

import uuid
from decimal import Decimal

from pydantic import BaseModel


class PagoCreate(BaseModel):
    trabajo_id: uuid.UUID
    proveedor_id: str
    monto: Decimal
    moneda: str
    region: str  # "CO" | "BR" — ver domain/pagos/value_objects.Region
    pasarela: str  # "stripe" | "mercadopago"


class PagoIdOut(BaseModel):
    """Respuesta de un COMANDO (POST /pagos, POST /pagos/{id}/compensar) —
    CQS: a lo sumo un id, no el estado de negocio completo del agregado."""

    id: uuid.UUID


class PagoOut(BaseModel):
    """Respuesta de una QUERY (GET /pagos/{id}) — solo lectura, sí puede
    exponer el estado completo."""

    id: uuid.UUID
    trabajo_id: uuid.UUID
    monto: Decimal
    moneda: str
    region: str
    pasarela: str
    estado: str
    referencia_externa: str | None = None
    motivo_falla: str | None = None

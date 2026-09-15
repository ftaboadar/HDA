"""Fábrica del agregado Trabajo — punto único de creación, garantiza que
todo agregado nuevo nace en un estado consistente (PENDIENTE, sin
eventos)."""

import uuid
from decimal import Decimal

from app.domain.trabajo.trabajo import Trabajo
from app.domain.trabajo.value_objects import (
    MONEDA_POR_REGION,
    Dinero,
    ProveedorId,
    Region,
)


class FabricaTrabajo:
    @staticmethod
    def crear(proveedor_id: ProveedorId, monto: Decimal, region: Region) -> Trabajo:
        moneda = MONEDA_POR_REGION[region]
        return Trabajo(
            id=uuid.uuid4(),
            proveedor_id=proveedor_id,
            monto=Dinero(monto, moneda),
            region=region,
        )

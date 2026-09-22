"""Fábrica del agregado Trabajo — punto único de creación, garantiza que
todo agregado nuevo nace en un estado consistente (PENDIENTE, sin
eventos)."""

import uuid
from decimal import Decimal

from app.ciclo_vida.domain.trabajo import Trabajo
from app.ciclo_vida.domain.value_objects import (
    MONEDA_POR_REGION,
    Dinero,
    ProveedorId,
    Region,
)


class FabricaTrabajo:
    @staticmethod
    def crear(
        monto: Decimal, region: Region, proveedor_id: ProveedorId | None = None
    ) -> Trabajo:
        moneda = MONEDA_POR_REGION[region]
        return Trabajo(
            id=uuid.uuid4(),
            monto=Dinero(monto, moneda),
            region=region,
            proveedor_id=proveedor_id,
        )

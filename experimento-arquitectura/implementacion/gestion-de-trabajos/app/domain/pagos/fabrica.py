"""Fábrica del agregado Pago — punto único de creación, garantiza que todo
Pago nuevo nace en estado PENDIENTE, sin referencia externa ni motivo de
falla."""

import uuid

from app.domain.pagos.pago import Pago
from app.domain.pagos.value_objects import Pasarela
from app.domain.trabajo.value_objects import Dinero, Region, TrabajoId


class FabricaPago:
    @staticmethod
    def crear(
        trabajo_id: TrabajoId, monto: Dinero, region: Region, pasarela: Pasarela
    ) -> Pago:
        return Pago(
            id=uuid.uuid4(),
            trabajo_id=trabajo_id,
            monto=monto,
            region=region,
            pasarela=pasarela,
        )

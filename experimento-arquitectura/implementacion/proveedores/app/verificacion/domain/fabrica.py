"""Fábrica del agregado Verificacion — punto único de creación, garantiza
que todo agregado nuevo nace en un estado consistente (PENDIENTE, sin
intentos)."""

import uuid

from app.verificacion.domain.value_objects import ProveedorId, TipoVerificador
from app.verificacion.domain.verificacion import Verificacion


class FabricaVerificacion:
    @staticmethod
    def crear(proveedor_id: ProveedorId, tipo_verificador: TipoVerificador) -> Verificacion:
        return Verificacion(
            id=uuid.uuid4(),
            proveedor_id=proveedor_id,
            tipo_verificador=tipo_verificador,
        )

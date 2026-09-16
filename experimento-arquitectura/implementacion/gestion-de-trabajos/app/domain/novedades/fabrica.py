"""Fábrica del agregado Novedad — punto único de creación, garantiza que
toda `Novedad` nueva nace en un estado consistente (PENDIENTE, 0 intentos,
sin eventos). Mismo principio que `FabricaTrabajo`."""

import uuid

from app.domain.novedades.novedad import Novedad
from app.domain.trabajo.value_objects import TrabajoId


class FabricaNovedad:
    @staticmethod
    def crear(trabajo_id: TrabajoId, descripcion: str) -> Novedad:
        if not descripcion:
            raise ValueError("descripcion no puede estar vacía")
        return Novedad(id=uuid.uuid4(), trabajo_id=trabajo_id, descripcion=descripcion)

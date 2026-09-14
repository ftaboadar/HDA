"""Base de Entity: igualdad por identidad (id), no por valor — a diferencia
de ValueObject. Sin dependencias de framework."""

from __future__ import annotations

import uuid
from typing import Any


class Entity:
    def __init__(self, id: uuid.UUID) -> None:
        self.id = id

    def __eq__(self, otro: Any) -> bool:
        if not isinstance(otro, Entity):
            return NotImplemented
        return type(self) is type(otro) and self.id == otro.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

"""Base de Entity: igualdad por identidad (id), no por valor — a diferencia
de ValueObject. Sin dependencias de framework, sin imports de otro
microservicio: cada Bounded Context (ver 03-contextos-acotados-TO-BE.cml)
tiene su propio seedwork independiente, aunque el patrón se parezca al de
`implementacion/DISP-03/app/domain/seedwork/` — es deliberado no compartir
código entre servicios, cada uno es su propio contexto acotado."""

from __future__ import annotations

import uuid


class Entity:
    def __init__(self, id: uuid.UUID) -> None:
        self.id = id

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Entity):
            return NotImplemented
        return type(self) is type(otro) and self.id == otro.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

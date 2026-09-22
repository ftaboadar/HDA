"""Base de Value Object: igualdad por valor, inmutable. Sin dependencias de
framework — esto es lo que hace `domain/` verificable como capa hexagonal
pura (Regla 5, criterio 2)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Las subclases son `@dataclass(frozen=True)` — la igualdad por valor y
    la inmutabilidad las da `dataclasses` de la librería estándar, no un
    framework externo."""

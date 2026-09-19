"""Base de Value Object: igualdad por valor, inmutable. Sin dependencias de
framework -- esto es lo que hace `domain/` verificable como capa hexagonal
pura (Regla 5, criterio 2 de REGLAS-DURAS-rubrica-entrega-3.md).

Copia deliberada (no import compartido) del seedwork equivalente en
proveedores/app/domain/seedwork/ -- cada microservicio es su propio Bounded
Context (ver 03-contextos-acotados-TO-BE.cml) y no comparte núcleo de
dominio con otros, ni siquiera clases base tan pequeñas como esta. Compartir
este archivo entre ambos crearía un acoplamiento de compilación/despliegue
entre dos servicios que se supone son independientes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Las subclases son `@dataclass(frozen=True)` -- la igualdad por valor y
    la inmutabilidad las da `dataclasses` de la librería estándar, no un
    framework externo."""

"""Value Objects del agregado PerfilReputacion -- inmutables, con
validación en el constructor, igualdad por valor.

Consistentes con `experimento-arquitectura/contexto/07-vista-informacion.puml`
(paquete "Reputación y Calidad"): `Calificacion *-- Garantia` (VO). `Trabajo`
y `Proveedor` son agregados de OTROS Bounded Contexts (Gestión de Trabajos,
Proveedores) -- aquí solo se referencian por id (`ProveedorId`, `TrabajoId`),
nunca por composición, tal como exige el diagrama para referencias entre
agregados de módulos distintos."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.seedwork.value_object import ValueObject


@dataclass(frozen=True)
class ProveedorId(ValueObject):
    """Referencia por id al agregado `Proveedor` del Bounded Context
    Proveedores -- ver 07-vista-informacion.puml: `PerfilReputacion ..>
    Proveedor : referencia (id)`. Es también el identificador del propio
    agregado `PerfilReputacion` (1 perfil por proveedor)."""

    valor: str

    def __post_init__(self) -> None:
        if not self.valor:
            raise ValueError("ProveedorId no puede estar vacío")

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True)
class TrabajoId(ValueObject):
    """Referencia por id al agregado `Trabajo` del Bounded Context Gestión
    de Trabajos -- ver 07-vista-informacion.puml: `Calificacion ..> Trabajo
    : referencia (id)`."""

    valor: str

    def __post_init__(self) -> None:
        if not self.valor:
            raise ValueError("TrabajoId no puede estar vacío")

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True)
class Garantia(ValueObject):
    """Ver 07-vista-informacion.puml: `Calificacion *-- Garantia`. Modelado
    aquí como VO mínimo (plazo en días) -- el enunciado y los diagramas no
    detallan reglas de garantía más allá de su existencia; no se inventa
    lógica de negocio adicional no pedida (ver reglas de comportamiento de
    `.claude/agents/implementador-ddd.md`: "no implementes nada que no esté
    anclado a una necesidad real del dominio ya modelado")."""

    plazo_dias: int

    def __post_init__(self) -> None:
        if self.plazo_dias < 0:
            raise ValueError("Garantia.plazo_dias no puede ser negativo")

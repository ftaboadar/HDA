"""Puerto genérico de repositorio — cada agregado define su propia interfaz
concreta (ver app/domain/trabajo/repository.py y app/domain/pagos/repository.py)
siguiendo esta forma; no se fuerza herencia porque Python no exige ABC
genérica para que el patrón funcione, pero queda documentado el contrato
esperado aquí."""

import abc
from typing import Generic, TypeVar

T = TypeVar("T")
IdT = TypeVar("IdT")


class IRepository(abc.ABC, Generic[T, IdT]):
    @abc.abstractmethod
    def guardar(self, entidad: T) -> None: ...

    @abc.abstractmethod
    def obtener_por_id(self, id: IdT) -> T | None: ...

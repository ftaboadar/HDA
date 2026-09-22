from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class EstadoSuscripcionDTO:
    id_cliente: str
    saldo_total: float
    cantidad_cargos: int

class ConsultaEstadoSuscripcion(ABC):
    @abstractmethod
    def obtener_estado(self, id_cliente: str) -> EstadoSuscripcionDTO:
        pass

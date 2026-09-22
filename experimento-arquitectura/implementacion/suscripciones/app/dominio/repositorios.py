from abc import ABC, abstractmethod
from app.dominio.entidades import Suscripcion

class RepositorioSuscripciones(ABC):
    @abstractmethod
    def obtener_por_cliente(self, id_cliente: str) -> Suscripcion:
        pass

    @abstractmethod
    def guardar(self, suscripcion: Suscripcion):
        pass

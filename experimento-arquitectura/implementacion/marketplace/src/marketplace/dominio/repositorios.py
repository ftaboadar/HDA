from abc import ABC, abstractmethod
from marketplace.dominio.entidades import Marketplace
import uuid

class RepositorioMarketplace(ABC):
    @abstractmethod
    def obtener_por_solicitud_id(self, solicitud_id: uuid.UUID) -> Marketplace:
        pass
    
    @abstractmethod
    def guardar(self, marketplace: Marketplace):
        pass

from abc import ABC, abstractmethod
from typing import Optional
from .entities import Suscripcion


class SuscripcionRepository(ABC):
    @abstractmethod
    def get(self, id: str) -> Optional[Suscripcion]:
        pass

    @abstractmethod
    def save(self, suscripcion: Suscripcion):
        pass

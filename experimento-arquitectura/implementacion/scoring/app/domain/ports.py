from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from app.domain.models import FotografoScoring

class ScoringRepository(ABC):
    @abstractmethod
    def get_by_fotografo_id(self, fotografo_id: UUID) -> Optional[FotografoScoring]:
        pass
    
    @abstractmethod
    def save(self, scoring: FotografoScoring) -> None:
        pass

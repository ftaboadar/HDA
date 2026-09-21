import uuid
from typing import Optional
from app.infrastructure.persistence.saga_repository_sqlalchemy import (
    SagaRepositorySQLAlchemy,
)
from app.domain.workflow.saga import SagaInstancia


class ConsultarSaga:
    def __init__(self, repo: SagaRepositorySQLAlchemy):
        self.repo = repo

    def ejecutar(self, saga_id: str) -> Optional[SagaInstancia]:
        return self.repo.obtener_por_id(uuid.UUID(saga_id))

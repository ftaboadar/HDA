"""Query — reemplaza `GET /dlq`."""

from app.verificacion.domain.repository import IVerificacionRepository
from app.verificacion.domain.verificacion import Verificacion


class ListarDLQ:
    def __init__(self, repo: IVerificacionRepository) -> None:
        self._repo = repo

    def ejecutar(self) -> list[Verificacion]:
        return self._repo.listar_en_dlq()

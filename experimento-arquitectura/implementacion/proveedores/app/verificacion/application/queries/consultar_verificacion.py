"""Query — solo lee, no muta estado (CQS). Reemplaza
`GET /verificaciones/{id}`."""

from app.verificacion.domain.repository import IVerificacionRepository
from app.verificacion.domain.value_objects import VerificacionId
from app.verificacion.domain.verificacion import Verificacion


class ConsultarVerificacion:
    def __init__(self, repo: IVerificacionRepository) -> None:
        self._repo = repo

    def ejecutar(self, verificacion_id: str) -> Verificacion | None:
        return self._repo.obtener_por_id(VerificacionId.desde_str(verificacion_id))

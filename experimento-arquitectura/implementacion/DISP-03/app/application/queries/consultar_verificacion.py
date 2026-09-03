"""Query — solo lee, no muta estado (CQS). Reemplaza
`GET /verificaciones/{id}`."""

from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import VerificacionId
from app.domain.verificacion.verificacion import Verificacion


class ConsultarVerificacion:
    def __init__(self, repo: IVerificacionRepository) -> None:
        self._repo = repo

    def ejecutar(self, verificacion_id: str) -> Verificacion | None:
        return self._repo.obtener_por_id(VerificacionId.desde_str(verificacion_id))

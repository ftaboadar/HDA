"""Query — solo lee, no muta estado (CQS). Reemplaza `GET /trabajos/{id}`."""

from app.domain.ciclo_vida.repository import ITrabajoRepository
from app.domain.ciclo_vida.trabajo import Trabajo
from app.domain.ciclo_vida.value_objects import TrabajoId


class ConsultarTrabajo:
    def __init__(self, repo: ITrabajoRepository) -> None:
        self._repo = repo

    def ejecutar(self, trabajo_id: str) -> Trabajo | None:
        return self._repo.obtener_por_id(TrabajoId.desde_str(trabajo_id))

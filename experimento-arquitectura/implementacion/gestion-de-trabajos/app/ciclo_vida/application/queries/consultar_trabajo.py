"""Query — solo lee, no muta estado (CQS). Reemplaza `GET /trabajos/{id}`."""

from app.ciclo_vida.domain.repository import ITrabajoRepository
from app.ciclo_vida.domain.trabajo import Trabajo
from app.ciclo_vida.domain.value_objects import TrabajoId


class ConsultarTrabajo:
    def __init__(self, repo: ITrabajoRepository) -> None:
        self._repo = repo

    def ejecutar(self, trabajo_id: str) -> Trabajo | None:
        return self._repo.obtener_por_id(TrabajoId.desde_str(trabajo_id))

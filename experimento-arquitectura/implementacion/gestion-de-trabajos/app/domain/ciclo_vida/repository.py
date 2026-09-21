"""Puerto (interfaz) del repositorio de Trabajo — el dominio depende de esta
abstracción, nunca de SQLAlchemy. El adaptador concreto vive en
app/infrastructure/persistence/trabajo_repository_sqlalchemy.py."""

import abc

from app.domain.ciclo_vida.trabajo import Trabajo
from app.domain.ciclo_vida.value_objects import TrabajoId


class ITrabajoRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, trabajo: Trabajo) -> None: ...

    @abc.abstractmethod
    def obtener_por_id(self, id: TrabajoId) -> Trabajo | None: ...

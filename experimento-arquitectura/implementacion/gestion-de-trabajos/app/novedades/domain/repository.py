"""Puerto (interfaz) del repositorio de Novedad — el dominio y la capa de
aplicación (el `Throttler`, en particular) dependen de esta abstracción,
nunca de SQLAlchemy directamente. El adaptador concreto vive en
`app/infrastructure/persistence/novedad_repository_sqlalchemy.py`."""

import abc

from app.novedades.domain.novedad import Novedad
from app.novedades.domain.value_objects import NovedadId


class INovedadRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, novedad: Novedad) -> None: ...

    @abc.abstractmethod
    def obtener_por_id(self, id: NovedadId) -> Novedad | None: ...

    @abc.abstractmethod
    def listar_pendientes(self) -> list[Novedad]:
        """Usado, por ejemplo, para reconstruir la cola del Throttler tras
        un reinicio del proceso (no implementado en este skeleton — ver
        README.md, "Qué falta"; el `asyncio.Queue` en memoria de
        `infrastructure/messaging/throttler.py` se pierde si el proceso
        muere con novedades PENDIENTES sin encolar aún)."""
        ...

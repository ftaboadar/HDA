"""Puerto (interfaz) del repositorio de Pago — el dominio depende de esta
abstracción, nunca de SQLAlchemy. El adaptador concreto vive en
app/infrastructure/persistence/pago_repository_sqlalchemy.py."""

import abc

from app.domain.pagos.pago import Pago
from app.domain.pagos.value_objects import PagoId
from app.domain.trabajo.value_objects import TrabajoId


class IPagoRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, pago: Pago) -> None: ...

    @abc.abstractmethod
    def obtener_por_id(self, id: PagoId) -> Pago | None: ...

    @abc.abstractmethod
    def listar_por_trabajo(self, trabajo_id: TrabajoId) -> list[Pago]: ...

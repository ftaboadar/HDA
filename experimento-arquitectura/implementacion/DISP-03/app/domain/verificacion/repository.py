"""Puerto (interfaz) del repositorio de Verificacion — el dominio depende de
esta abstracción, nunca de SQLAlchemy. El adaptador concreto vive en
app/infrastructure/persistence/verificacion_repository_sqlalchemy.py."""

import abc

from app.domain.verificacion.value_objects import ProveedorId, VerificacionId
from app.domain.verificacion.verificacion import Verificacion


class IVerificacionRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, verificacion: Verificacion) -> None: ...

    @abc.abstractmethod
    def obtener_por_id(self, id: VerificacionId) -> Verificacion | None: ...

    @abc.abstractmethod
    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> list[Verificacion]: ...

    @abc.abstractmethod
    def listar_en_dlq(self) -> list[Verificacion]: ...

    @abc.abstractmethod
    def listar(
        self, estado: str | None = None, proveedor_id: ProveedorId | None = None
    ) -> list[Verificacion]: ...

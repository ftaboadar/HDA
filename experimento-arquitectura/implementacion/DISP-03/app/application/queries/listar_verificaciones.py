"""Query — reemplaza `GET /verificaciones`."""

from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import ProveedorId
from app.domain.verificacion.verificacion import Verificacion


class ListarVerificaciones:
    def __init__(self, repo: IVerificacionRepository) -> None:
        self._repo = repo

    def ejecutar(
        self, estado: str | None = None, proveedor_id: str | None = None
    ) -> list[Verificacion]:
        return self._repo.listar(
            estado=estado,
            proveedor_id=ProveedorId(proveedor_id) if proveedor_id else None,
        )

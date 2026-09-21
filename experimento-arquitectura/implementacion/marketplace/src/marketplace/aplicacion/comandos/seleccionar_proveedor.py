from dataclasses import dataclass
import uuid
from marketplace.dominio.repositorios import RepositorioMarketplace
from marketplace.infraestructura.despachadores import Despachador
from marketplace.dominio.eventos import ProveedorSeleccionado


@dataclass
class SeleccionarProveedor:
    solicitud_id: uuid.UUID
    proveedor_id: uuid.UUID


class SeleccionarProveedorHandler:
    def __init__(self, repositorio: RepositorioMarketplace, despachador: Despachador):
        self.repositorio = repositorio
        self.despachador = despachador

    def handle(self, comando: SeleccionarProveedor):
        mkp = self.repositorio.obtener_por_solicitud_id(comando.solicitud_id)
        mkp.seleccionar_proveedor(comando.proveedor_id)
        self.repositorio.guardar(mkp)

        evento = ProveedorSeleccionado(
            solicitud_id=comando.solicitud_id, proveedor_id=comando.proveedor_id
        )
        self.despachador.publicar_seleccion(evento)

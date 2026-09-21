from dataclasses import dataclass
import uuid
from marketplace.dominio.repositorios import RepositorioMarketplace


@dataclass
class ObtenerMarketplace:
    solicitud_id: uuid.UUID


class ObtenerMarketplaceHandler:
    def __init__(self, repositorio: RepositorioMarketplace):
        self.repositorio = repositorio

    def handle(self, consulta: ObtenerMarketplace):
        return self.repositorio.obtener_por_solicitud_id(consulta.solicitud_id)

from dataclasses import dataclass
import uuid
from marketplace.dominio.repositorios import RepositorioMarketplace
from marketplace.infraestructura.despachadores import Despachador
from marketplace.dominio.eventos import SolicitudDiagnosticada


@dataclass
class DiagnosticarSolicitud:
    solicitud_id: uuid.UUID
    descripcion: str
    severidad: str


class DiagnosticarSolicitudHandler:
    def __init__(self, repositorio: RepositorioMarketplace, despachador: Despachador):
        self.repositorio = repositorio
        self.despachador = despachador

    def handle(self, comando: DiagnosticarSolicitud):
        mkp = self.repositorio.obtener_por_solicitud_id(comando.solicitud_id)
        mkp.diagnosticar(comando.descripcion, comando.severidad)
        self.repositorio.guardar(mkp)

        evento = SolicitudDiagnosticada(
            solicitud_id=comando.solicitud_id,
            descripcion_diagnostico=comando.descripcion,
            severidad=comando.severidad,
        )
        self.despachador.publicar_diagnostico(evento)

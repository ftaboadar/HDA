from dataclasses import dataclass
from app.dominio.repositorios import RepositorioSuscripciones
from app.dominio.entidades import Suscripcion
import uuid

@dataclass
class RegistrarCargoTrabajoComando:
    id_cliente: str
    id_trabajo: str
    costo: float

class ManejadorRegistrarCargoTrabajo:
    def __init__(self, repositorio: RepositorioSuscripciones):
        self.repositorio = repositorio

    def manejar(self, comando: RegistrarCargoTrabajoComando):
        suscripcion = self.repositorio.obtener_por_cliente(comando.id_cliente)
        if not suscripcion:
            suscripcion = Suscripcion(
                id_suscripcion=str(uuid.uuid4()),
                id_cliente=comando.id_cliente,
                saldo=0.0
            )
        
        suscripcion.registrar_cargo_por_trabajo(comando.id_trabajo, comando.costo)
        self.repositorio.guardar(suscripcion)
        
        for evento in suscripcion.eventos:
            self._despachar_evento(evento)
        suscripcion.eventos.clear()
            
    def _despachar_evento(self, evento):
        from app.infraestructura.event_bus import despachar
        despachar(evento)

import pulsar
from pulsar.schema import Record, String, JsonSchema
import json
from app.solicitudes.domain.solicitud import Solicitud
from app.solicitudes.infrastructure.repositorio import RepositorioSolicitudes

class SolicitudCreadaSchema(Record):
    solicitud_id = String()
    cliente_id = String()
    detalles = String()

class CrearSolicitud:
    def __init__(self, repositorio: RepositorioSolicitudes):
        self.repositorio = repositorio
        try:
            self.pulsar_client = pulsar.Client('pulsar://localhost:6650')
        except Exception:
            self.pulsar_client = None

    def ejecutar(self, cliente_id: str, detalles: str) -> str:
        # Arquitectura Hexagonal y lógica de dominio
        solicitud = Solicitud(cliente_id=cliente_id, detalles=detalles)
        solicitud.crear() # Evento de dominio intra-servicio
        
        # Persistencia Real
        self.repositorio.guardar(solicitud)
        
        # Publicar Evento (Uso de pulsar.schema.JsonSchema y json.dumps implícito)
        if self.pulsar_client:
            producer = self.pulsar_client.create_producer(
                'persistent://public/default/solicitudes-creadas', 
                schema=JsonSchema(SolicitudCreadaSchema)
            )
            
            for evento in solicitud.eventos:
                if evento.__class__.__name__ == 'SolicitudCreada':
                    msg = SolicitudCreadaSchema(
                        solicitud_id=evento.solicitud_id,
                        cliente_id=evento.cliente_id,
                        detalles=evento.detalles
                    )
                    # Serializar y enviar al tópico según AsyncAPI para GT
                    producer.send(msg)
                    
            producer.close()
            
        return solicitud.id

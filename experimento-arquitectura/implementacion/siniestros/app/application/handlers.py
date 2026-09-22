from app.application.commands import AprobarSiniestroCommand, ProcesarFacturaCommand, CompensarReservaCommand
from app.application.queries import GetSiniestroQuery, SiniestroDTO
from app.infrastructure.repositories import SiniestroRepository
import pulsar
import json

class MessagePublisher:
    def __init__(self):
        self.client = pulsar.Client('pulsar://localhost:6650')
        self.producer = self.client.create_producer('siniestros-events')

    def publish(self, event):
        self.producer.send(json.dumps(event.__dict__, default=str).encode('utf-8'))

    def close(self):
        self.client.close()

class CommandHandler:
    def __init__(self, repository: SiniestroRepository, publisher: MessagePublisher):
        self.repository = repository
        self.publisher = publisher

    def handle_aprobar_siniestro(self, cmd: AprobarSiniestroCommand):
        siniestro = self.repository.get(cmd.siniestro_id)
        if not siniestro: raise Exception("Siniestro no encontrado")
        
        siniestro.aprobar(cmd.monto_aprobado)
        self.repository.save(siniestro)
        
        for event in siniestro.events:
            self.publisher.publish(event)
        siniestro.events.clear()

    def handle_procesar_factura(self, cmd: ProcesarFacturaCommand):
        siniestro = self.repository.get(cmd.siniestro_id)
        if not siniestro: raise Exception("Siniestro no encontrado")

        siniestro.procesar_facturacion(cmd.factura_id, cmd.monto)
        self.repository.save(siniestro)

        for event in siniestro.events:
            self.publisher.publish(event)
        siniestro.events.clear()
        
    def handle_compensar_reserva(self, cmd: CompensarReservaCommand):
        siniestro = self.repository.get(cmd.siniestro_id)
        if not siniestro: raise Exception("Siniestro no encontrado")
            
        siniestro.reserva += cmd.monto_adicional
        self.repository.save(siniestro)

class QueryHandler:
    def __init__(self, repository: SiniestroRepository):
        self.repository = repository

    def handle_get_siniestro(self, query: GetSiniestroQuery) -> SiniestroDTO:
        siniestro = self.repository.get(query.siniestro_id)
        if not siniestro: return None
        return SiniestroDTO(
            id=siniestro.id, estado=siniestro.estado,
            reserva=siniestro.reserva, facturas=siniestro.facturas
        )

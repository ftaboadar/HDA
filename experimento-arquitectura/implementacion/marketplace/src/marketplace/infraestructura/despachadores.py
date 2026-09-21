import pulsar
from pulsar.schema import JsonSchema
from marketplace.infraestructura.schema.v1.eventos import (
    SolicitudDiagnosticadaPayload,
    ProveedorSeleccionadoPayload,
)


class Despachador:
    def __init__(self, broker_url: str):
        self.client = pulsar.Client(broker_url)

    def publicar_diagnostico(self, evento):
        producer = self.client.create_producer(
            "persistent://public/default/solicitud-diagnosticada",
            schema=JsonSchema(SolicitudDiagnosticadaPayload),
        )
        producer.send(
            SolicitudDiagnosticadaPayload(
                solicitud_id=str(evento.solicitud_id),
                descripcion_diagnostico=evento.descripcion_diagnostico,
                severidad=evento.severidad,
            )
        )
        producer.close()

    def publicar_seleccion(self, evento):
        producer = self.client.create_producer(
            "persistent://public/default/proveedor-seleccionado",
            schema=JsonSchema(ProveedorSeleccionadoPayload),
        )
        producer.send(
            ProveedorSeleccionadoPayload(
                solicitud_id=str(evento.solicitud_id),
                proveedor_id=str(evento.proveedor_id),
            )
        )
        producer.close()

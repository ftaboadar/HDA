from typing import List
from .events import DomainEvent, SiniestroAprobado, FacturacionProcesada, CompensacionReservaRequerida

class Siniestro:
    def __init__(self, siniestro_id: str, cliente_id: str, monto_reclamado: float, estado: str = "PENDIENTE", reserva: float = 0.0):
        self.id = siniestro_id
        self.cliente_id = cliente_id
        self.monto_reclamado = monto_reclamado
        self.estado = estado
        self.reserva = reserva
        self.facturas = []
        self.events: List[DomainEvent] = []

    def aprobar(self, monto_aprobado: float):
        if self.estado != "PENDIENTE":
            raise Exception("Solo se pueden aprobar siniestros pendientes")
        
        self.estado = "APROBADO"
        self.reserva = monto_aprobado
        self.events.append(SiniestroAprobado(siniestro_id=self.id, monto_aprobado=monto_aprobado))

    def procesar_facturacion(self, factura_id: str, monto_factura: float):
        if self.estado != "APROBADO":
            raise Exception("El siniestro debe estar aprobado")
        
        self.facturas.append({"id": factura_id, "monto": monto_factura})
        self.events.append(FacturacionProcesada(siniestro_id=self.id, factura_id=factura_id, monto=monto_factura))

        if monto_factura > self.reserva:
            diferencia = monto_factura - self.reserva
            self.events.append(CompensacionReservaRequerida(
                siniestro_id=self.id, 
                monto_compensacion=diferencia,
                motivo="Facturación excede reserva"
            ))
            self.reserva = monto_factura

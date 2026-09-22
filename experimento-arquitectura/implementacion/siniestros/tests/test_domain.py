import pytest
from app.domain.entities import Siniestro
from app.domain.events import CompensacionReservaRequerida

def test_aprobar_siniestro():
    siniestro = Siniestro(siniestro_id="1", cliente_id="C1", monto_reclamado=1000.0)
    siniestro.aprobar(800.0)
    assert siniestro.estado == "APROBADO"
    assert siniestro.reserva == 800.0
    assert len(siniestro.events) == 1
    assert siniestro.events[0].monto_aprobado == 800.0

def test_procesar_factura_genera_compensacion():
    siniestro = Siniestro(siniestro_id="1", cliente_id="C1", monto_reclamado=1000.0)
    siniestro.aprobar(500.0) 
    siniestro.events.clear()

    siniestro.procesar_facturacion("F1", 600.0)
    assert len(siniestro.facturas) == 1
    
    eventos_compensacion = [e for e in siniestro.events if isinstance(e, CompensacionReservaRequerida)]
    assert len(eventos_compensacion) == 1
    assert eventos_compensacion[0].monto_compensacion == 100.0
    assert siniestro.reserva == 600.0

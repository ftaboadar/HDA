import uuid
from marketplace.dominio.entidades import Marketplace

def test_diagnosticar():
    mkp = Marketplace(solicitud_id=uuid.uuid4())
    mkp.diagnosticar("Fuga de agua", "Alta")
    assert mkp.diagnostico is not None
    assert mkp.diagnostico.descripcion == "Fuga de agua"

def test_agregar_cotizacion():
    mkp = Marketplace(solicitud_id=uuid.uuid4())
    mkp.agregar_cotizacion(uuid.uuid4(), 100.0, "Mañana")
    assert len(mkp.cotizaciones) == 1

def test_seleccionar_proveedor():
    mkp = Marketplace(solicitud_id=uuid.uuid4())
    prov_id = uuid.uuid4()
    mkp.seleccionar_proveedor(prov_id)
    assert mkp.proveedor_seleccionado_id == prov_id

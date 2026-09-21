import uuid
from marketplace.aplicacion.comandos.diagnosticar_solicitud import (
    DiagnosticarSolicitud,
    DiagnosticarSolicitudHandler,
)
from marketplace.aplicacion.comandos.seleccionar_proveedor import (
    SeleccionarProveedor,
    SeleccionarProveedorHandler,
)
from marketplace.dominio.entidades import Marketplace
from marketplace.dominio.repositorios import RepositorioMarketplace


class MockRepositorio(RepositorioMarketplace):
    def __init__(self):
        self.data = {}

    def obtener_por_solicitud_id(self, solicitud_id):
        if solicitud_id not in self.data:
            self.data[solicitud_id] = Marketplace(solicitud_id=solicitud_id)
        return self.data[solicitud_id]

    def guardar(self, marketplace):
        self.data[marketplace.solicitud_id] = marketplace


class MockDespachador:
    def publicar_diagnostico(self, evento):
        pass

    def publicar_seleccion(self, evento):
        pass


def test_diagnosticar_solicitud():
    repo = MockRepositorio()
    desp = MockDespachador()
    handler = DiagnosticarSolicitudHandler(repo, desp)
    solicitud_id = uuid.uuid4()

    comando = DiagnosticarSolicitud(
        solicitud_id=solicitud_id, descripcion="Falla", severidad="Alta"
    )
    handler.handle(comando)

    assert repo.data[solicitud_id].diagnostico is not None
    assert repo.data[solicitud_id].diagnostico.descripcion == "Falla"


def test_seleccionar_proveedor():
    repo = MockRepositorio()
    desp = MockDespachador()
    handler = SeleccionarProveedorHandler(repo, desp)
    solicitud_id = uuid.uuid4()
    proveedor_id = uuid.uuid4()

    comando = SeleccionarProveedor(solicitud_id=solicitud_id, proveedor_id=proveedor_id)
    handler.handle(comando)

    assert repo.data[solicitud_id].proveedor_seleccionado_id == proveedor_id

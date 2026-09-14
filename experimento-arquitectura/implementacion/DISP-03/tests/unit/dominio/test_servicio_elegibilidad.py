"""Prueba del servicio de dominio ServicioDeElegibilidad — usa un
repositorio falso en memoria (implementa IVerificacionRepository) en vez de
Postgres: es lo que permite probar la lógica de negocio sin infraestructura,
la ventaja concreta de que domain/ no dependa de SQLAlchemy."""

from app.domain.verificacion.fabrica import FabricaVerificacion
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.servicio_elegibilidad import ServicioDeElegibilidad
from app.domain.verificacion.value_objects import ProveedorId, ResultadoIntento, TipoVerificador
from app.domain.verificacion.verificacion import Verificacion


class RepositorioEnMemoria(IVerificacionRepository):
    def __init__(self) -> None:
        self._filas: dict = {}

    def guardar(self, verificacion: Verificacion) -> None:
        self._filas[verificacion.id] = verificacion

    def obtener_por_id(self, id):
        return self._filas.get(id.valor)

    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.proveedor_id == proveedor_id]

    def listar_en_dlq(self) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.estado.value == "FALLIDA_DLQ"]

    def listar(self, estado=None, proveedor_id=None) -> list[Verificacion]:
        return list(self._filas.values())


def test_proveedor_sin_verificaciones_no_esta_habilitado():
    repo = RepositorioEnMemoria()
    servicio = ServicioDeElegibilidad(repo)
    assert servicio.proveedor_esta_habilitado(ProveedorId("prov-x")) is False


def test_proveedor_habilitado_solo_si_todas_completadas():
    repo = RepositorioEnMemoria()
    proveedor = ProveedorId("prov-y")

    v1 = FabricaVerificacion.crear(proveedor, TipoVerificador.POLICIA)
    v1.registrar_intento(ResultadoIntento.EXITOSO, duracion_ms=10)
    repo.guardar(v1)

    v2 = FabricaVerificacion.crear(proveedor, TipoVerificador.RUES)
    repo.guardar(v2)  # sigue PENDIENTE

    servicio = ServicioDeElegibilidad(repo)
    assert servicio.proveedor_esta_habilitado(proveedor) is False

    v2.registrar_intento(ResultadoIntento.EXITOSO, duracion_ms=10)
    repo.guardar(v2)

    assert servicio.proveedor_esta_habilitado(proveedor) is True

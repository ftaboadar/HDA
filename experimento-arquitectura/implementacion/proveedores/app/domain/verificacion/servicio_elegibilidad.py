"""Servicio de dominio — vive fuera de un único agregado porque la decisión
de habilitación cruza múltiples instancias de Verificacion para el mismo
proveedor. Ver 11-implementacion-ddd-verificacion.md, sección 2 para la
nota de alcance: aquí se simplifica a un booleano ("¿todas completadas?"),
no al motor de reglas de habilitación por servicio/zona completo — eso es
negocio adicional, no patrón DDD adicional, y no lo exige la Regla 5."""

from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import EstadoVerificacion, ProveedorId


class ServicioDeElegibilidad:
    def __init__(self, repo: IVerificacionRepository) -> None:
        self._repo = repo

    def proveedor_esta_habilitado(self, proveedor_id: ProveedorId) -> bool:
        verificaciones = self._repo.listar_por_proveedor(proveedor_id)
        if not verificaciones:
            return False
        return all(v.estado == EstadoVerificacion.COMPLETADA for v in verificaciones)

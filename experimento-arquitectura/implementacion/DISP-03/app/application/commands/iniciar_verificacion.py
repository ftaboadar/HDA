"""Comando — reemplaza el cuerpo de `POST /verificaciones` que antes tocaba
`SessionLocal`/`VerificacionORM` directo desde la ruta HTTP."""

from datetime import datetime, timezone

from app.common.publicador import Publicador
from app.domain.verificacion.fabrica import FabricaVerificacion
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import ProveedorId, TipoVerificador
from app.domain.verificacion.verificacion import Verificacion


class IniciarVerificacion:
    def __init__(self, repo: IVerificacionRepository, publicador: Publicador) -> None:
        self._repo = repo
        self._publicador = publicador

    async def ejecutar(self, proveedor_id: str, tipo_verificador: str) -> Verificacion:
        verificacion = FabricaVerificacion.crear(
            proveedor_id=ProveedorId(proveedor_id),
            tipo_verificador=TipoVerificador(tipo_verificador),
        )
        self._repo.guardar(verificacion)

        # Evento de INTEGRACIÓN (no de dominio): cruza del adaptador de
        # entrada al worker vía el broker — transporte sin cambios respecto
        # a la versión anterior, ver app/common/mq.py.
        await self._publicador.publicar_solicitud(
            {
                "verificacion_id": str(verificacion.id),
                "proveedor_id": proveedor_id,
                "tipo_verificador": tipo_verificador,
                "solicitado_en": datetime.now(timezone.utc).isoformat(),
            }
        )
        return verificacion

"""Comando — reemplaza el cuerpo de `POST /dlq/{id}/reprocesar`."""

from datetime import datetime, timezone

from app.common.publicador import Publicador
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import VerificacionId
from app.domain.verificacion.verificacion import Verificacion


class VerificacionNoEncontrada(Exception):
    pass


class ReprocesarDesdeDLQ:
    def __init__(self, repo: IVerificacionRepository, publicador: Publicador) -> None:
        self._repo = repo
        self._publicador = publicador

    async def ejecutar(self, verificacion_id: str) -> Verificacion:
        vid = VerificacionId.desde_str(verificacion_id)
        verificacion = self._repo.obtener_por_id(vid)
        if verificacion is None:
            raise VerificacionNoEncontrada(verificacion_id)

        verificacion.reprocesar()  # valida el invariante: solo desde FALLIDA_DLQ
        self._repo.guardar(verificacion)

        await self._publicador.publicar_solicitud(
            {
                "verificacion_id": str(verificacion.id),
                "proveedor_id": str(verificacion.proveedor_id),
                "tipo_verificador": verificacion.tipo_verificador.value,
                "solicitado_en": datetime.now(timezone.utc).isoformat(),
                "reprocesado": True,
            }
        )
        return verificacion

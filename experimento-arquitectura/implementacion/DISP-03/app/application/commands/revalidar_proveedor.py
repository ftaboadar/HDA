"""Comando — exigido explícitamente por el enunciado: "Re-validaciones:
periódicas, por vencimiento de certificados y por novedades de personal, un
técnico nuevo... no puede atender trabajos hasta ser verificado". Crea una
nueva `Verificacion` (vía la fábrica) para el proveedor afectado, dejando
las anteriores como historial — nunca sobreescribe.

Alcance de este PoC: expone el comando y un endpoint manual
(`POST /proveedores/{id}/revalidar`) para disparar la revalidación — el
disparo automático por vencimiento (cron/Cloud Scheduler) o por alta de
técnico nuevo, que el documento de propuesta describe como los otros dos
disparadores, no se implementa aquí (es integración con un scheduler
externo, no parte de los 5 criterios de la Regla 5)."""

from datetime import datetime, timezone

from app.common.publicador import Publicador
from app.domain.verificacion.fabrica import FabricaVerificacion
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import MotivoRevalidacion, ProveedorId, TipoVerificador
from app.domain.verificacion.verificacion import Verificacion


class RevalidarProveedor:
    def __init__(self, repo: IVerificacionRepository, publicador: Publicador) -> None:
        self._repo = repo
        self._publicador = publicador

    async def ejecutar(
        self,
        proveedor_id: str,
        motivo: MotivoRevalidacion,
        tipo_verificador: str = TipoVerificador.CERTIFICADORA.value,
    ) -> Verificacion:
        verificacion = FabricaVerificacion.crear(
            proveedor_id=ProveedorId(proveedor_id),
            tipo_verificador=TipoVerificador(tipo_verificador),
        )
        self._repo.guardar(verificacion)

        await self._publicador.publicar_solicitud(
            {
                "verificacion_id": str(verificacion.id),
                "proveedor_id": proveedor_id,
                "tipo_verificador": tipo_verificador,
                "solicitado_en": datetime.now(timezone.utc).isoformat(),
                "motivo_revalidacion": motivo.value,
            }
        )
        return verificacion

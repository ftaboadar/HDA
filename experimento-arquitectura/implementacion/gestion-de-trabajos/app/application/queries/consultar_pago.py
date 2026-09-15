"""Query — solo lee, no muta estado (CQS). Reemplaza `GET /pagos/{id}`."""

from app.domain.pagos.pago import Pago
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import PagoId


class ConsultarPago:
    def __init__(self, repo: IPagoRepository) -> None:
        self._repo = repo

    def ejecutar(self, pago_id: str) -> Pago | None:
        return self._repo.obtener_por_id(PagoId.desde_str(pago_id))

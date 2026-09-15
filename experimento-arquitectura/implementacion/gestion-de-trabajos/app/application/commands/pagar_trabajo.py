"""Comando `PagarTrabajo` — usa la Strategy `ReglaRegional` (selecciona la
regla según la región del trabajo) y el Adapter `IPasarelaDePago`
(selecciona la pasarela pedida por el cliente HTTP). Ninguna llamada a
Pulsar aquí: Pagos no tiene tópico propio (12-plan-entrega-4.md sección 3)
— la única comunicación que cruza el proceso es el HTTP síncrono hacia el
mock externo, permitido explícitamente por la sección 3.1 del plan.

Regla 5, criterio 4: este comando ya NO recibe `ITrabajoRepository` (el
repositorio del módulo Trabajo) inyectado — antes lo usaba para leer
`region`/`monto` directamente, acoplando Pagos al repositorio ajeno en vez
de a un evento. Ahora depende solo de `IRegistroTrabajosRepository`
(`app/application/ports/registro_trabajos.py`), poblado exclusivamente por
`application/dispatcher_eventos_dominio.py` al reaccionar al evento de
dominio `TrabajoFinalizado`. Si no hay registro para ese `trabajo_id`, es
porque Pagos nunca fue notificado de que ese trabajo existe/finalizó — el
mismo caso que antes se reportaba como "trabajo no encontrado".

CQS: `ejecutar()` retorna solo el `id` del pago creado.

CORRECCIÓN (encontrada corriendo k6 real contra GCP): `_registro_repo`/
`_pago_repo` son síncronos (SQLAlchemy) — invocados directo dentro de este
`async def` bloqueaban el event loop del worker en cada llamada. Mismo
hallazgo y mismo fix que `crear_trabajo.py` (ver su docstring), aplicado
aquí por consistencia aunque este comando no fue el que ESC-01 midió
directamente."""

from __future__ import annotations

import asyncio
import uuid

from app.application.dispatcher_eventos_dominio import despachar
from app.application.ports.pasarela_de_pago import IPasarelaDePago
from app.application.ports.registro_trabajos import IRegistroTrabajosRepository
from app.common.logging_utils import configurar_logging, log_evento
from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import Pasarela
from app.domain.trabajo.value_objects import Dinero, Region, TrabajoId

logger = configurar_logging("application.commands.pagar_trabajo")


class TrabajoNoEncontrado(Exception):
    pass


class PagarTrabajo:
    def __init__(
        self,
        pago_repo: IPagoRepository,
        registro_repo: IRegistroTrabajosRepository,
        reglas_regionales: dict[Region, ReglaRegional],
        pasarelas: dict[str, IPasarelaDePago],
    ) -> None:
        self._pago_repo = pago_repo
        self._registro_repo = registro_repo
        self._reglas_regionales = reglas_regionales
        self._pasarelas = pasarelas

    async def ejecutar(self, trabajo_id: str, pasarela: str) -> uuid.UUID:
        registro = await asyncio.to_thread(
            self._registro_repo.obtener_por_trabajo, TrabajoId.desde_str(trabajo_id)
        )
        if registro is None:
            raise TrabajoNoEncontrado(trabajo_id)

        regla = self._reglas_regionales.get(registro.region)
        if regla is None:
            raise ValueError(
                f"No hay ReglaRegional configurada para la región {registro.region}"
            )

        pasarela_impl = self._pasarelas.get(pasarela)
        if pasarela_impl is None:
            raise ValueError(f"Pasarela desconocida: {pasarela}")

        pago = FabricaPago.crear(
            trabajo_id=registro.trabajo_id,
            monto=Dinero(registro.monto, registro.moneda),
            region=registro.region,
            pasarela=Pasarela(pasarela),
        )

        # Strategy: valida según la región ANTES de llamar al externo.
        regla.validar(pago)

        # Se persiste PENDIENTE antes de la llamada externa — si el proceso
        # cae entre aquí y la respuesta de la pasarela, el registro de
        # intento de cobro ya quedó trazado (mismo principio que
        # Verificacion en DISP-03: persistir antes de la I/O externa).
        await asyncio.to_thread(self._pago_repo.guardar, pago)

        resultado = await pasarela_impl.cobrar(pago)
        if resultado.exitoso:
            pago.marcar_exitoso(resultado.referencia_externa or "")
        else:
            pago.marcar_fallido(
                resultado.motivo_falla or "error desconocido en la pasarela"
            )
        await asyncio.to_thread(self._pago_repo.guardar, pago)
        await despachar(pago.recoger_eventos())

        log_evento(
            logger,
            "pago_procesado",
            pago_id=str(pago.id),
            trabajo_id=trabajo_id,
            pasarela=pasarela,
            estado=pago.estado.value,
        )
        return pago.id

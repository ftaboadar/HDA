"""Comando `PagarTrabajo` — usa la Strategy `ReglaRegional` (selecciona la
regla según la región del trabajo) y el Adapter `IPasarelaDePago`
(selecciona la pasarela pedida por el cliente HTTP). Este microservicio no
tiene tópico de integración propio — la única comunicación que cruza el
proceso es el HTTP síncrono hacia el mock externo (Stripe/MercadoPago).

Regla 5, criterio 4: este comando NO recibe el repositorio del agregado
`Trabajo` (eso vive en OTRO microservicio, Gestión de Trabajos) — depende
solo de `IRegistroTrabajosRepository`
(`app/application/ports/registro_trabajos.py`), un registro propio de este
servicio. Antes de la separación en microservicios, ese registro lo poblaba
`application/dispatcher_eventos_dominio.py` reaccionando al evento de
DOMINIO `TrabajoFinalizado` intra-proceso; ahora lo puebla `POST /pagos`
(`app/api/main.py`) explícitamente en el mismo request, a partir de los
datos que el cliente HTTP ya conoce del trabajo (ver README.md, sección
"Frontera del API", para la justificación completa de este cableado nuevo).
Si no hay registro para ese `trabajo_id`, es porque nunca se pobló — el
mismo caso que antes se reportaba como "trabajo no encontrado".

CQS: `ejecutar()` retorna solo el `id` del pago creado.

CORRECCIÓN (encontrada corriendo k6 real contra GCP, heredada de
`gestion-de-trabajos/app/application/commands/crear_trabajo.py`):
`_registro_repo`/`_pago_repo` son síncronos (SQLAlchemy) — invocados directo
dentro de este `async def` bloquearían el event loop del worker en cada
llamada, por eso van envueltos en `asyncio.to_thread`."""

from __future__ import annotations

import asyncio
import time
import uuid

from app.application.dispatcher_eventos_dominio import despachar
from app.application.ports.pasarela_de_pago import IPasarelaDePago
from app.application.ports.registro_trabajos import IRegistroTrabajosRepository
from app.common.logging_utils import configurar_logging, log_evento
from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import Dinero, Pasarela, Region, TrabajoId

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
        inicio = time.perf_counter()
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
        log_evento(
            logger,
            "regla_regional_aplicada",
            patron="Strategy",
            regla=type(regla).__name__,
            region=registro.region.value,
            moneda=registro.moneda,
            pago_id=str(pago.id),
            trabajo_id=trabajo_id,
        )
        log_evento(
            logger,
            "pasarela_seleccionada",
            patron="Adapter",
            adaptador=type(pasarela_impl).__name__,
            pasarela=pasarela,
            pago_id=str(pago.id),
            trabajo_id=trabajo_id,
        )

        # Se persiste PENDIENTE antes de la llamada externa — si el proceso
        # cae entre aquí y la respuesta de la pasarela, el registro de
        # intento de cobro ya quedó trazado (mismo principio que
        # Verificacion en Proveedores: persistir antes de la I/O externa).
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
            regla=type(regla).__name__,
            adaptador=type(pasarela_impl).__name__,
            region=registro.region.value,
            moneda=registro.moneda,
            monto=str(registro.monto),
            referencia_externa=resultado.referencia_externa,
            motivo_falla=resultado.motivo_falla,
            duracion_total_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )
        return pago.id

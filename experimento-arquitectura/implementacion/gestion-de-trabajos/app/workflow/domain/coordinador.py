import uuid
from typing import List

from app.workflow.domain.saga import SagaInstancia
from app.workflow.domain.value_objects import PasoSaga, EstadoSaga, SagaId
from app.ciclo_vida.domain.trabajo import Trabajo
from app.ciclo_vida.domain.value_objects import ProveedorId, TrabajoId
from app.workflow.domain.eventos import (
    ComandoSaga,
    PublicarElegibles,
    ReservarFranja,
    RetenerPago,
    LiberarPago,
    LiberarFranja,
)


class CoordinadorSaga:
    """Coordinador de Saga (Orquestador) para el Workflow del Trabajo"""

    @staticmethod
    def iniciar_saga(
        trabajo: Trabajo, origen: str, origen_id: str
    ) -> tuple[SagaInstancia, List[ComandoSaga]]:
        """Paso 1: local CrearTrabajo -> dispara PublicarElegibles.

        Tabla de estados (15-arquitectura-entrega-5.md §6): SOLICITADO
        --(TrabajoCreado publicado)--> ESPERANDO_ELEGIBLES. `trabajo` llega
        recién creado por `FabricaTrabajo` (SOLICITADO, sin proveedor); este
        método es quien dispara esa transición al armar el comando
        `PublicarElegibles` (el equivalente local a "publicar TrabajoCreado")."""
        trabajo.esperar_elegibles()
        saga_id = SagaId.nueva()
        saga = SagaInstancia(
            id=saga_id.valor,
            trabajo_id=TrabajoId(trabajo.id),
            origen=origen,
            estado=EstadoSaga.INICIADA,
            paso_actual=PasoSaga.PUBLICAR_ELEGIBLES,
        )

        comando = PublicarElegibles(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga_id),
            correlation_id=str(trabajo.id),
            origen=origen,
            origen_id=origen_id,
        )
        return saga, [comando]

    @staticmethod
    def on_proveedor_seleccionado(
        saga: SagaInstancia,
        proveedor_id: str,
        tecnico_id: str,
        fecha_franja: str,
        bloque: str,
    ) -> List[ComandoSaga]:
        """Paso 3: Proveedores ReservarFranja (tras recibir seleccion de canal)"""
        saga.avanzar_paso(PasoSaga.RESERVAR_FRANJA)
        comando = ReservarFranja(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            proveedor_id=proveedor_id,
            tecnico_id=tecnico_id,
            fecha_franja=fecha_franja,
            bloque=bloque,
        )
        return [comando]

    @staticmethod
    def on_franja_reservada(
        saga: SagaInstancia,
        trabajo: Trabajo,
        proveedor_id: str,
        reserva_id: str,
        monto: float,
        moneda: str,
    ) -> List[ComandoSaga]:
        """Paso 4: `AgendaConfirmada` -> GT·Ciclo de Vida AsignarProveedor
        (ASIGNADO) -> Pagos RetenerPago (15-arquitectura-entrega-5.md §5.1
        paso 4 y §7.1 paso 3-4). Antes de este fix, `asignar_proveedor()`
        nunca se llamaba en ningún lado del coordinador y el Trabajo se
        quedaba en SOLICITADO para siempre."""
        trabajo.asignar_proveedor(ProveedorId(proveedor_id))
        saga.avanzar_paso(PasoSaga.RETENER_PAGO)
        comando = RetenerPago(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            monto=monto,
            moneda=moneda,
        )
        return [comando]

    @staticmethod
    def on_franja_rechazada(
        saga: SagaInstancia, origen: str, origen_id: str
    ) -> List[ComandoSaga]:
        """Vuelve al paso 2"""
        saga.avanzar_paso(PasoSaga.PUBLICAR_ELEGIBLES)
        comando = PublicarElegibles(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            origen=origen,
            origen_id=origen_id,
        )
        return [comando]

    @staticmethod
    def on_pago_retenido(saga: SagaInstancia, trabajo: Trabajo) -> List[ComandoSaga]:
        """Paso 5: local IniciarWorkflow (ASIGNADO -> EN_CURSO). Antes de
        este fix llamaba `trabajo.iniciar_curso()`, método inexistente en
        `Trabajo` (el real es `iniciar_workflow()`) -- `AttributeError`
        garantizado en cuanto llegaba `PagoRetenido`."""
        saga.avanzar_paso(PasoSaga.INICIAR_WORKFLOW)
        trabajo.iniciar_workflow()
        return []

    @staticmethod
    def on_pago_retencion_fallida(
        saga: SagaInstancia, trabajo: Trabajo, reserva_id: str
    ) -> List[ComandoSaga]:
        """Falla -> LiberarFranja + Trabajo CANCELADO (caso compensación)"""
        saga.compensar()
        trabajo.cancelar()
        comando = LiberarFranja(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            reserva_id=reserva_id,
        )
        return [comando]

    @staticmethod
    def on_trabajo_completado_por_proveedor(
        saga: SagaInstancia, trabajo: Trabajo, pago_id: str
    ) -> List[ComandoSaga]:
        """Paso 6: Liberar pago"""
        saga.avanzar_paso(PasoSaga.LIBERAR_PAGO)
        trabajo.finalizar()
        comando = LiberarPago(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            pago_id=pago_id,
        )
        return [comando]

    @staticmethod
    def on_pago_liberado(saga: SagaInstancia, trabajo: Trabajo) -> None:
        saga.completar()
        trabajo.pagar()

    @staticmethod
    def on_novedad_disputa(
        saga: SagaInstancia, trabajo: Trabajo, pago_id: str
    ) -> List[ComandoSaga]:
        """Alt: Novedad disputa -> CompensarPago"""
        trabajo.disputar()
        from app.workflow.domain.eventos import CompensarPago

        comando = CompensarPago(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            pago_id=pago_id,
        )
        return [comando]

    @staticmethod
    def on_pago_compensado(saga: SagaInstancia, trabajo: Trabajo) -> None:
        """Alt: Pago compensado -> CANCELADO"""
        saga.compensar()
        trabajo.cancelar()

    @staticmethod
    def on_novedad_no_show(
        saga: SagaInstancia,
        trabajo: Trabajo,
        reserva_id: str,
        origen: str,
        origen_id: str,
    ) -> List[ComandoSaga]:
        """Alt: Novedad no-show -> LiberarFranja y pedir elegibles de nuevo"""
        trabajo.reasignar_proveedor()
        comando_liberar = LiberarFranja(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            reserva_id=reserva_id,
        )
        comando_elegibles = PublicarElegibles(
            comando_id=str(uuid.uuid4()),
            saga_id=str(saga.id),
            correlation_id=str(saga.trabajo_id),
            origen=origen,
            origen_id=origen_id,
        )
        return [comando_liberar, comando_elegibles]

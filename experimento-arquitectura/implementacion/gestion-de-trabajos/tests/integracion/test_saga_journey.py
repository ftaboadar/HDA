"""Prueba de integración de la Saga del Trabajo (A22, orquestada por
GT·Motor de Workflow) de punta a punta -- coordinador + handlers +
persistencia REAL (Postgres, Regla 5 criterio 3), con Pulsar reemplazado por
un doble en memoria del puerto `IPublicador` (mismo patrón que otros agentes
usaron hoy en Proveedores para no depender de un cluster de Pulsar real en
las pruebas de integración: el broker es infraestructura reemplazable, el
coordinador y la persistencia no).

Existía la máquina de estados (`ciclo_vida/domain/trabajo.py`) y el
coordinador (`workflow/domain/coordinador.py`), pero NINGÚN test ejercía la
saga de punta a punta -- por eso pasaron sin detectarse varios bugs que
garantizaban un `AttributeError`/estado incorrecto en producción (ver
`ESTADO-IMPLEMENTACION.md` y los docstrings de cada fix en `coordinador.py`
y `handlers_saga.py`). Esta prueba cubre exactamente ese hueco para JRN-01
(saga exitosa) y JRN-04 (saga con compensación).

Requiere Postgres real de este servicio arriba:

    docker compose up -d postgres   # expone localhost:5434

Si `DATABASE_URL` no está en el entorno, se usa por defecto la URL de ese
docker-compose (ver docker-compose.yml, servicio `postgres`)."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://hda:hda@localhost:5434/gestion_trabajos",
)

import pytest  # noqa: E402

from app.ciclo_vida.domain.fabrica import FabricaTrabajo  # noqa: E402
from app.ciclo_vida.domain.value_objects import (  # noqa: E402
    EstadoTrabajo,
    Region,
    TrabajoId,
)
from app.ciclo_vida.infrastructure.persistence.trabajo_repository_sqlalchemy import (  # noqa: E402
    TrabajoRepositorySQLAlchemy,
)
from app.common.db import Base, engine  # noqa: E402
from app.workflow.application.commands.completar_sub_trabajo import (  # noqa: E402
    CompletarSubTrabajo,
)
from app.workflow.application.handlers_saga import SagaHandlers  # noqa: E402
from app.workflow.domain.coordinador import CoordinadorSaga  # noqa: E402
from app.workflow.domain.value_objects import EstadoSaga, PasoSaga  # noqa: E402
from app.workflow.infrastructure.persistence.saga_repository_sqlalchemy import (  # noqa: E402
    SagaRepositorySQLAlchemy,
)


class _PublicadorFake:
    """Doble del puerto `IPublicador` (`application/ports/publicador.py`) --
    registra los comandos de la saga que se hubieran publicado en Pulsar sin
    necesitar un broker real arriba para esta prueba."""

    def __init__(self) -> None:
        self.comandos: list = []

    async def publicar_comando(self, comando) -> None:
        self.comandos.append(comando)

    async def publicar_trabajo_finalizado(self, evento) -> None:  # pragma: no cover
        pass

    def nombres_comandos(self) -> list[str]:
        return [type(c).__name__ for c in self.comandos]


@pytest.fixture(scope="module", autouse=True)
def _tablas():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def contexto():
    repo_trabajos = TrabajoRepositorySQLAlchemy()
    repo_saga = SagaRepositorySQLAlchemy()
    publicador = _PublicadorFake()
    handlers = SagaHandlers(repo_saga, repo_trabajos, publicador)
    coordinador = CoordinadorSaga()
    return repo_trabajos, repo_saga, publicador, handlers, coordinador


async def test_saga_camino_feliz_paso_1_a_6_jrn01(contexto):
    """JRN-01: SOLICITADO -> ESPERANDO_ELEGIBLES -> ASIGNADO -> EN_CURSO ->
    FINALIZADO -> PAGADO, con el Saga Log completo y ningún `AttributeError`
    (bug #1) ni transición inválida (bug #2) en el camino."""
    repo_trabajos, repo_saga, publicador, handlers, coordinador = contexto

    # Paso 1 (local): CrearTrabajo -> PublicarElegibles
    trabajo = FabricaTrabajo.crear(monto=Decimal("150000"), region=Region.COLOMBIA)
    saga, comandos_iniciales = coordinador.iniciar_saga(
        trabajo, origen="MARKETPLACE", origen_id="sol-jrn01"
    )
    repo_trabajos.guardar(trabajo)
    repo_saga.guardar(
        saga,
        tipo="COMANDO_ENVIADO",
        mensaje="PublicarElegibles",
        payload=comandos_iniciales[0].__dict__,
    )

    assert trabajo.estado == EstadoTrabajo.ESPERANDO_ELEGIBLES
    assert saga.paso_actual == PasoSaga.PUBLICAR_ELEGIBLES
    assert saga.trabajo_id.valor == trabajo.id  # bug de tipos (TrabajoId) corregido

    proveedor_id = str(uuid.uuid4())
    tecnico_id = str(uuid.uuid4())

    # Paso 3: el canal publica ProveedorSeleccionado -> GT pide ReservarFranja
    await handlers.handle_proveedor_seleccionado(
        {
            "trabajo_id": str(trabajo.id),
            "origen": "MARKETPLACE",
            "origen_id": "sol-jrn01",
            "proveedor_id": proveedor_id,
            "tecnico_id": tecnico_id,
            "franja": {"fecha": "2026-10-01", "bloque": "MANANA"},
        },
        id_mensaje=str(uuid.uuid4()),
    )
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert saga.paso_actual == PasoSaga.RESERVAR_FRANJA
    assert "ReservarFranja" in publicador.nombres_comandos()

    # Paso 4: Proveedores confirma la agenda -> GT asigna proveedor (bug #2)
    # y pide RetenerPago a Pagos
    await handlers.handle_franja_reservada(
        {
            "correlation_id": str(trabajo.id),
            "proveedor_id": proveedor_id,
            "reserva_id": str(uuid.uuid4()),
            "monto": 150000,
            "moneda": "COP",
        },
        id_mensaje=str(uuid.uuid4()),
    )
    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.ASIGNADO
    assert str(trabajo.proveedor_id) == proveedor_id
    assert saga.paso_actual == PasoSaga.RETENER_PAGO
    assert "RetenerPago" in publicador.nombres_comandos()

    # Paso 5: Pagos confirma la retención -> GT inicia el workflow (bug #1:
    # `iniciar_curso` -> `iniciar_workflow`)
    await handlers.handle_pago_retenido(
        {"correlation_id": str(trabajo.id), "pago_id": "pago-jrn01"},
        id_mensaje=str(uuid.uuid4()),
    )
    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.EN_CURSO
    assert saga.paso_actual == PasoSaga.INICIAR_WORKFLOW

    # Paso 5 (cierre): el proveedor completa vía API -> Motor cierra el
    # sub-trabajo -> CerrarTrabajo (FINALIZADO) + LiberarPago (bug/gap #4).
    # `pago_id` se recupera del Saga Log (`PagoRetenido`), no de un campo
    # nuevo -- ver docstring de `SagaRepositorySQLAlchemy.obtener_pago_id_retenido`.
    comando_completar = CompletarSubTrabajo(handlers)
    await comando_completar.ejecutar(trabajo.id)
    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.FINALIZADO
    assert saga.paso_actual == PasoSaga.LIBERAR_PAGO
    comandos_liberar_pago = [
        c for c in publicador.comandos if type(c).__name__ == "LiberarPago"
    ]
    assert len(comandos_liberar_pago) == 1
    assert comandos_liberar_pago[0].pago_id == "pago-jrn01"

    # Paso 6: Pagos libera el pago -> GT marca PAGADO
    await handlers.handle_pago_liberado(
        {"correlation_id": str(trabajo.id), "pago_id": "pago-jrn01"},
        id_mensaje=str(uuid.uuid4()),
    )
    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.PAGADO
    assert saga.estado == EstadoSaga.COMPLETADA


async def test_saga_con_compensacion_pago_retencion_fallida_jrn04(contexto):
    """JRN-04: la saga se ASIGNA (paso 4) pero Pagos rechaza la retención ->
    compensación (`LiberarFranja` + Trabajo CANCELADO + Saga COMPENSADA).
    Antes del fix del bug #2, `on_franja_reservada` nunca asignaba al
    proveedor, así que este camino tampoco podía completar la transición
    ASIGNADO -> CANCELADO (la invariante de `Trabajo.cancelar()` exige
    ASIGNADO o EN_DISPUTA)."""
    repo_trabajos, repo_saga, publicador, handlers, coordinador = contexto

    trabajo = FabricaTrabajo.crear(monto=Decimal("90000"), region=Region.COLOMBIA)
    saga, comandos_iniciales = coordinador.iniciar_saga(
        trabajo, origen="MARKETPLACE", origen_id="sol-jrn04"
    )
    repo_trabajos.guardar(trabajo)
    repo_saga.guardar(
        saga,
        tipo="COMANDO_ENVIADO",
        mensaje="PublicarElegibles",
        payload=comandos_iniciales[0].__dict__,
    )

    proveedor_id = str(uuid.uuid4())
    await handlers.handle_proveedor_seleccionado(
        {
            "trabajo_id": str(trabajo.id),
            "proveedor_id": proveedor_id,
            "tecnico_id": str(uuid.uuid4()),
            "franja": {"fecha": "2026-10-02", "bloque": "TARDE"},
        },
        id_mensaje=str(uuid.uuid4()),
    )

    reserva_id = str(uuid.uuid4())
    await handlers.handle_franja_reservada(
        {
            "correlation_id": str(trabajo.id),
            "proveedor_id": proveedor_id,
            "reserva_id": reserva_id,
            "monto": 90000,
            "moneda": "COP",
        },
        id_mensaje=str(uuid.uuid4()),
    )
    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    assert trabajo.estado == EstadoTrabajo.ASIGNADO

    # Pagos NO logra retener (fondos insuficientes / pasarela caída, etc.)
    await handlers.handle_pago_retencion_fallida(
        {"correlation_id": str(trabajo.id), "reserva_id": reserva_id},
        id_mensaje=str(uuid.uuid4()),
    )

    trabajo = repo_trabajos.obtener_por_id(TrabajoId(trabajo.id))
    saga = repo_saga.obtener_por_trabajo_id(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.CANCELADO
    assert saga.estado == EstadoSaga.COMPENSADA
    comandos_liberar_franja = [
        c for c in publicador.comandos if type(c).__name__ == "LiberarFranja"
    ]
    assert len(comandos_liberar_franja) == 1
    assert comandos_liberar_franja[0].reserva_id == reserva_id


async def test_handler_es_idempotente_por_id_mensaje(contexto):
    """Regla de mensajería (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §3): todo
    consumidor es idempotente por `id_evento`/`id_mensaje` -- reenviar el
    mismo `AgendaConfirmada` (at-least-once de Pulsar) no debe reasignar ni
    duplicar el comando `RetenerPago`."""
    repo_trabajos, repo_saga, publicador, handlers, coordinador = contexto

    trabajo = FabricaTrabajo.crear(monto=Decimal("50000"), region=Region.COLOMBIA)
    saga, comandos_iniciales = coordinador.iniciar_saga(
        trabajo, origen="MARKETPLACE", origen_id="sol-idem"
    )
    repo_trabajos.guardar(trabajo)
    repo_saga.guardar(
        saga,
        tipo="COMANDO_ENVIADO",
        mensaje="PublicarElegibles",
        payload=comandos_iniciales[0].__dict__,
    )

    proveedor_id = str(uuid.uuid4())
    id_mensaje_agenda = str(uuid.uuid4())
    payload_agenda = {
        "correlation_id": str(trabajo.id),
        "proveedor_id": proveedor_id,
        "reserva_id": str(uuid.uuid4()),
        "monto": 50000,
        "moneda": "COP",
    }

    await handlers.handle_franja_reservada(payload_agenda, id_mensaje=id_mensaje_agenda)
    await handlers.handle_franja_reservada(payload_agenda, id_mensaje=id_mensaje_agenda)

    retener_pago = [c for c in publicador.comandos if type(c).__name__ == "RetenerPago"]
    assert len(retener_pago) == 1

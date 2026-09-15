"""Comando `CrearTrabajo` — reemplaza el cuerpo de `POST /trabajos`; la ruta
HTTP nunca toca el ORM ni el agregado directo (ver app/api/main.py).

CQS: `ejecutar()` retorna solo el `id` del trabajo creado, nunca el
agregado completo ni su estado de negocio — una consulta posterior
(`ConsultarTrabajo`) es quien expone ese estado.

Dominio vs. integración (Regla 4, ver docstring de
`domain/trabajo/eventos.py`): el agregado `Trabajo.finalizar()` produce el
evento de DOMINIO `TrabajoFinalizado`, puramente interno. Este comando
guarda el agregado y le pasa sus eventos a
`application/dispatcher_eventos_dominio.py` — nunca publica ni notifica
directamente. El dispatcher es quien decide traducir ese evento de dominio
en un evento de INTEGRACIÓN hacia Pulsar Y en la reacción intra-servicio
del módulo Pagos (ver docstring del dispatcher).

CORRECCIÓN (encontrada corriendo k6 real contra GCP, no en tests): `_repo.guardar`
es una llamada SÍNCRONA de SQLAlchemy — invocarla directo dentro de un
`async def` bloquea el event loop entero de ese worker de Uvicorn durante
el round-trip a Cloud SQL. Bajo carga (ESC-01), esto serializa
efectivamente todas las requests de una instancia sin importar
`containerConcurrency`, causando colas de segundos y timeouts (p95 medido:
14.2s, 20% de requests fallidas). Se envuelve en `asyncio.to_thread`, mismo
patrón ya establecido y auditado en
`DISP-03/app/application/commands/registrar_intento.py`."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from app.application.dispatcher_eventos_dominio import despachar
from app.application.ports.publicador import IPublicador
from app.application.ports.registro_trabajos import IRegistroTrabajosRepository
from app.common.logging_utils import configurar_logging
from app.domain.trabajo.fabrica import FabricaTrabajo
from app.domain.trabajo.repository import ITrabajoRepository
from app.domain.trabajo.value_objects import ProveedorId, Region

logger = configurar_logging("application.commands.crear_trabajo")


class CrearTrabajo:
    def __init__(
        self,
        repo: ITrabajoRepository,
        publicador: IPublicador,
        registro_repo: IRegistroTrabajosRepository,
    ) -> None:
        self._repo = repo
        self._publicador = publicador
        self._registro_repo = registro_repo

    async def ejecutar(
        self, proveedor_id: str, monto: Decimal, region: str
    ) -> uuid.UUID:
        trabajo = FabricaTrabajo.crear(
            proveedor_id=ProveedorId(proveedor_id),
            monto=monto,
            region=Region(region),
        )

        # Skeleton simplificado (12-plan-entrega-4.md sección 3): sin
        # modelar el ciclo de vida intermedio de un Trabajo real (eso es
        # de la Saga, Entrega 5), este comando finaliza el trabajo de
        # inmediato para poder demostrar el evento `trabajos.finalizado`
        # de punta a punta.
        trabajo.finalizar()
        await asyncio.to_thread(self._repo.guardar, trabajo)

        await despachar(
            trabajo.recoger_eventos(),
            publicador=self._publicador,
            registro_repo=self._registro_repo,
        )

        return trabajo.id

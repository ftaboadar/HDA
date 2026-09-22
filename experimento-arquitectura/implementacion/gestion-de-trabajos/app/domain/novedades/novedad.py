"""Agregado raíz `Novedad` — representa un webhook (aviso de novedad sobre
un `Trabajo`) pendiente de entregar al CRM externo "Gestión de Agentes"
(DISP-02, ver `escenarios_calidad.md`). Solo referencia a `Trabajo` por id
(`TrabajoId`), nunca por composición — mismo principio de frontera de
agregado que `Trabajo.proveedor_id` respecto al agregado `Proveedor` de
otro Bounded Context (ver `07-vista-informacion.puml`, nota en
`domain/trabajo/value_objects.ProveedorId`).

INCONSISTENCIA EXPLÍCITA con el modelo de información, dejada a propósito
en vez de improvisarse en silencio (mismo criterio que la nota equivalente
en `domain/trabajo/trabajo.py`): `07-vista-informacion.puml` dibuja
`Novedad` como entidad HIJA del agregado `Trabajo` en el paquete "Gestión
de Trabajos", sin atributos ni ciclo de vida propio — coherente con que ese
diagrama no modela todavía el mecanismo de entrega hacia un CRM externo
(DISP-02 es un escenario de calidad, no un caso de uso de negocio que ya
estuviera en el modelo de información cuando se dibujó). Aquí se promueve
`Novedad` a agregado raíz PROPIO, con su propia identidad, tabla y
repositorio, porque su ciclo de vida de entrega (PENDIENTE → ENTREGADA /
AGOTADA, con reintentos acotados) necesita consistencia transaccional
independiente de `Trabajo`: cargar el agregado `Trabajo` completo solo para
registrar un intento de webhook sería una violación de límite de agregado
mucho peor que la promoción hecha aquí. Quien mantenga
`07-vista-informacion.puml` debería decidir si vale la pena reflejar este
cambio en el diagrama o dejarlo explícitamente fuera de alcance de esta
entrega (ver README.md, sección "Qué falta")."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.novedades.eventos import NovedadAgotada, NovedadEntregada
from app.domain.novedades.value_objects import EstadoNovedad, NovedadId
from app.seedwork.dominio.aggregate_root import AggregateRoot
from app.domain.ciclo_vida.value_objects import TrabajoId


class ErrorTransicionInvalida(Exception):
    """Se lanza cuando se intenta una transición de estado que viola un
    invariante del agregado — nunca un `assert` silencioso (mismo patrón
    que `Trabajo.ErrorTransicionInvalida`; cada agregado con su propia
    excepción, sin compartir código entre agregados)."""


class Novedad(AggregateRoot):
    def __init__(
        self,
        id: uuid.UUID,
        trabajo_id: TrabajoId,
        descripcion: str,
        estado: EstadoNovedad = EstadoNovedad.PENDIENTE,
        intentos: int = 0,
        creado_en: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.trabajo_id = trabajo_id
        self.descripcion = descripcion
        self.estado = estado
        self.intentos = intentos
        self.creado_en = creado_en or datetime.now(timezone.utc)

    def registrar_intento(self) -> None:
        """La invoca el Throttler (infrastructure/messaging/throttler.py)
        una vez por cada intento de envío al CRM, exitoso o no, ANTES de
        conocer el resultado — es lo que permite decidir después, comparando
        contra `settings.throttler_max_reintentos`, si toca reintentar o
        agotar. Invariante: no se puede seguir intentando una `Novedad` que
        ya salió de PENDIENTE (ya fue entregada o ya se agotó)."""
        if self.estado != EstadoNovedad.PENDIENTE:
            raise ErrorTransicionInvalida(
                f"La novedad {self.id} está {self.estado.value}, no se pueden "
                "registrar más intentos de envío"
            )
        self.intentos += 1

    def marcar_entregada(self) -> None:
        if self.estado == EstadoNovedad.ENTREGADA:
            raise ErrorTransicionInvalida(
                f"La novedad {self.id} ya está ENTREGADA, no puede marcarse "
                "entregada de nuevo"
            )
        if self.estado == EstadoNovedad.AGOTADA:
            raise ErrorTransicionInvalida(
                f"La novedad {self.id} ya está AGOTADA, no puede marcarse entregada"
            )
        self.estado = EstadoNovedad.ENTREGADA
        self.registrar_evento(
            NovedadEntregada(
                novedad_id=NovedadId(self.id),
                trabajo_id=self.trabajo_id,
                intentos=self.intentos,
            )
        )

    def marcar_agotada(self, motivo: str | None = None) -> None:
        if self.estado == EstadoNovedad.AGOTADA:
            raise ErrorTransicionInvalida(
                f"La novedad {self.id} ya está AGOTADA, no puede marcarse agotada "
                "de nuevo"
            )
        if self.estado == EstadoNovedad.ENTREGADA:
            raise ErrorTransicionInvalida(
                f"La novedad {self.id} ya está ENTREGADA, no puede marcarse agotada"
            )
        self.estado = EstadoNovedad.AGOTADA
        self.registrar_evento(
            NovedadAgotada(
                novedad_id=NovedadId(self.id),
                trabajo_id=self.trabajo_id,
                intentos=self.intentos,
                motivo=motivo,
            )
        )

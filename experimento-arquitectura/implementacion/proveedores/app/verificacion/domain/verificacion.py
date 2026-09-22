"""Agregado raíz `Verificacion` — un solo agregado para esta pieza (ver
11-implementacion-ddd-verificacion.md, sección 1). Las transiciones de
estado se validan DENTRO del agregado, nunca desde fuera — es la garantía
central de invariantes que un ORM anémico no puede dar."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.seedwork.aggregate_root import AggregateRoot
from app.domain.seedwork.entity import Entity
from app.domain.verificacion.eventos import (
    IntentoRegistrado,
    VerificacionAgotoReintentos,
    VerificacionCompletada,
)
from app.domain.verificacion.value_objects import (
    EstadoVerificacion,
    ProveedorId,
    ResultadoIntento,
    TipoVerificador,
    VerificacionId,
)

MAX_INTENTOS_POR_DEFECTO = 4


class IntentoVerificacion(Entity):
    """Entidad hija — reemplaza los campos planos `intentos: int` /
    `motivo_falla: str` del ORM anterior por una lista real de intentos:
    trazabilidad completa, que es justo lo que exige la medida de la
    respuesta de DISP-03 ("100% de verificaciones fallidas trazables")."""

    def __init__(
        self,
        id: uuid.UUID,
        numero: int,
        resultado: ResultadoIntento,
        duracion_ms: int,
        error: str | None = None,
        ocurrido_en: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.numero = numero
        self.resultado = resultado
        self.error = error
        self.duracion_ms = duracion_ms
        self.ocurrido_en = ocurrido_en or datetime.now(timezone.utc)


class ErrorTransicionInvalida(Exception):
    """Se lanza cuando se intenta una transición de estado que viola un
    invariante del agregado — nunca un `assert` silencioso."""


class Verificacion(AggregateRoot):
    def __init__(
        self,
        id: uuid.UUID,
        proveedor_id: ProveedorId,
        tipo_verificador: TipoVerificador,
        estado: EstadoVerificacion = EstadoVerificacion.PENDIENTE,
        intentos: list[IntentoVerificacion] | None = None,
        max_intentos: int = MAX_INTENTOS_POR_DEFECTO,
        reprocesos: int = 0,
        creado_en: datetime | None = None,
        actualizado_en: datetime | None = None,
        completado_en: datetime | None = None,
        en_dlq_desde: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.proveedor_id = proveedor_id
        self.tipo_verificador = tipo_verificador
        self.estado = estado
        self.intentos = intentos if intentos is not None else []
        self.max_intentos = max_intentos
        self.reprocesos = reprocesos
        # Metadata informativa para el contrato HTTP (VerificacionOut) — no
        # participa de ningún invariante; la fábrica la fija al crear, el
        # repositorio la fija al reconstruir desde persistencia.
        self.creado_en = creado_en or datetime.now(timezone.utc)
        self.actualizado_en = actualizado_en or self.creado_en
        self.completado_en = completado_en
        self.en_dlq_desde = en_dlq_desde

    @property
    def ultimo_intento(self) -> IntentoVerificacion | None:
        return self.intentos[-1] if self.intentos else None

    def registrar_intento(
        self, resultado: ResultadoIntento, duracion_ms: int, error: str | None = None
    ) -> None:
        if self.estado not in (EstadoVerificacion.PENDIENTE,):
            raise ErrorTransicionInvalida(
                f"No se puede registrar un intento sobre una verificación en estado {self.estado}"
            )

        intento = IntentoVerificacion(
            id=uuid.uuid4(),
            numero=len(self.intentos) + 1,
            resultado=resultado,
            duracion_ms=duracion_ms,
            error=error,
        )
        self.intentos.append(intento)
        self.registrar_evento(
            IntentoRegistrado(
                verificacion_id=VerificacionId(self.id),
                numero_intento=intento.numero,
                resultado=resultado,
            )
        )

        if resultado == ResultadoIntento.EXITOSO:
            self._completar()
        elif len(self.intentos) >= self.max_intentos:
            self._mover_a_dlq(error or "reintentos agotados")

    def _completar(self) -> None:
        """Invariante 1: una transición a COMPLETADA solo es válida si el
        último intento fue EXITOSO — se aplica arriba, antes de llamar
        aquí, así que este método asume la precondición ya verificada."""
        if self.ultimo_intento is None or self.ultimo_intento.resultado != ResultadoIntento.EXITOSO:
            raise ErrorTransicionInvalida(
                "Invariante violado: COMPLETADA requiere que el último intento sea EXITOSO"
            )
        self.estado = EstadoVerificacion.COMPLETADA
        self.registrar_evento(
            VerificacionCompletada(
                verificacion_id=VerificacionId(self.id), proveedor_id=self.proveedor_id
            )
        )

    def _mover_a_dlq(self, motivo_falla: str) -> None:
        """Invariante 2: solo válido si se agotaron los intentos y el
        último fue fallido — nunca se salta directo de PENDIENTE a
        FALLIDA_DLQ sin haber intentado."""
        if len(self.intentos) < self.max_intentos:
            raise ErrorTransicionInvalida(
                "Invariante violado: FALLIDA_DLQ requiere haber agotado max_intentos"
            )
        if self.ultimo_intento is None or self.ultimo_intento.resultado != ResultadoIntento.FALLIDO:
            raise ErrorTransicionInvalida(
                "Invariante violado: FALLIDA_DLQ requiere que el último intento haya sido FALLIDO"
            )
        self.estado = EstadoVerificacion.FALLIDA_DLQ
        self.registrar_evento(
            VerificacionAgotoReintentos(
                verificacion_id=VerificacionId(self.id),
                proveedor_id=self.proveedor_id,
                motivo_falla=motivo_falla,
            )
        )

    def reprocesar(self) -> None:
        if self.estado != EstadoVerificacion.FALLIDA_DLQ:
            raise ErrorTransicionInvalida(
                f"Solo se puede reprocesar desde FALLIDA_DLQ, estado actual: {self.estado}"
            )
        self.estado = EstadoVerificacion.PENDIENTE
        self.intentos = []
        self.reprocesos += 1

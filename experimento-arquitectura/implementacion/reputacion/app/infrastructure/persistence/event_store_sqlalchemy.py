"""Adaptador concreto de `IEventStore` sobre SQLAlchemy/Postgres -- tabla
`eventos_reputacion` (event_id, agregado_id, tipo_evento, payload_json,
version, timestamp). Es la ÚNICA pieza del sistema que serializa/deserializa
eventos de dominio a JSON: `domain/` y `application/` no conocen SQLAlchemy
ni el formato de `payload_json` (Regla 5, criterio 2 -- el dominio nunca
importa infraestructura).

Registro explícito de eventos soportados (`_EVENTOS`, `_serializar`,
`_deserializar`): si se agrega un evento de dominio nuevo a
`domain/reputacion/eventos.py`, hay que registrarlo también aquí. Es
deliberado -- se prefiere este mapeo explícito, fácil de auditar, en vez de
reflexión automática sobre nombres de módulos/campos, que sería más
"mágica" pero más difícil de razonar para un PoC pequeño con un solo tipo
de evento."""

import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.db import SessionLocal
from app.domain.reputacion.event_store import ConflictoDeConcurrencia, IEventStore
from app.domain.reputacion.eventos import ProveedorCalificado
from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId
from app.domain.seedwork.domain_event import DomainEvent
from app.infrastructure.persistence.models_db import EventoReputacionORM

_EVENTOS: dict[str, type[DomainEvent]] = {
    "ProveedorCalificado": ProveedorCalificado,
}


def _serializar(evento: DomainEvent) -> str:
    if isinstance(evento, ProveedorCalificado):
        payload = {
            "event_id": str(evento.event_id),
            "ocurrido_en": evento.ocurrido_en.isoformat(),
            "proveedor_id": str(evento.proveedor_id),
            "trabajo_id": str(evento.trabajo_id),
            "puntaje": evento.puntaje,
            "comentario": evento.comentario,
            "garantia_dias": evento.garantia.plazo_dias if evento.garantia else None,
        }
        return json.dumps(payload)
    raise NotImplementedError(
        f"No hay serializador registrado para {type(evento).__name__} -- agregarlo en _serializar()"
    )


def _deserializar(tipo_evento: str, payload_json: str) -> DomainEvent:
    clase = _EVENTOS.get(tipo_evento)
    if clase is None:
        raise NotImplementedError(
            f"No hay deserializador registrado para el tipo '{tipo_evento}'"
        )

    payload = json.loads(payload_json)

    if clase is ProveedorCalificado:
        return ProveedorCalificado(
            event_id=uuid.UUID(payload["event_id"]),
            ocurrido_en=datetime.fromisoformat(payload["ocurrido_en"]),
            proveedor_id=ProveedorId(payload["proveedor_id"]),
            trabajo_id=TrabajoId(payload["trabajo_id"]),
            puntaje=payload["puntaje"],
            comentario=payload.get("comentario"),
            garantia=(
                Garantia(payload["garantia_dias"])
                if payload.get("garantia_dias") is not None
                else None
            ),
        )
    raise NotImplementedError(
        f"No hay deserializador registrado para el tipo '{tipo_evento}'"
    )


class EventStoreSQLAlchemy(IEventStore):
    def guardar_eventos(
        self, agregado_id: str, eventos: list[DomainEvent], version_esperada: int
    ) -> None:
        if not eventos:
            return
        with SessionLocal() as sesion:
            version_actual = self._version_actual(sesion, agregado_id)
            if version_actual != version_esperada:
                raise ConflictoDeConcurrencia(
                    f"Version esperada {version_esperada}, version real persistida "
                    f"{version_actual} para agregado '{agregado_id}'"
                )
            for indice, evento in enumerate(eventos, start=1):
                sesion.add(
                    EventoReputacionORM(
                        event_id=evento.event_id,
                        agregado_id=agregado_id,
                        tipo_evento=type(evento).__name__,
                        payload_json=_serializar(evento),
                        version=version_actual + indice,
                        timestamp=evento.ocurrido_en,
                    )
                )
            sesion.commit()

    def cargar_eventos(self, agregado_id: str) -> list[DomainEvent]:
        with SessionLocal() as sesion:
            filas = sesion.scalars(
                select(EventoReputacionORM)
                .where(EventoReputacionORM.agregado_id == agregado_id)
                .order_by(EventoReputacionORM.version.asc())
            ).all()
            return [
                _deserializar(fila.tipo_evento, fila.payload_json) for fila in filas
            ]

    @staticmethod
    def _version_actual(sesion: Session, agregado_id: str) -> int:
        ultima = sesion.scalars(
            select(EventoReputacionORM.version)
            .where(EventoReputacionORM.agregado_id == agregado_id)
            .order_by(EventoReputacionORM.version.desc())
            .limit(1)
        ).first()
        return ultima or 0

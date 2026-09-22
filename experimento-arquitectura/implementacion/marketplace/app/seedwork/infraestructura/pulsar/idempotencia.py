"""Idempotencia del consumidor por `id_evento` (CONVENCIONES §3): tabla
`eventos_procesados(id_evento PK, tipo, recibido_en)` en la BD del consumidor.

`reservar` inserta primero y procesa después: la PK hace que dos instancias del
worker que reciben la misma reentrega a la vez no apliquen el efecto dos veces
(solo una logra el INSERT). Si el manejador falla, `liberar` borra la fila para
que la reentrega de Pulsar lo vuelva a intentar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.db import Base, SessionLocal


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class EventoProcesadoORM(Base):
    __tablename__ = "eventos_procesados"

    id_evento = Column(String, primary_key=True)
    tipo = Column(String, nullable=False)
    recibido_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)


class RegistroMensajesProcesadosSQLAlchemy:
    def __init__(self, fabrica_sesion: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_sesion = fabrica_sesion

    def reservar(self, id_evento: str, tipo_evento: str) -> bool:
        with self._fabrica_sesion() as sesion:
            sesion.add(EventoProcesadoORM(id_evento=id_evento, tipo=tipo_evento))
            try:
                sesion.commit()
            except IntegrityError:
                sesion.rollback()
                return False
            return True

    def liberar(self, id_evento: str) -> None:
        with self._fabrica_sesion() as sesion:
            sesion.query(EventoProcesadoORM).filter_by(id_evento=id_evento).delete()
            sesion.commit()


class RegistroMensajesProcesadosEnMemoria:
    """Para pruebas unitarias del consumidor, sin BD."""

    def __init__(self) -> None:
        self.procesados: dict[str, str] = {}

    def reservar(self, id_evento: str, tipo_evento: str) -> bool:
        if id_evento in self.procesados:
            return False
        self.procesados[id_evento] = tipo_evento
        return True

    def liberar(self, id_evento: str) -> None:
        self.procesados.pop(id_evento, None)

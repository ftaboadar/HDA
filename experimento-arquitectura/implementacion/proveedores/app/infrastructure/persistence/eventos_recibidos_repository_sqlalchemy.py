"""Adaptador concreto de `IEventosRecibidosRepository` — persistencia real
(tabla `eventos_recibidos`, ver `app/common/models_db.py`), no en memoria.
Deliberadamente el único adaptador de este puerto que hoy existe: no hay
motivo, dentro de este PoC, para simular otro transporte de persistencia
aquí (a diferencia de `VerificacionRepositorySQLAlchemy`, que sí necesita
convivir con el agregado y sus invariantes)."""

import json

from app.application.ports.eventos_recibidos import IEventosRecibidosRepository
from app.common.db import SessionLocal
from app.common.models_db import EventoRecibidoORM


class EventosRecibidosRepositorySQLAlchemy(IEventosRecibidosRepository):
    def registrar(self, tipo_evento: str, payload: dict) -> None:
        with SessionLocal() as sesion:
            fila = EventoRecibidoORM(tipo_evento=tipo_evento, payload=json.dumps(payload))
            sesion.add(fila)
            sesion.commit()

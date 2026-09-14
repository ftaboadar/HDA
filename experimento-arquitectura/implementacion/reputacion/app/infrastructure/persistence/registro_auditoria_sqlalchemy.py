"""Adaptador concreto de `IRegistroAuditoria` sobre SQLAlchemy/Postgres --
tabla `trabajos_vistos`. Usado exclusivamente por el consumidor de
`trabajos.finalizado` (ver infrastructure/messaging/consumidor_pulsar.py)
a través del comando `RegistrarEventoTrabajoFinalizado`."""

import json
import uuid
from datetime import datetime, timezone

from app.application.ports.registro_auditoria import IRegistroAuditoria
from app.common.db import SessionLocal
from app.infrastructure.persistence.models_db import TrabajoVistoORM


class RegistroAuditoriaSQLAlchemy(IRegistroAuditoria):
    def registrar_trabajo_finalizado(self, trabajo_id: str, proveedor_id: str, payload: dict) -> None:
        with SessionLocal() as sesion:
            sesion.add(
                TrabajoVistoORM(
                    id=uuid.uuid4(),
                    trabajo_id=trabajo_id,
                    proveedor_id=proveedor_id,
                    payload_json=json.dumps(payload),
                    recibido_en=datetime.now(timezone.utc),
                )
            )
            sesion.commit()

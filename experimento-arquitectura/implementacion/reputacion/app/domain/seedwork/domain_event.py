"""Evento de DOMINIO: en este microservicio los eventos de dominio cumplen
un rol distinto al de DISP-03 -- aquí SON la fuente de verdad del agregado
(Event Sourcing, ver perfil_reputacion.py), no un simple side-effect que se
despacha a otro módulo. Aun así, la distinción dominio/integración sigue
aplicando igual (Regla 4 de la rúbrica):

- `ProveedorCalificado` (domain/reputacion/eventos.py) es un evento de
  DOMINIO: nunca cruza a Pulsar, vive solo dentro de `eventos_reputacion`.
- `trabajos.finalizado` es un evento de INTEGRACIÓN que llega desde afuera
  (Gestión de Trabajos) vía Pulsar -- se recibe en
  infrastructure/messaging/consumidor_pulsar.py y JAMÁS se convierte en un
  DomainEvent de este módulo; solo dispara un comando de aplicación que
  registra el hecho en una tabla de auditoría aparte (ver
  application/commands/registrar_evento_trabajo_finalizado.py)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    # kw_only: así las subclases pueden agregar campos obligatorios sin
    # violar el orden de dataclasses (campos con default no pueden preceder
    # a campos sin default en la lista posicional).
    event_id: uuid.UUID = field(default_factory=uuid.uuid4, kw_only=True)
    ocurrido_en: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), kw_only=True
    )

    @property
    def tipo(self) -> str:
        return type(self).__name__

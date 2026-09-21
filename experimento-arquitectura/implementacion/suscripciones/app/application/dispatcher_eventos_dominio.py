from typing import List
from app.seedwork.domain_event import DomainEvent
from app.ciclo_suscripcion.domain.events import CicloSuscripcionGenerado
from app.ciclo_suscripcion.infrastructure.messaging.publicador import (
    publicar_ciclo_suscripcion,
)


def despachar_eventos(eventos: List[DomainEvent]):
    for ev in eventos:
        if isinstance(ev, CicloSuscripcionGenerado):
            publicar_ciclo_suscripcion(ev)

"""Puerto (interfaz) del Event Store -- el dominio y la aplicación dependen
de esta abstracción, nunca de SQLAlchemy directo. El adaptador concreto
vive en `app/infrastructure/persistence/event_store_sqlalchemy.py`
(Regla 5, criterio 2: el dominio nunca importa infraestructura)."""

import abc

from app.domain.seedwork.domain_event import DomainEvent


class ConflictoDeConcurrencia(Exception):
    """Se lanza cuando `version_esperada` no coincide con la versión real ya
    persistida para el agregado -- alguien más escribió eventos nuevos
    entre la lectura y la escritura de este comando (control de
    concurrencia optimista, estándar en Event Sourcing)."""


class IEventStore(abc.ABC):
    @abc.abstractmethod
    def guardar_eventos(
        self, agregado_id: str, eventos: list[DomainEvent], version_esperada: int
    ) -> None:
        """Persiste `eventos` (ya producidos por el agregado, en orden) como
        la continuación de su historial, empezando en `version_esperada + 1`.
        Debe lanzar `ConflictoDeConcurrencia` si la versión real persistida
        para `agregado_id` no coincide con `version_esperada`."""
        ...

    @abc.abstractmethod
    def cargar_eventos(self, agregado_id: str) -> list[DomainEvent]:
        """Devuelve el historial completo de eventos de `agregado_id`, en
        el orden en que ocurrieron. Lista vacía si el agregado no existe
        todavía (nunca se calificó a ese proveedor)."""
        ...

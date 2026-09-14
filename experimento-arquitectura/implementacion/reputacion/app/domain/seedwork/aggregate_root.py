"""Base de Aggregate Root para EVENT SOURCING -- distinta a propósito de la
base CRUD clásica usada en DISP-03
(`DISP-03/app/domain/seedwork/aggregate_root.py`), donde el agregado
acumula eventos solo como side-effect para publicarlos DESPUÉS de guardar
el estado directo en una tabla. Aquí no hay "estado directo": la única
fuente de verdad son los eventos persistidos en el Event Store (ver
domain/reputacion/event_store.py) -- el estado en memoria del agregado es
siempre una PROYECCIÓN reconstruida reproduciendo esa lista.

Patrón:
  - `desde_eventos(eventos)`: usado por la capa de aplicación al cargar el
    agregado desde el Event Store -- reproduce eventos YA persistidos, sin
    volver a marcarlos como pendientes.
  - `_aplicar_nuevo(evento)`: usado por los métodos de negocio del agregado
    (ej. `PerfilReputacion.calificar()`) -- muta el estado invocando el
    handler `_on_<TipoDeEvento>` correspondiente y deja el evento en la
    lista de "no confirmados", pendiente de que `application/` lo persista
    a través del puerto `IEventStore`.

No importa nada de infraestructura -- SQLAlchemy vive únicamente en
`infrastructure/persistence/event_store_sqlalchemy.py`."""

from __future__ import annotations

from app.domain.seedwork.domain_event import DomainEvent


class AggregateRootES:
    def __init__(self) -> None:
        # Número de eventos ya aplicados -- se usa como control de
        # concurrencia optimista al persistir (ver IEventStore.guardar_eventos,
        # parámetro `version_esperada`).
        self.version: int = 0
        self._eventos_no_confirmados: list[DomainEvent] = []

    @classmethod
    def desde_eventos(cls, eventos: list[DomainEvent]) -> "AggregateRootES":
        """Reconstruye el agregado reproduciendo, en orden, una lista de
        eventos ya persistidos. No agrega nada a la lista de "no
        confirmados" -- estos eventos ya existen en el Event Store."""
        if not eventos:
            raise ValueError("No se puede reconstruir un agregado a partir de una lista vacía de eventos")
        instancia = cls()
        for evento in eventos:
            instancia._aplicar(evento, es_nuevo=False)
        return instancia

    def _aplicar_nuevo(self, evento: DomainEvent) -> None:
        """Usado por los métodos de negocio del agregado para producir un
        hecho nuevo: muta el estado y dEja el evento pendiente de
        persistir."""
        self._aplicar(evento, es_nuevo=True)

    def _aplicar(self, evento: DomainEvent, *, es_nuevo: bool) -> None:
        nombre_handler = f"_on_{type(evento).__name__}"
        handler = getattr(self, nombre_handler, None)
        if handler is None:
            raise NotImplementedError(
                f"{type(self).__name__} no define {nombre_handler}() para aplicar "
                f"el evento {type(evento).__name__}"
            )
        handler(evento)
        self.version += 1
        if es_nuevo:
            self._eventos_no_confirmados.append(evento)

    def recoger_eventos_no_confirmados(self) -> list[DomainEvent]:
        """Devuelve los eventos producidos en esta sesión de uso del
        agregado y limpia el buffer -- se llama una sola vez, justo antes
        de persistirlos vía IEventStore.guardar_eventos()."""
        eventos, self._eventos_no_confirmados = self._eventos_no_confirmados, []
        return eventos

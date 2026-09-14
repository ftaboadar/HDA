"""Agregado raíz `PerfilReputacion` -- Event Sourcing (justificación en
README.md, sección "Por qué Event Sourcing", y en
`experimento-arquitectura/contexto/12-plan-entrega-4.md`, sección 6: "el
read model (Perfil de reputación) es una proyección acumulada de
calificaciones -- el caso más natural de los 3").

Consistente con `07-vista-informacion.puml` (paquete "Reputación y
Calidad"): `PerfilReputacion` es <<AggregateRoot>>, contiene 0..*
`Calificacion` <<Entity>>, y referencia a `Proveedor` (otro Bounded
Context) solo por id -- nunca por composición."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.domain.reputacion.eventos import ProveedorCalificado
from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId
from app.domain.seedwork.aggregate_root import AggregateRootES

PUNTAJE_MIN = 1
PUNTAJE_MAX = 5


class PuntajeFueraDeRango(Exception):
    """Invariante de dominio: toda calificación debe estar en [1, 5]. Se
    valida DENTRO del agregado (en `calificar()`), nunca desde afuera --
    misma filosofía que las invariantes de `Verificacion` en DISP-03
    (`ErrorTransicionInvalida`): un ORM anémico no puede dar esta garantía,
    solo el agregado."""


class Calificacion:
    """Entidad hija -- ver 07-vista-informacion.puml (`Calificacion
    <<Entity>>` dentro de `PerfilReputacion`). No tiene tabla propia ni
    identidad fuera del agregado: se reconstruye completa cada vez que se
    reproduce el evento `ProveedorCalificado` correspondiente (su `id` es,
    de hecho, el `event_id` de ese evento)."""

    def __init__(
        self,
        id: uuid.UUID,
        trabajo_id: TrabajoId,
        puntaje: int,
        comentario: str | None,
        garantia: Garantia | None,
        calificado_en: datetime,
    ) -> None:
        self.id = id
        self.trabajo_id = trabajo_id
        self.puntaje = puntaje
        self.comentario = comentario
        self.garantia = garantia
        self.calificado_en = calificado_en


class PerfilReputacion(AggregateRootES):
    def __init__(self) -> None:
        super().__init__()
        # `id`/`proveedor_id` quedan en None hasta que se aplica el primer
        # evento (vía `crear()` o vía `desde_eventos()` reproduciendo un
        # `ProveedorCalificado` ya persistido) -- un agregado de Event
        # Sourcing no tiene identidad real hasta que existe al menos un
        # hecho sobre él.
        self.id: str | None = None
        self.proveedor_id: ProveedorId | None = None
        self.calificaciones: list[Calificacion] = []
        self.promedio: float = 0.0

    @classmethod
    def crear(cls, proveedor_id: ProveedorId) -> "PerfilReputacion":
        """Fábrica: perfil nuevo, todavía sin calificaciones. No emite
        ningún evento por sí sola -- el primer hecho real de negocio lo
        produce `calificar()`. Útil para que `application/commands` tenga
        un punto de partida cuando el proveedor todavía no tiene ningún
        evento en el Event Store."""
        instancia = cls()
        instancia.id = proveedor_id.valor
        instancia.proveedor_id = proveedor_id
        return instancia

    def calificar(
        self,
        trabajo_id: TrabajoId,
        puntaje: int,
        comentario: str | None = None,
        garantia: Garantia | None = None,
    ) -> None:
        if not (PUNTAJE_MIN <= puntaje <= PUNTAJE_MAX):
            raise PuntajeFueraDeRango(
                f"El puntaje debe estar entre {PUNTAJE_MIN} y {PUNTAJE_MAX}, recibido: {puntaje}"
            )
        evento = ProveedorCalificado(
            proveedor_id=self.proveedor_id,
            trabajo_id=trabajo_id,
            puntaje=puntaje,
            comentario=comentario,
            garantia=garantia,
        )
        self._aplicar_nuevo(evento)

    # --- Handler de reconstrucción -- invocado tanto al aplicar un evento
    # nuevo (`calificar()`) como al reproducir el historial completo
    # (`desde_eventos()`). Es la ÚNICA función que muta el estado del
    # agregado; nunca se asignan campos directo desde fuera de esta clase. ---
    def _on_ProveedorCalificado(self, evento: ProveedorCalificado) -> None:
        self.proveedor_id = evento.proveedor_id
        self.id = evento.proveedor_id.valor
        self.calificaciones.append(
            Calificacion(
                id=evento.event_id,
                trabajo_id=evento.trabajo_id,
                puntaje=evento.puntaje,
                comentario=evento.comentario,
                garantia=evento.garantia,
                calificado_en=evento.ocurrido_en,
            )
        )
        total = sum(c.puntaje for c in self.calificaciones)
        self.promedio = round(total / len(self.calificaciones), 2)

"""Query -- solo LEE, no muta estado (CQS: ver
`application/commands/calificar_proveedor.py` para el lado de escritura).

Proyecta el estado "actual" de `PerfilReputacion` reproduciendo su event
stream completo cada vez que se consulta (proyección "on the fly", no
materializada). Decisión documentada en README.md, sección "Proyección
on-the-fly vs. materializada": a la escala de un perfil por proveedor en
este PoC, reproducir N eventos por consulta es O(n) y trivial; si el
volumen de calificaciones por proveedor creciera mucho, la alternativa
correcta sería una tabla `perfiles_reputacion` mantenida por un proyector
asíncrono -- explícitamente no se construye esa segunda tabla ahora para no
acumular features sin necesidad real (ver reglas de comportamiento de
`.claude/agents/implementador-ddd.md`)."""

from app.domain.reputacion.event_store import IEventStore
from app.domain.reputacion.perfil_reputacion import PerfilReputacion
from app.domain.reputacion.value_objects import ProveedorId


class ConsultarPerfilReputacion:
    def __init__(self, event_store: IEventStore) -> None:
        self._event_store = event_store

    def ejecutar(self, proveedor_id: str) -> PerfilReputacion | None:
        pid = ProveedorId(proveedor_id)
        eventos = self._event_store.cargar_eventos(pid.valor)
        if not eventos:
            return None
        return PerfilReputacion.desde_eventos(eventos)

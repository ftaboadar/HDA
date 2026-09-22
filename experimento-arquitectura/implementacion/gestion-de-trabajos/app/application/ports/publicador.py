"""Puerto de publicación de eventos de INTEGRACIÓN — el caso de uso
`CrearTrabajo` (application/commands/crear_trabajo.py) programa contra esta
interfaz, nunca contra `pulsar-client` directamente. El adaptador concreto
(`PublicadorPulsar`) vive en
`app/infrastructure/messaging/publicador_pulsar.py`.

Solo hay un método porque este servicio, en su alcance de skeleton, publica
un único tipo de evento de integración (`trabajos.finalizado` — ver
12-plan-entrega-4.md sección 3: "Pagos no tiene tópico propio", así que el
submódulo ACL de Pagos no necesita este puerto)."""

import abc

from app.ciclo_vida.domain.eventos import TrabajoFinalizado


class IPublicador(abc.ABC):
    @abc.abstractmethod
    async def publicar_trabajo_finalizado(self, evento: TrabajoFinalizado) -> None: ...

"""Puerto para el registro liviano de eventos de integración RECIBIDOS de
otros microservicios (ver `worker/consumidor_trabajos_finalizado.py` y
sección 1.1/2.1 del plan de Entrega 4). Deliberadamente separado de
`IVerificacionRepository`: este puerto nunca toca el agregado `Verificacion`
ni sus invariantes — solo deja constancia de que el evento llegó. Completar
la cadena de verificación automáticamente al recibir `trabajos.finalizado`
es Entrega 5 (Saga), fuera de alcance aquí."""

import abc


class IEventosRecibidosRepository(abc.ABC):
    @abc.abstractmethod
    def registrar(self, tipo_evento: str, payload: dict) -> None: ...

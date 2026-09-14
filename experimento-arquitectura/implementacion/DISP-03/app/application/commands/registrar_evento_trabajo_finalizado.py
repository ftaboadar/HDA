"""Comando — registra que Proveedores "oyó" `trabajos.finalizado` (Gestión
de Trabajos -> Proveedores/Reputación, sección 2 punto 2 y sección 1.1 del
plan de Entrega 4: *"basta con que el consumidor exista y pueda recibir y
registrar el evento (skeleton de 'oír'), sin necesitar completar la
cadena"*).

Deliberadamente NO completa ninguna verificación, NO toca el agregado
`Verificacion` y NO dispara ningún comando de dominio existente — es un
placeholder de comunicación entre servicios. La reacción real (ej. iniciar
una verificación automática al completarse un trabajo) es Entrega 5, cuando
exista el coordinador de Saga."""

from app.application.ports.eventos_recibidos import IEventosRecibidosRepository

TIPO_EVENTO_TRABAJOS_FINALIZADO = "trabajos.finalizado"


class RegistrarEventoTrabajoFinalizado:
    def __init__(self, repo: IEventosRecibidosRepository) -> None:
        self._repo = repo

    def ejecutar(self, payload: dict) -> None:
        self._repo.registrar(tipo_evento=TIPO_EVENTO_TRABAJOS_FINALIZADO, payload=payload)

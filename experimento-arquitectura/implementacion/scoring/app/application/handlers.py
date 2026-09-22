from app.domain.ports import ScoringRepository
from app.domain.models import FotografoScoring
from app.application.commands import ActualizarScoringCommand
from app.domain.events import EventDispatcher

class ActualizarScoringHandler:
    def __init__(self, repository: ScoringRepository, dispatcher: EventDispatcher):
        self.repository = repository
        self.dispatcher = dispatcher

    def handle(self, command: ActualizarScoringCommand):
        scoring = self.repository.get_by_fotografo_id(command.fotografo_id)
        if not scoring:
            scoring = FotografoScoring(fotografo_id=command.fotografo_id)
        
        scoring.registrar_trabajo_finalizado(command.calificacion)
        self.repository.save(scoring)
        
        for event in scoring._events:
            self.dispatcher.dispatch(event)
        scoring.clear_events()

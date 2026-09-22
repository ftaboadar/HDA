from typing import Optional
from uuid import UUID
from app.domain.ports import ScoringRepository
from app.domain.models import FotografoScoring
from app.infrastructure.database import SessionLocal, FotografoScoringModel

class SQLiteScoringRepository(ScoringRepository):
    def get_by_fotografo_id(self, fotografo_id: UUID) -> Optional[FotografoScoring]:
        with SessionLocal() as session:
            model = session.query(FotografoScoringModel).filter_by(fotografo_id=str(fotografo_id)).first()
            if model:
                return FotografoScoring(
                    id=UUID(model.id),
                    fotografo_id=UUID(model.fotografo_id),
                    puntuacion_actual=model.puntuacion_actual,
                    trabajos_completados=model.trabajos_completados,
                    fecha_ultima_actualizacion=model.fecha_ultima_actualizacion
                )
            return None

    def save(self, scoring: FotografoScoring) -> None:
        with SessionLocal() as session:
            model = session.query(FotografoScoringModel).filter_by(id=str(scoring.id)).first()
            if not model:
                model = FotografoScoringModel(
                    id=str(scoring.id),
                    fotografo_id=str(scoring.fotografo_id),
                    puntuacion_actual=scoring.puntuacion_actual,
                    trabajos_completados=scoring.trabajos_completados,
                    fecha_ultima_actualizacion=scoring.fecha_ultima_actualizacion
                )
                session.add(model)
            else:
                model.puntuacion_actual = scoring.puntuacion_actual
                model.trabajos_completados = scoring.trabajos_completados
                model.fecha_ultima_actualizacion = scoring.fecha_ultima_actualizacion
            session.commit()

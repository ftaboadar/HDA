from dataclasses import dataclass
from typing import Optional
from app.ciclo_suscripcion.domain.repositories import SuscripcionRepository
from app.ciclo_suscripcion.domain.entities import Suscripcion

@dataclass
class ConsultarSuscripcionQuery:
    id: str

def ejecutar_consultar_suscripcion(query: ConsultarSuscripcionQuery, repositorio: SuscripcionRepository) -> Optional[Suscripcion]:
    return repositorio.get(query.id)

from dataclasses import dataclass
from typing import Optional
from app.ciclo_suscripcion.domain.entities import Suscripcion
from app.ciclo_suscripcion.domain.value_objects import TipoBloqueFranja
from app.ciclo_suscripcion.domain.repositories import SuscripcionRepository
from app.application.dispatcher_eventos_dominio import despachar_eventos

@dataclass
class IniciarSuscripcionCommand:
    cliente_id: str
    dia_semana: int
    bloque: str

def ejecutar_iniciar_suscripcion(comando: IniciarSuscripcionCommand, repositorio: SuscripcionRepository) -> str:
    suscripcion = Suscripcion()
    suscripcion.iniciar_suscripcion(
        cliente_id=comando.cliente_id,
        dia_semana=comando.dia_semana,
        bloque=TipoBloqueFranja(comando.bloque)
    )
    suscripcion.generar_siguiente_ciclo()
    
    repositorio.save(suscripcion)
    despachar_eventos(suscripcion.eventos)
    suscripcion.clear_events()
    
    return suscripcion.id

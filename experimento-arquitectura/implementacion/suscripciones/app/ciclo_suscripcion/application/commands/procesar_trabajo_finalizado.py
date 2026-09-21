from dataclasses import dataclass
from app.ciclo_suscripcion.domain.repositories import SuscripcionRepository
from app.application.dispatcher_eventos_dominio import despachar_eventos


@dataclass
class ProcesarTrabajoFinalizadoCommand:
    suscripcion_id: str
    ciclo_id: str
    proveedor_id: str


def ejecutar_procesar_trabajo_finalizado(
    comando: ProcesarTrabajoFinalizadoCommand, repositorio: SuscripcionRepository
):
    suscripcion = repositorio.get(comando.suscripcion_id)
    if not suscripcion:
        return  # Si el trabajo no era de una suscripción, lo ignoramos

    # Regla A13: Continuidad del proveedor en Suscripciones
    suscripcion.actualizar_proveedor_continuo(comando.proveedor_id)

    # Marcar el ciclo actual como completado
    for ciclo in suscripcion.ciclos:
        if ciclo.id == comando.ciclo_id:
            ciclo.completado = True

    # Generar el próximo ciclo (A13: el próximo ciclo ya tendrá el proveedor asignado)
    suscripcion.generar_siguiente_ciclo()

    repositorio.save(suscripcion)
    despachar_eventos(suscripcion.eventos)
    suscripcion.clear_events()

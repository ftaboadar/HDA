from app.ciclo_suscripcion.domain.entities import Suscripcion
from app.ciclo_suscripcion.domain.value_objects import TipoBloqueFranja


def test_a13_a14_iniciar_suscripcion_y_ciclos():
    suscripcion = Suscripcion()

    # A14: Reserva recurrente. Se define franja (dia, bloque) para toda la suscripcion.
    suscripcion.iniciar_suscripcion(
        cliente_id="C1", dia_semana=0, bloque=TipoBloqueFranja.MANANA
    )

    assert suscripcion.cliente_id == "C1"
    assert suscripcion.franja.dia_semana == 0
    assert suscripcion.franja.bloque == TipoBloqueFranja.MANANA
    assert len(suscripcion.eventos) == 1

    # Inicia el primer ciclo
    suscripcion.generar_siguiente_ciclo()
    assert len(suscripcion.ciclos) == 1
    primer_ciclo = suscripcion.ciclos[0]
    assert primer_ciclo.numero_ciclo == 1
    assert primer_ciclo.proveedor_id is None  # El cliente elige (o GT asigna elegibles)

    # Cuando el trabajo finaliza, GT manda el evento y nosotros actualizamos el proveedor continuo
    # Regla A13: Continuidad. Ese mismo atiende todos los ciclos del periodo
    suscripcion.actualizar_proveedor_continuo("P_123")
    assert suscripcion.proveedor_continuo_id == "P_123"

    # Generar siguiente ciclo
    suscripcion.generar_siguiente_ciclo()
    assert len(suscripcion.ciclos) == 2
    segundo_ciclo = suscripcion.ciclos[1]
    assert segundo_ciclo.numero_ciclo == 2
    # A13: El segundo ciclo ya trae el proveedor asignado
    assert segundo_ciclo.proveedor_id == "P_123"

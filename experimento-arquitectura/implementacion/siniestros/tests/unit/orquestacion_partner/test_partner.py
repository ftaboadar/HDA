from app.orquestacion_partner.domain.entidades.partner import Partner
from app.orquestacion_partner.domain.entidades.value_objects import (
    ReglaDeAprobacion,
    RedPermitida,
    MontoMaximo,
)


def test_registrar_siniestro():
    partner = Partner(
        id="p1",
        nombre="Aseguradora Alfa",
        regla=ReglaDeAprobacion(True, 100.0),
        red=RedPermitida(["a"]),
        monto=MontoMaximo(1000.0, "COP"),
    )
    partner.registrar_siniestro("s1", "plomeria", True, "calle 1", "reg1")

    assert len(partner.domain_events) == 1
    event = partner.domain_events[0]
    assert event.__class__.__name__ == "SiniestroAprobado"
    assert event.siniestro_id == "s1"
    assert event.monto_maximo == 1000.0


def test_evaluar_novedad_automatica():
    partner = Partner(
        id="p1",
        nombre="Alfa",
        regla=ReglaDeAprobacion(True, 100.0),
        red=RedPermitida(["a"]),
        monto=MontoMaximo(1000.0, "COP"),
    )
    decision = partner.evaluar_novedad("t1", "n1", 50.0)
    assert decision == "APROBADA"

    assert len(partner.domain_events) == 1
    event = partner.domain_events[0]
    assert event.decision == "APROBADA"
    assert event.automatica is True


def test_evaluar_novedad_manual():
    partner = Partner(
        id="p1",
        nombre="Alfa",
        regla=ReglaDeAprobacion(True, 100.0),
        red=RedPermitida(["a"]),
        monto=MontoMaximo(1000.0, "COP"),
    )
    decision = partner.evaluar_novedad("t1", "n1", 150.0)
    assert decision == "PENDIENTE"
    assert len(partner.domain_events) == 0


def test_aprobar_novedad_manual():
    partner = Partner(
        id="p1",
        nombre="Alfa",
        regla=ReglaDeAprobacion(True, 100.0),
        red=RedPermitida(["a"]),
        monto=MontoMaximo(1000.0, "COP"),
    )
    partner.aprobar_novedad("t1", "n1", "RECHAZADA")
    assert len(partner.domain_events) == 1
    event = partner.domain_events[0]
    assert event.decision == "RECHAZADA"
    assert event.automatica is False

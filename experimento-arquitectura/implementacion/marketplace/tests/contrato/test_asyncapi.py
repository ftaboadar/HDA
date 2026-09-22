"""El AsyncAPI es utilizable como contrato ejecutable: cada canal Pulsar sigue
las convenciones de nombres (CONVENCIONES §3) y cada mensaje tiene un esquema
con campos obligatorios contra el que se puede validar. También ata la
plantilla de mensajería al contrato: las propiedades que pone el publicador
validan contra `PropiedadesPulsar`."""

import uuid

import pytest
from jsonschema import ValidationError

from app.seedwork.infraestructura.pulsar.mensajeria import construir_propiedades
from tests.contrato.asyncapi import (
    canales_pulsar,
    esquema_cuerpo,
    mensajes_del_canal,
    topico_de,
    validar_cuerpo,
    validar_propiedades,
)

SERVICIOS = {
    "gestion-de-trabajos": "gestion-trabajos",
    "proveedores": "proveedores",
    "pagos": "pagos",
    "reputacion": "reputacion",
    "marketplace": "marketplace",
    "siniestros": "siniestros",
    "suscripciones": "suscripciones",
    "scoring": "scoring",
}
TIPOS = {"comando", "integracion_carga_estado", "integracion_delgado"}
CANALES = sorted(canales_pulsar())


@pytest.mark.parametrize("topico", CANALES)
def test_canal_sigue_la_convencion_de_nombres(topico):
    canal = canales_pulsar()[topico]
    productor = canal["x-productor"]
    assert productor in SERVICIOS
    assert canal["x-tipo"] in TIPOS
    if canal["x-tipo"] == "comando":
        # §7.1: persistent://hda/<servicio-destino>/comandos, un solo receptor.
        (destino,) = canal["x-consumidores"]
        assert topico == f"persistent://hda/{SERVICIOS[destino['servicio']]}/comandos"
    else:
        # §7: persistent://hda/<servicio-productor>/<evento>.
        assert topico.startswith(f"persistent://hda/{SERVICIOS[productor]}/")
    evento = topico.rsplit("/", 1)[-1]
    for consumidor in canal["x-consumidores"]:
        assert consumidor["servicio"] in SERVICIOS
        assert (
            consumidor["suscripcion"] == f"{SERVICIOS[consumidor['servicio']]}-{evento}"
        )


@pytest.mark.parametrize("topico", CANALES)
def test_mensajes_del_canal_tienen_campos_obligatorios(topico):
    for nombre in mensajes_del_canal(canales_pulsar()[topico]):
        esquema = esquema_cuerpo(nombre)
        obligatorios = esquema.get("required") or [
            campo
            for parte in esquema.get("allOf", [])
            for campo in parte.get("required", [])
        ]
        assert obligatorios, f"{nombre} no declara campos obligatorios"


def test_comandos_viajan_por_el_topico_comandos_del_destino():
    assert topico_de("ReservarFranja") == "persistent://hda/proveedores/comandos"
    assert topico_de("RetenerPago") == "persistent://hda/pagos/comandos"
    assert topico_de("FacturarAPartner") == "persistent://hda/siniestros/comandos"


def test_respuesta_a_reservar_franja_es_agenda_confirmada():
    assert (
        topico_de("AgendaConfirmada")
        == "persistent://hda/proveedores/agenda.confirmada"
    )
    assert (
        topico_de("AgendaRechazada") == "persistent://hda/proveedores/agenda.rechazada"
    )


def test_propiedades_del_publicador_cumplen_el_contrato():
    validar_propiedades(
        construir_propiedades(
            tipo_evento="ReservarFranja",
            productor="gestion-de-trabajos",
            correlation_id=str(uuid.uuid4()),
            causation_id=str(uuid.uuid4()),
        )
    )


def _reservar_franja() -> dict:
    trabajo_id = str(uuid.uuid4())
    return {
        "id_comando": str(uuid.uuid4()),
        "saga_id": str(uuid.uuid4()),
        "correlation_id": trabajo_id,
        "trabajo_id": trabajo_id,
        "origen": "MARKETPLACE",
        "origen_id": str(uuid.uuid4()),
        "proveedor_id": "prov-1",
        "tecnico_id": "tec-1",
        "franja": {"fecha": "2026-10-05", "bloque": "MANANA"},
        "monto": "150000.00",
        "moneda": "COP",
    }


def test_comando_valido_pasa():
    validar_cuerpo("ReservarFranja", _reservar_franja())


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ({"id_comando": None}, "falta un campo común de §7.1"),
        ({"monto": 150000.0}, "monto como float, no string decimal"),
        ({"franja": {"fecha": "2026-10-05", "bloque": "NOCHE"}}, "bloque fuera de A14"),
        ({"moneda": "USD"}, "moneda fuera del catálogo"),
    ],
)
def test_comando_invalido_falla(cambio, motivo):
    cuerpo = {**_reservar_franja(), **cambio}
    cuerpo = {k: v for k, v in cuerpo.items() if v is not None}
    with pytest.raises(ValidationError):
        validar_cuerpo("ReservarFranja", cuerpo)

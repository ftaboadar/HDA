"""Plantilla de mensajería (seedwork/infraestructura/pulsar): propiedades de
CONVENCIONES §3, idempotencia por id_evento, nack ante error y cuerpo sin nulos.
Sin broker: `ConsumidorPulsar.procesar` recibe un mensaje falso."""

import json
import uuid

import pytest
from pulsar.schema import Array, Record, String

from app.seedwork.infraestructura.pulsar.idempotencia import (
    RegistroMensajesProcesadosEnMemoria,
)
from app.seedwork.infraestructura.pulsar.mensajeria import (
    ConsumidorPulsar,
    construir_propiedades,
    record_a_dict,
    sin_nulos,
)


class _MensajeFalso:
    def __init__(self, cuerpo: dict, propiedades: dict, reentregas: int = 0) -> None:
        self._cuerpo = json.dumps(cuerpo).encode()
        self._propiedades = propiedades
        self._reentregas = reentregas
        self._id = f"(1,{uuid.uuid4().int % 1000},-1,-1)"

    def data(self) -> bytes:
        return self._cuerpo

    def properties(self) -> dict:
        return self._propiedades

    def message_id(self) -> str:
        return self._id

    def redelivery_count(self) -> int:
        return self._reentregas


def _consumidor(manejadores, registro=None) -> ConsumidorPulsar:
    return ConsumidorPulsar(
        service_url="pulsar://no-se-usa:6650",
        topico="persistent://hda/proveedores/comandos",
        suscripcion="proveedores-comandos",
        manejadores=manejadores,
        registro=registro or RegistroMensajesProcesadosEnMemoria(),
        tipo_comunicacion="entre_servicios_comando",
    )


def _propiedades(tipo="ReservarFranja", id_evento=None) -> dict:
    return construir_propiedades(
        tipo_evento=tipo,
        productor="gestion-de-trabajos",
        correlation_id="trabajo-1",
        causation_id="evento-previo",
        id_evento=id_evento,
    )


def test_propiedades_llevan_los_siete_campos_de_convenciones():
    props = _propiedades()
    assert set(props) == {
        "tipo_evento",
        "version_esquema",
        "content_type",
        "productor",
        "id_evento",
        "correlation_id",
        "causation_id",
    }
    assert props["content_type"] == "application/json"
    uuid.UUID(props["id_evento"])


def test_cada_publicacion_tiene_id_evento_nuevo():
    assert _propiedades()["id_evento"] != _propiedades()["id_evento"]


def test_sin_causation_id_no_se_envia_la_propiedad():
    props = construir_propiedades(tipo_evento="X", productor="p", correlation_id="c")
    assert "causation_id" not in props


def test_mensaje_se_entrega_al_manejador_de_su_tipo():
    recibidos = []
    consumidor = _consumidor({"ReservarFranja": recibidos.append})
    ok = consumidor.procesar(
        _MensajeFalso({"trabajo_id": "t1", "saga_id": "s1"}, _propiedades())
    )
    assert ok is True
    assert recibidos[0].cuerpo == {"trabajo_id": "t1", "saga_id": "s1"}
    assert recibidos[0].correlation_id == "trabajo-1"
    assert recibidos[0].causation_id == "evento-previo"


def test_manejador_async_se_ejecuta():
    recibidos = []

    async def manejar(msg):
        recibidos.append(msg.tipo_evento)

    consumidor = _consumidor({"ReservarFranja": manejar})
    assert consumidor.procesar(_MensajeFalso({}, _propiedades())) is True
    assert recibidos == ["ReservarFranja"]


def test_mismo_id_evento_dos_veces_no_duplica_el_efecto():
    recibidos = []
    consumidor = _consumidor({"ReservarFranja": recibidos.append})
    props = _propiedades(id_evento=str(uuid.uuid4()))
    assert consumidor.procesar(_MensajeFalso({"n": 1}, props)) is True
    assert consumidor.procesar(_MensajeFalso({"n": 1}, props, reentregas=1)) is True
    assert len(recibidos) == 1


def test_error_del_manejador_hace_nack_y_libera_la_reserva():
    intentos = []

    def falla_una_vez(msg):
        intentos.append(msg.id_evento)
        if len(intentos) == 1:
            raise RuntimeError("BD caída")

    registro = RegistroMensajesProcesadosEnMemoria()
    consumidor = _consumidor({"ReservarFranja": falla_una_vez}, registro)
    props = _propiedades()
    assert consumidor.procesar(_MensajeFalso({}, props)) is False
    assert props["id_evento"] not in registro.procesados
    # La reentrega de Pulsar vuelve a intentarlo y esta vez sí se procesa.
    assert consumidor.procesar(_MensajeFalso({}, props, reentregas=1)) is True
    assert len(intentos) == 2
    assert props["id_evento"] in registro.procesados


def test_tipo_sin_manejador_se_reconoce_sin_procesar():
    registro = RegistroMensajesProcesadosEnMemoria()
    consumidor = _consumidor({"ReservarFranja": lambda m: None}, registro)
    assert (
        consumidor.procesar(_MensajeFalso({}, _propiedades(tipo="ComandoNuevo")))
        is True
    )
    assert registro.procesados == {}


def test_mensaje_viejo_sin_id_evento_usa_el_message_id():
    recibidos = []
    consumidor = _consumidor({"TrabajoFinalizado": recibidos.append})
    msg = _MensajeFalso({"trabajo_id": "t9"}, {"tipo_evento": "TrabajoFinalizado"})
    assert consumidor.procesar(msg) is True
    assert recibidos[0].id_evento == msg.message_id()
    assert recibidos[0].correlation_id == "t9"


def test_dlq_sigue_la_convencion_topico_suscripcion():
    assert _consumidor({}).topico_dlq == (
        "persistent://hda/proveedores/comandos-proveedores-comandos-DLQ"
    )


class _Franja(Record):
    fecha = String(required=True)
    bloque = String(required=True)


class _Comando(Record):
    id_comando = String(required=True)
    franja = _Franja(required=False, default=None)
    excluidos = Array(String())
    reserva_id = String()


def test_cuerpo_omite_opcionales_vacios_y_records_anidados_sin_valor():
    assert record_a_dict(_Comando(id_comando="c1")) == {"id_comando": "c1"}


def test_cuerpo_conserva_los_valores_presentes():
    cuerpo = record_a_dict(
        _Comando(
            id_comando="c1",
            franja=_Franja(fecha="2026-10-05", bloque="MANANA"),
            excluidos=["p1"],
        )
    )
    assert cuerpo == {
        "id_comando": "c1",
        "franja": {"fecha": "2026-10-05", "bloque": "MANANA"},
        "excluidos": ["p1"],
    }


@pytest.mark.parametrize(
    ("entrada", "salida"),
    [
        ({"a": None, "b": 1}, {"b": 1}),
        ({"a": {"x": None}}, {}),
        ({"l": [{"x": None, "y": 2}]}, {"l": [{"y": 2}]}),
        ({"falso": False, "cero": 0}, {"falso": False, "cero": 0}),
    ],
)
def test_sin_nulos(entrada, salida):
    assert sin_nulos(entrada) == salida

import uuid
from pulsar.schema import Record, String, Float


class PagoMensajeBase(Record):
    pago_id = String()
    trabajo_id = String()


class PagoRetenidoMensaje(PagoMensajeBase):
    monto = Float()
    moneda = String()
    pasarela = String()
    regla_regional = String()


class PagoRetencionFallidaMensaje(PagoMensajeBase):
    motivo = String()


class PagoLiberadoMensaje(PagoMensajeBase):
    monto = Float()
    moneda = String()


class PagoFallidoMensaje(PagoMensajeBase):
    motivo = String()


class PagoCompensadoMensaje(PagoMensajeBase):
    pass


def publicar_mensaje_generico(
    productor,
    mensaje,
    tipo_evento: str,
    productor_nombre: str,
    correlation_id: str,
    causation_id: str = None,
    version_esquema: str = "1",
) -> str:
    propiedades = {
        "tipo_evento": tipo_evento,
        "version_esquema": version_esquema,
        "content_type": "application/json",
        "productor": productor_nombre,
        "id_evento": str(uuid.uuid4()),
        "correlation_id": str(correlation_id),
    }
    if causation_id:
        propiedades["causation_id"] = str(causation_id)

    return productor.send(mensaje, properties=propiedades)

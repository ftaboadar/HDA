import pulsar
from pulsar.schema import JsonSchema, Record, String, Boolean, Float
from app.common.config import settings
from app.common.logging_utils import log_evento


class SiniestroAprobadoRecord(Record):
    tipo_evento = String(default="SiniestroAprobado")
    siniestro_id = String()
    partner_id = String()
    categoria = String()
    urgencia = Boolean()
    ubicacion = String()
    region = String()
    monto_maximo = Float()
    moneda = String()


class DecisionPartnerRecord(Record):
    tipo_evento = String(default="DecisionPartner")
    trabajo_id = String()
    novedad_id = String()
    partner_id = String()
    decision = String()
    regla_aplicada = String()
    automatica = Boolean()


def publicar_siniestro_aprobado(evento):
    client = pulsar.Client(settings.pulsar_service_url)
    producer = client.create_producer(
        settings.pulsar_topic_siniestro_aprobado,
        schema=JsonSchema(SiniestroAprobadoRecord),
    )
    msg = SiniestroAprobadoRecord(
        siniestro_id=evento.siniestro_id,
        partner_id=evento.partner_id,
        categoria=evento.categoria,
        urgencia=evento.urgencia,
        ubicacion=evento.ubicacion,
        region=evento.region,
        monto_maximo=evento.monto_maximo,
        moneda=evento.moneda,
    )
    # Json format required by conventions
    import uuid

    id_evento = str(uuid.uuid4())
    properties = {
        "tipo_evento": "SiniestroAprobado",
        "version_esquema": "1",
        "content_type": "application/json",
        "productor": "siniestros",
        "id_evento": id_evento,
        "correlation_id": evento.siniestro_id,
    }

    producer.send(msg, properties=properties)
    log_evento(
        "mensaje_publicado",
        evento.siniestro_id,
        "INFRA",
        {"topico": settings.pulsar_topic_siniestro_aprobado},
    )
    client.close()


def publicar_decision_partner(evento):
    client = pulsar.Client(settings.pulsar_service_url)
    producer = client.create_producer(
        settings.pulsar_topic_decision_partner, schema=JsonSchema(DecisionPartnerRecord)
    )
    msg = DecisionPartnerRecord(
        trabajo_id=evento.trabajo_id,
        novedad_id=evento.novedad_id,
        partner_id=evento.partner_id,
        decision=evento.decision,
        regla_aplicada=evento.regla_aplicada,
        automatica=evento.automatica,
    )
    import uuid

    id_evento = str(uuid.uuid4())
    properties = {
        "tipo_evento": "DecisionPartner",
        "version_esquema": "1",
        "content_type": "application/json",
        "productor": "siniestros",
        "id_evento": id_evento,
        "correlation_id": evento.trabajo_id,
    }

    producer.send(msg, properties=properties)
    log_evento(
        "mensaje_publicado",
        evento.trabajo_id,
        "INFRA",
        {"topico": settings.pulsar_topic_decision_partner},
    )
    client.close()

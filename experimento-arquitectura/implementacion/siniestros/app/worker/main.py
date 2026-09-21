import asyncio
from fastapi import FastAPI
import uvicorn
import pulsar
from pulsar.schema import JsonSchema, Record, String, Float
from app.common.config import settings
from app.common.logging_utils import log_evento
from app.orquestacion_partner.domain.entidades.partner import Partner
from app.orquestacion_partner.domain.entidades.value_objects import (
    ReglaDeAprobacion,
    RedPermitida,
    MontoMaximo,
)
from app.orquestacion_partner.infrastructure.messaging.publisher import (
    publicar_decision_partner,
)


class ComandoSolicitarAprobacionRecord(Record):
    tipo_comando = String(default="SolicitarAprobacionNovedad")
    trabajo_id = String()
    novedad_id = String()
    partner_id = String()
    impacto_monto = Float(default=0.0)


app = FastAPI(title="Worker de Siniestros")


@app.get("/salud")
def salud():
    return {"status": "ok", "worker": "active"}


def consumir_comandos():
    client = pulsar.Client(settings.pulsar_service_url)
    consumer = client.subscribe(
        settings.pulsar_topic_solicitar_aprobacion_novedad,
        subscription_name="siniestros-comandos",
        consumer_type=pulsar.ConsumerType.Shared,
        schema=JsonSchema(ComandoSolicitarAprobacionRecord),
    )

    while True:
        try:
            msg = consumer.receive()
            data = msg.value()
            props = msg.properties()
            log_evento(
                "mensaje_recibido",
                props.get("correlation_id", "N/A"),
                "WORKER",
                {"id_evento": props.get("id_evento")},
            )

            if data.tipo_comando == "SolicitarAprobacionNovedad":
                partner = Partner(
                    id=data.partner_id,
                    nombre="Aseguradora Alfa",
                    regla=ReglaDeAprobacion(
                        requiere_aprobacion_manual=True, umbral_monto=100.0
                    ),
                    red=RedPermitida(["prov1", "prov2"]),
                    monto=MontoMaximo(1000.0, "COP"),
                )

                partner.evaluar_novedad(
                    data.trabajo_id, data.novedad_id, data.impacto_monto
                )
                for event in partner.domain_events:
                    if event.__class__.__name__ == "DecisionPartner":
                        publicar_decision_partner(event)

            consumer.acknowledge(msg)
        except Exception:
            pass


@app.on_event("startup")
def startup_event():
    asyncio.create_task(asyncio.to_thread(consumir_comandos))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

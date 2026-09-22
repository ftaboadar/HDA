"""Plantilla de mensajería contra Pulsar local real (CONVENCIONES §9, pruebas de
integración del servicio). Requiere el cluster de `pulsar-infra/` con los
namespaces de `scripts/pulsar-namespaces-local.sh` y el Postgres del compose
del servicio (idempotencia real). Se omite si alguno no está arriba.

Comprueba lo que la prueba unitaria no puede: que el esquema queda en el Schema
Registry (A21), que un consumidor sin esquema lee el cuerpo JSON sin nulos, que
viajan las propiedades de §3, que el mismo id_evento dos veces no duplica el
efecto y que tras 3 reentregas el mensaje termina en la DLQ nativa."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import urllib.request
import uuid
from urllib.parse import urlparse

import pytest
from pulsar.schema import Record, String

PULSAR_URL = os.environ.get("PULSAR_SERVICE_URL", "pulsar://localhost:6650")
PULSAR_ADMIN = os.environ.get("PULSAR_ADMIN_URL", "http://localhost:8080")


def _escucha(url: str, puerto_defecto: int) -> bool:
    destino = urlparse(url)
    try:
        socket.create_connection(
            (destino.hostname, destino.port or puerto_defecto), 1
        ).close()
        return True
    except OSError:
        return False


def _postgres_arriba() -> bool:
    from sqlalchemy import text

    from app.common.db import engine

    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _escucha(PULSAR_URL, 6650), reason=f"Pulsar no está arriba en {PULSAR_URL}"
)


class _PruebaPlantilla(Record):
    trabajo_id = String(required=True)
    reserva_id = String()


def _topico() -> str:
    return f"persistent://hda/gestion-trabajos/prueba-plantilla-{uuid.uuid4().hex[:8]}"


def _esperar(condicion, segundos: float = 20) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.2)
    return False


@pytest.fixture
def registro():
    if not _postgres_arriba():
        pytest.skip("Postgres del compose no está arriba (idempotencia real)")
    from app.common.db import Base, engine
    from app.seedwork.infraestructura.pulsar.idempotencia import (
        RegistroMensajesProcesadosSQLAlchemy,
    )

    Base.metadata.create_all(bind=engine)
    return RegistroMensajesProcesadosSQLAlchemy()


def _consumidor(topico, manejador, registro):
    from app.seedwork.infraestructura.pulsar.mensajeria import ConsumidorPulsar

    return ConsumidorPulsar(
        service_url=PULSAR_URL,
        topico=topico,
        suscripcion="gestion-trabajos-prueba-plantilla",
        manejadores={"PruebaPlantilla": manejador},
        registro=registro,
        retardo_reentrega_ms=200,
    )


def test_publica_con_esquema_y_el_consumidor_lee_json_con_propiedades(registro):
    from app.seedwork.infraestructura.pulsar.mensajeria import PublicadorPulsar

    topico = _topico()
    recibidos = []
    consumidor = _consumidor(topico, recibidos.append, registro)
    consumidor.iniciar_en_hilo()
    publicador = PublicadorPulsar(PULSAR_URL, productor="gestion-de-trabajos")
    trabajo_id = str(uuid.uuid4())
    try:
        props = asyncio.run(
            publicador.publicar(
                topico,
                _PruebaPlantilla(trabajo_id=trabajo_id),
                tipo_evento="PruebaPlantilla",
                correlation_id=trabajo_id,
                causation_id="evento-anterior",
            )
        )
        assert _esperar(lambda: recibidos), "el consumidor no recibió el mensaje"
    finally:
        consumidor.detener()
        publicador.cerrar()

    msg = recibidos[0]
    assert msg.cuerpo == {"trabajo_id": trabajo_id}, "el cuerpo no debe llevar nulos"
    assert msg.id_evento == props["id_evento"]
    assert msg.correlation_id == trabajo_id
    assert msg.causation_id == "evento-anterior"
    assert msg.propiedades["productor"] == "gestion-de-trabajos"

    ruta = topico.removeprefix("persistent://")
    with urllib.request.urlopen(f"{PULSAR_ADMIN}/admin/v2/schemas/{ruta}/schema") as r:
        esquema = json.load(r)
    assert (
        esquema["type"] == "JSON"
    ), "el tópico debe tener esquema en el Schema Registry"
    assert "trabajo_id" in esquema["data"]


def test_mismo_id_evento_no_se_procesa_dos_veces(registro):
    import pulsar

    topico = _topico()
    recibidos = []
    consumidor = _consumidor(topico, recibidos.append, registro)
    consumidor.iniciar_en_hilo()
    cliente = pulsar.Client(PULSAR_URL)
    productor = cliente.create_producer(topico)
    propiedades = {
        "tipo_evento": "PruebaPlantilla",
        "id_evento": str(uuid.uuid4()),
        "correlation_id": "t-dup",
    }
    try:
        for _ in range(2):
            productor.send(
                json.dumps({"trabajo_id": "t-dup"}).encode(), properties=propiedades
            )
        assert _esperar(lambda: recibidos)
        time.sleep(2)
    finally:
        consumidor.detener()
        cliente.close()
    assert len(recibidos) == 1


def test_mensaje_que_siempre_falla_termina_en_la_dlq(registro):
    import pulsar

    topico = _topico()
    intentos = []

    def siempre_falla(msg):
        intentos.append(msg.id_evento)
        raise RuntimeError("falla permanente")

    consumidor = _consumidor(topico, siempre_falla, registro)
    cliente = pulsar.Client(PULSAR_URL)
    lector_dlq = cliente.subscribe(
        consumidor.topico_dlq, subscription_name="prueba-lector-dlq"
    )
    consumidor.iniciar_en_hilo()
    try:
        cliente.create_producer(topico).send(
            json.dumps({"trabajo_id": "t-dlq"}).encode(),
            properties={
                "tipo_evento": "PruebaPlantilla",
                "id_evento": str(uuid.uuid4()),
            },
        )
        msg_dlq = lector_dlq.receive(timeout_millis=30000)
    finally:
        consumidor.detener()
        cliente.close()
    assert json.loads(msg_dlq.data()) == {"trabajo_id": "t-dlq"}
    assert len(intentos) == 1 + consumidor.max_reentregas

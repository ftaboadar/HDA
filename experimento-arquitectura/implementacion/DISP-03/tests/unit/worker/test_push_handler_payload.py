"""Prueba de regresión para el bug de producción encontrado en GCP real
(2026-09-06): un evento de INTEGRACIÓN `proveedor.habilitado` (publicado por
app/application/dispatcher_eventos_dominio.py) llegaba al endpoint
`/pubsub/push` del worker con la misma forma que un mensaje de la
suscripción push, pero SIN `verificacion_id` — `recibir_push` hacía
`payload["verificacion_id"]` sin validar y reventaba con `KeyError`, lo que
Pub/Sub interpretaba como fallo y reintregaba el mismo mensaje envenenado.

La corrección de raíz es un topic de Pub/Sub físicamente distinto para
eventos de integración, sin suscripción push (ver infra/pubsub.tf,
`google_pubsub_topic.eventos_integracion`, y
`PublicadorPubSub.publicar_evento` en app/common/publicador.py) — esta
prueba cubre la defensa en profundidad complementaria en
`app/worker/push_handler.py:recibir_push`: si de todos modos llega un
mensaje sin `verificacion_id`, el handler debe responder 200 con
`{"estado": "ignorado"}` en vez de propagar una excepción sin capturar."""

import base64
import json

import pytest

from app.worker import push_handler


class _RequestFalso:
    """Doble mínimo de `fastapi.Request`: solo necesitamos `.json()`."""

    def __init__(self, envoltura: dict) -> None:
        self._envoltura = envoltura

    async def json(self) -> dict:
        return self._envoltura


def _envoltura_con_payload(payload: dict) -> dict:
    datos_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": datos_b64}}


@pytest.mark.asyncio
async def test_recibir_push_ignora_evento_de_integracion_sin_verificacion_id(monkeypatch):
    # `_publicador` normalmente lo fija `startup()` contra credenciales GCP
    # reales — aquí basta con que no sea None para pasar el assert inicial;
    # el resto del handler no debe llegar a usarlo en este camino.
    monkeypatch.setattr(push_handler, "_publicador", object())

    payload_evento_integracion = {
        "proveedor_id": "prov-123",
        "evento": "ProveedorHabilitado",
        "routing_key": "proveedor.habilitado",
    }
    request = _RequestFalso(_envoltura_con_payload(payload_evento_integracion))

    respuesta = await push_handler.recibir_push(request)

    assert respuesta == {"estado": "ignorado"}


@pytest.mark.asyncio
async def test_recibir_push_procesa_solicitud_real_sin_ser_bloqueada_por_la_validacion(
    monkeypatch,
):
    """La validación no debe descartar mensajes legítimos: si trae
    `verificacion_id`, el handler debe seguir el camino normal (aquí
    verificado solo hasta el punto en que llamaría a `procesar_verificacion`,
    sin BD real)."""
    monkeypatch.setattr(push_handler, "_publicador", object())

    class _DetenerAqui(Exception):
        """Se lanza deliberadamente para no seguir ejecutando el resto del
        handler (que sí necesitaría BD real) una vez confirmado que la
        validación de forma dejó pasar el mensaje legítimo."""

    llamado = {}

    async def _procesar_verificacion_falso(verificacion_id, proveedor_id, tipo_verificador):
        llamado["args"] = (verificacion_id, proveedor_id, tipo_verificador)
        raise _DetenerAqui

    monkeypatch.setattr(push_handler, "procesar_verificacion", _procesar_verificacion_falso)

    payload_solicitud_real = {
        "verificacion_id": "verif-1",
        "proveedor_id": "prov-1",
        "tipo_verificador": "POLICIA",
    }
    request = _RequestFalso(_envoltura_con_payload(payload_solicitud_real))

    with pytest.raises(_DetenerAqui):
        await push_handler.recibir_push(request)

    assert llamado["args"] == ("verif-1", "prov-1", "POLICIA")

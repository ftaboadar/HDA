"""Worker estándar (/salud refleja si los consumidores siguen vivos,
CONVENCIONES §5) y campos de observabilidad del §13 en logging_utils."""

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.common.logging_utils import (
    JsonFormatter,
    contexto_journey,
    log_evento,
)
from app.seedwork.infraestructura.worker import crear_app_worker


class _ConsumidorFalso:
    def __init__(self, suscripcion: str) -> None:
        self.suscripcion = suscripcion
        self.iniciado = False
        self.detenido = False
        self._vivo = True

    def iniciar_en_hilo(self) -> None:
        self.iniciado = True

    def vivo(self) -> bool:
        return self.iniciado and self._vivo

    def detener(self) -> None:
        self.detenido = True


def test_salud_200_con_todos_los_consumidores_vivos():
    consumidores = [_ConsumidorFalso("gt-a"), _ConsumidorFalso("gt-b")]
    with TestClient(crear_app_worker(lambda: consumidores)) as cliente:
        respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["consumidores"] == {"gt-a": True, "gt-b": True}
    assert all(c.detenido for c in consumidores)


def test_salud_503_si_un_consumidor_murio():
    muerto = _ConsumidorFalso("gt-b")
    with TestClient(
        crear_app_worker(lambda: [_ConsumidorFalso("gt-a"), muerto])
    ) as cliente:
        muerto._vivo = False
        respuesta = cliente.get("/salud")
    assert respuesta.status_code == 503
    assert respuesta.json()["estado"] == "degradado"


def test_salud_503_sin_consumidores():
    with TestClient(crear_app_worker(lambda: [])) as cliente:
        assert cliente.get("/salud").status_code == 503


@pytest.fixture
def capturar_logs():
    salida = io.StringIO()
    logger = logging.getLogger("application.prueba_logging")
    handler = logging.StreamHandler(salida)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    def lineas() -> list[dict]:
        return [json.loads(linea) for linea in salida.getvalue().splitlines()]

    return logger, lineas


def test_cada_linea_lleva_servicio_y_contexto_ddd(capturar_logs):
    logger, lineas = capturar_logs
    log_evento(logger, "comando_crear_trabajo", modulo="ciclo_vida", agregado="Trabajo")
    linea = lineas()[0]
    assert linea["servicio"] == "gestion-de-trabajos"
    assert linea["bounded_context"] == "ContextoGestionDeTrabajos"
    assert linea["capa"] == "application"
    assert linea["modulo"] == "ciclo_vida"
    assert linea["agregado"] == "Trabajo"
    assert linea["tipo_mensaje"] == "comando"


def test_contexto_journey_aparece_en_todas_las_lineas_del_bloque(capturar_logs):
    logger, lineas = capturar_logs
    with contexto_journey(correlation_id="t-1", saga_id="s-1"):
        log_evento(logger, "a")
        with contexto_journey(paso_saga="RESERVAR_FRANJA"):
            log_evento(logger, "b")
    log_evento(logger, "c")
    a, b, c = lineas()
    assert (a["correlation_id"], a["saga_id"]) == ("t-1", "s-1")
    assert "paso_saga" not in a
    assert b["paso_saga"] == "RESERVAR_FRANJA" and b["correlation_id"] == "t-1"
    assert "correlation_id" not in c


def test_compensacion_se_distingue_en_tipo_mensaje(capturar_logs):
    logger, lineas = capturar_logs
    log_evento(
        logger, "compensacion_enviada", tipo_comunicacion="entre_servicios_comando"
    )
    assert lineas()[0]["tipo_mensaje"] == "compensacion"


def test_tipo_comunicacion_invalido_falla(capturar_logs):
    logger, _ = capturar_logs
    with pytest.raises(ValueError):
        log_evento(logger, "x", tipo_comunicacion="por_telepatia")


def test_contexto_journey_rechaza_campos_desconocidos():
    with pytest.raises(ValueError):
        with contexto_journey(usuario="x"):
            pass

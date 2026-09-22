"""Logging estructurado (JSON lines), una línea = un objeto JSON en stdout.

Cloud Run lo ingiere como `jsonPayload` en Cloud Logging. Cada línea lleva,
además de los campos propios del evento, el CONTEXTO DDD del servicio
(dominio / subdominio / tipo de subdominio / bounded context) y la CAPA
hexagonal que la emitió, para poder filtrar en GCP y en Grafana por concepto
de diseño y no solo por nombre de servicio:

- `tipo_mensaje`: comando | evento_de_dominio | evento_de_integracion |
  mensajeria | consulta | aplicacion (se infiere del prefijo del evento).
- `severity`: campo nativo de Cloud Logging (sin él todo salía como INFO).
- `logging.googleapis.com/trace`: correlaciona el log de aplicación con el
  log de la petición HTTP de Cloud Run (requiere env GCP_PROJECT).

Campos del journey (Entrega 5, 15-arquitectura-entrega-5.md §13): cada línea
lleva además `servicio` (nombre estable de la carpeta, igual en api y worker),
`correlation_id` (= trabajo_id), `saga_id` y `paso_saga` — tomados del contexto
de la petición o del mensaje con `contexto_journey(...)` — y, cuando el
llamador los pasa, `modulo`, `agregado` y `tipo_comunicacion` (uno de
`TIPOS_COMUNICACION`). Así una sola query por `jsonPayload.correlation_id`
muestra el journey completo a través de los servicios.

`LOG_DETALLE=minimo` desactiva los eventos marcados `detalle=True` (los de
trazado fino por petición) — para corridas de carga (ESC-01 real), donde un
log extra por request cuesta CPU y dinero en Cloud Logging.

Mismo módulo copiado (no importado) en cada microservicio: cada uno es su
propio Bounded Context independiente; solo cambia CONTEXTO_DDD."""

import contextvars
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator

# Nombre estable del servicio (la carpeta en implementacion/). Es lo que se
# filtra en Logs Explorer; K_SERVICE (nombre del servicio de Cloud Run, distinto
# para api y worker) va aparte en `servicio_cloud_run`.
SERVICIO = "gestion-de-trabajos"

CONTEXTO_DDD = {
    "dominio": "MarketplaceDeServicios",
    "subdominio": "GestionDeTrabajos",
    "tipo_subdominio": "CORE_DOMAIN",
    "bounded_context": "ContextoGestionDeTrabajos",
}

_CAPAS = ("api", "application", "domain", "infrastructure", "worker", "mocks", "common")
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

# Valores válidos de `tipo_comunicacion` (15-…md §13).
TIPOS_COMUNICACION = (
    "intra_modulo",
    "entre_modulos_sync",
    "entre_modulos_async",
    "entre_servicios_comando",
    "entre_servicios_evento",
    "rest_bff",
    "externo",
)

# correlation_id / saga_id / paso_saga del journey en curso (petición HTTP o
# mensaje Pulsar). Se ponen una vez en la entrada y aparecen en cada línea.
_CAMPOS_JOURNEY = ("correlation_id", "saga_id", "paso_saga")
_contexto_journey: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "contexto_journey", default={}
)


@contextmanager
def contexto_journey(**campos: str | None) -> Iterator[None]:
    """Agrega `correlation_id`, `saga_id` y/o `paso_saga` a todas las líneas
    de log emitidas dentro del bloque (se combinan con los que ya había)."""
    desconocidos = set(campos) - set(_CAMPOS_JOURNEY)
    if desconocidos:
        raise ValueError(f"campos de journey desconocidos: {sorted(desconocidos)}")
    nuevo = {**_contexto_journey.get()}
    nuevo.update({k: str(v) for k, v in campos.items() if v is not None})
    token = _contexto_journey.set(nuevo)
    try:
        yield
    finally:
        _contexto_journey.reset(token)


def contexto_journey_actual() -> dict[str, str]:
    """Para propagar el contexto a otro hilo o a un mensaje saliente."""
    return dict(_contexto_journey.get())


def _detalle_completo() -> bool:
    return os.environ.get("LOG_DETALLE", "completo") != "minimo"


def establecer_trace(header: str | None) -> None:
    """Toma el trace id de `X-Cloud-Trace-Context` (formato TRACE/SPAN;o=1)
    para que los logs de esta petición queden correlacionados."""
    _trace_id.set(header.split("/")[0] if header else None)


def headers_trace_salientes() -> dict[str, str]:
    """Propaga el trace a la siguiente llamada HTTP (Cloud Run lo une en el
    mismo trace de Cloud Logging)."""
    trace = _trace_id.get()
    return {"X-Cloud-Trace-Context": f"{trace}/0;o=1"} if trace else {}


def _capa(nombre_logger: str) -> str:
    primero = nombre_logger.split(".")[0]
    return primero if primero in _CAPAS else "otra"


def _tipo_mensaje(evento: str) -> str:
    if evento.startswith("evento_dominio_"):
        return "evento_de_dominio"
    if evento.startswith("compensacion_"):
        return "compensacion"
    if evento.startswith("evento_integracion_"):
        return "evento_de_integracion"
    if evento.startswith("comando_"):
        return "comando"
    if evento.startswith("consulta_"):
        return "consulta"
    if evento.startswith("mensaje_"):
        return "mensajeria"
    return "aplicacion"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "nivel": record.levelname,
            "severity": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "message": record.getMessage(),
            "servicio": SERVICIO,
            "servicio_cloud_run": os.environ.get("K_SERVICE", "local"),
            "revision": os.environ.get("K_REVISION", "local"),
            "capa": _capa(record.name),
            **CONTEXTO_DDD,
            **_contexto_journey.get(),
        }
        extra = getattr(record, "campos", None)
        if extra:
            payload.update(extra)
            payload.setdefault("tipo_mensaje", _tipo_mensaje(extra.get("evento", "")))
        trace = _trace_id.get()
        proyecto = os.environ.get("GCP_PROJECT")
        if trace:
            payload["trace_id"] = trace
            if proyecto:
                payload["logging.googleapis.com/trace"] = (
                    f"projects/{proyecto}/traces/{trace}"
                )
        return json.dumps(payload, ensure_ascii=False, default=str)


def configurar_logging(nombre: str) -> logging.Logger:
    logger = logging.getLogger(nombre)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_evento(
    logger: logging.Logger,
    evento: str,
    nivel: str = "info",
    detalle: bool = False,
    **campos,
) -> None:
    """`nivel` por defecto "info". `detalle=True` marca un evento de trazado
    fino que se omite con LOG_DETALLE=minimo. Campos reconocidos del §13:
    `modulo`, `agregado`, `tipo_comunicacion` (validado contra
    TIPOS_COMUNICACION) y `tipo_mensaje` (si no se pasa, se infiere del nombre
    del evento)."""
    if detalle and not _detalle_completo():
        return
    tipo = campos.get("tipo_comunicacion")
    if tipo is not None and tipo not in TIPOS_COMUNICACION:
        raise ValueError(f"tipo_comunicacion inválido: {tipo!r}")
    metodo = getattr(logger, nivel, logger.info)
    metodo(evento, extra={"campos": {"evento": evento, **campos}})


def describir_mensaje(
    payload: dict,
    *,
    canal: str,
    topico: str,
    version_esquema: str = "1",
    **extra,
) -> dict:
    """Campos estándar de un mensaje asíncrono (publicado o recibido): dónde
    viajó, cómo se serializó y qué forma tiene. Sirve para ver en los logs la
    topología de datos y la versión del contrato sin abrir el broker."""
    cuerpo = json.dumps(payload, default=str).encode()
    ids = {
        k: payload[k]
        for k in (
            "verificacion_id",
            "trabajo_id",
            "proveedor_id",
            "novedad_id",
            "pago_id",
        )
        if k in payload
    }
    return {
        **ids,
        "canal": canal,
        "topico": topico,
        "formato_serializacion": "json",
        "content_type": "application/json",
        "tamano_bytes": len(cuerpo),
        "esquema_campos": sorted(payload),
        "version_esquema": version_esquema,
        **extra,
    }

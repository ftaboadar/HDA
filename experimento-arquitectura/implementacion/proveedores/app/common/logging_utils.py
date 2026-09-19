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

CONTEXTO_DDD = {
    "dominio": "MarketplaceDeServicios",
    "subdominio": "ProveedoresDeServicio",
    "tipo_subdominio": "CORE_DOMAIN",
    "bounded_context": "ContextoProveedores",
}

_CAPAS = ("api", "application", "domain", "infrastructure", "worker", "mocks", "common")
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


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
            "servicio": os.environ.get("K_SERVICE", "local"),
            "revision": os.environ.get("K_REVISION", "local"),
            "capa": _capa(record.name),
            **CONTEXTO_DDD,
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
                payload["logging.googleapis.com/trace"] = f"projects/{proyecto}/traces/{trace}"
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
    fino que se omite con LOG_DETALLE=minimo."""
    if detalle and not _detalle_completo():
        return
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
        for k in ("verificacion_id", "trabajo_id", "proveedor_id", "novedad_id", "pago_id")
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

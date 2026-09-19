"""Logging estructurado (JSON lines) — es la fuente de datos crudos que
tests/reporte.py y el análisis de validador-hipotesis usan para calcular
las métricas del experimento (ver plan.md, sección 6)."""

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        extra = getattr(record, "campos", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def configurar_logging(nombre: str) -> logging.Logger:
    logger = logging.getLogger(nombre)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_evento(logger: logging.Logger, evento: str, nivel: str = "info", **campos) -> None:
    """`nivel` es opcional (default "info") para no romper las ~30 llamadas
    existentes que no lo pasan. Se usa "error" en
    application/dispatcher_eventos_dominio.py cuando falla la publicación de
    un evento de integración secundario — ver docstring de ese módulo y de
    worker/push_handler.py: el fallo se registra pero no se propaga, porque
    el handler push debe responder 200 aun si esta publicación falla."""
    metodo = getattr(logger, nivel, logger.info)
    metodo(evento, extra={"campos": {"evento": evento, **campos}})

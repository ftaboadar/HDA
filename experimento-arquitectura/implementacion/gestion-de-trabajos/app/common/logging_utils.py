"""Logging estructurado (JSON lines) — mismo patrón que
implementacion/DISP-03/app/common/logging_utils.py, copiado (no importado)
porque cada microservicio es su propio Bounded Context independiente."""

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


def log_evento(
    logger: logging.Logger, evento: str, nivel: str = "info", **campos
) -> None:
    metodo = getattr(logger, nivel, logger.info)
    metodo(evento, extra={"campos": {"evento": evento, **campos}})

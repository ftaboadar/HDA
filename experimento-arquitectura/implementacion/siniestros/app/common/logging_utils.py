import json
import logging
from datetime import datetime, timezone

def log_evento(tipo_mensaje: str, correlation_id: str, capa: str, detalles: dict = None):
    log = {
        "dominio": "HogarDeLosAlpes",
        "subdominio": "Siniestros",
        "tipo_subdominio": "Core",
        "bounded_context": "Siniestros",
        "capa": capa,
        "tipo_mensaje": tipo_mensaje,
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if detalles:
        log.update(detalles)
    logging.info(json.dumps(log))

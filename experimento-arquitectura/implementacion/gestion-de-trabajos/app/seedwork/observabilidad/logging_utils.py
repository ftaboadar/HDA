import logging
import json

class ObservabilityFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "servicio": getattr(record, "servicio", "unknown"),
            "modulo": getattr(record, "modulo", "unknown"),
            "agregado": getattr(record, "agregado", "unknown"),
            "correlation_id": getattr(record, "correlation_id", "unknown"),
            "saga_id": getattr(record, "saga_id", "none"),
            "paso_saga": getattr(record, "paso_saga", "none"),
            "tipo_comunicacion": getattr(record, "tipo_comunicacion", "unknown"),
        }
        return json.dumps(log_record)

def setup_logger(name, log_level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = ObservabilityFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Ejemplo de uso:
# logger = setup_logger("app")
# logger.info("Procesando evento", extra={"servicio": "gestion-de-trabajos", "modulo": "trabajos", "agregado": "Trabajo", "correlation_id": "123", "saga_id": "456", "paso_saga": "1", "tipo_comunicacion": "evento"})

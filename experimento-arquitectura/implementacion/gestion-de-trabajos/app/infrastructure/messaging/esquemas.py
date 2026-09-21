import json
import time
import uuid
from typing import Any, Callable, Type, TypeVar
import pulsar
from pulsar.schema import Record

T = TypeVar('T', bound=Record)

def publicar_mensaje_generico(
    productor: pulsar.Producer,
    mensaje: Record,
    tipo_evento: str,
    productor_nombre: str,
    correlation_id: str,
    causation_id: str = None,
    version_esquema: str = "1"
) -> str:
    propiedades = {
        "tipo_evento": tipo_evento,
        "version_esquema": version_esquema,
        "content_type": "application/json",
        "productor": productor_nombre,
        "id_evento": str(uuid.uuid4()),
        "correlation_id": str(correlation_id),
    }
    if causation_id:
        propiedades["causation_id"] = str(causation_id)
        
    return productor.send(mensaje, properties=propiedades)


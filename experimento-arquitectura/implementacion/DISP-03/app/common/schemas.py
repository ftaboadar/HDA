import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TipoVerificador = Literal["policia", "rues", "certificadora"]
EstadoVerificacion = Literal["PENDIENTE", "COMPLETADA", "FALLIDA_DLQ"]


class VerificacionCreate(BaseModel):
    proveedor_id: str
    tipo_verificador: TipoVerificador


class VerificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proveedor_id: str
    tipo_verificador: TipoVerificador
    estado: EstadoVerificacion
    intentos: int
    motivo_falla: str | None = None
    creado_en: datetime
    actualizado_en: datetime
    completado_en: datetime | None = None
    en_dlq_desde: datetime | None = None
    reprocesos: int

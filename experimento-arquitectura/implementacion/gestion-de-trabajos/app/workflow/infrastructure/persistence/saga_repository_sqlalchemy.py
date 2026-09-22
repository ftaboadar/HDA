import json
import uuid
from typing import Optional

from app.common.db import SessionLocal
from app.workflow.domain.saga import SagaInstancia
from app.workflow.domain.value_objects import EstadoSaga, PasoSaga
from app.ciclo_vida.domain.value_objects import TrabajoId
from app.infrastructure.persistence.models_db import SagaInstanciaORM, SagaLogORM


class SagaRepositorySQLAlchemy:
    def guardar(
        self,
        saga: SagaInstancia,
        secuencia: int = 1,
        tipo: str = "COMANDO_ENVIADO",
        servicio: str = "gestion-de-trabajos",
        mensaje: str = "Comando",
        id_mensaje: Optional[str] = None,
        payload: Optional[dict] = None,
        guardar_log: bool = True,
    ) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(SagaInstanciaORM, saga.id)
            if fila is None:
                fila = SagaInstanciaORM(
                    saga_id=saga.id,
                    trabajo_id=saga.trabajo_id.valor,
                    origen=saga.origen,
                    estado=saga.estado.value,
                    paso_actual=saga.paso_actual.value,
                    iniciada_en=saga.iniciada_en,
                    actualizada_en=saga.actualizada_en,
                )
                sesion.add(fila)
            else:
                fila.estado = saga.estado.value
                fila.paso_actual = saga.paso_actual.value
                fila.actualizada_en = saga.actualizada_en

            if guardar_log:
                log = SagaLogORM(
                    saga_id=saga.id,
                    secuencia=secuencia,
                    paso=saga.paso_actual.value,
                    tipo=tipo,
                    servicio=servicio,
                    mensaje=mensaje,
                    id_mensaje=id_mensaje,
                    payload=json.dumps(payload) if payload else None,
                )
                sesion.add(log)

            sesion.commit()

    def obtener_por_trabajo_id(self, trabajo_id: uuid.UUID) -> Optional[SagaInstancia]:
        with SessionLocal() as sesion:
            fila = (
                sesion.query(SagaInstanciaORM).filter_by(trabajo_id=trabajo_id).first()
            )
            if not fila:
                return None
            return self._a_dominio(fila)

    def obtener_por_id(self, id: uuid.UUID) -> Optional[SagaInstancia]:
        with SessionLocal() as sesion:
            fila = sesion.get(SagaInstanciaORM, id)
            if not fila:
                return None
            return self._a_dominio(fila)

    def _a_dominio(self, fila: SagaInstanciaORM) -> SagaInstancia:
        return SagaInstancia(
            id=fila.saga_id,
            trabajo_id=TrabajoId(fila.trabajo_id),
            origen=fila.origen,
            estado=EstadoSaga(fila.estado),
            paso_actual=PasoSaga(fila.paso_actual),
            iniciada_en=fila.iniciada_en,
            actualizada_en=fila.actualizada_en,
        )

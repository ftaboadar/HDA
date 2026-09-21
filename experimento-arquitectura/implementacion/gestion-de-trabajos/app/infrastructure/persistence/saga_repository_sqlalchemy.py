import json
import uuid
from typing import Optional

from app.common.db import SessionLocal
from app.domain.workflow.saga import SagaInstancia
from app.domain.workflow.value_objects import EstadoSaga, PasoSaga
from app.domain.ciclo_vida.value_objects import TrabajoId
from app.infrastructure.persistence.models_db import SagaInstanciaORM, SagaLogORM

class SagaRepositorySQLAlchemy:
    def guardar(self, saga: SagaInstancia, evento_log: Optional[str] = None, detalles_log: Optional[dict] = None) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(SagaInstanciaORM, saga.id)
            datos_contexto = json.dumps({"origen": saga.origen})
            if fila is None:
                fila = SagaInstanciaORM(
                    id=saga.id,
                    correlation_id=str(saga.trabajo_id.valor),
                    estado=saga.estado.value,
                    paso_actual=saga.paso_actual.value,
                    creado_en=saga.iniciada_en,
                    actualizado_en=saga.actualizada_en,
                    datos_contexto=datos_contexto
                )
                sesion.add(fila)
            else:
                fila.estado = saga.estado.value
                fila.paso_actual = saga.paso_actual.value
                fila.actualizado_en = saga.actualizada_en
                fila.datos_contexto = datos_contexto

            if evento_log:
                log = SagaLogORM(
                    saga_id=saga.id,
                    paso=saga.paso_actual.value,
                    evento=evento_log,
                    detalles=json.dumps(detalles_log) if detalles_log else None
                )
                sesion.add(log)

            sesion.commit()

    def obtener_por_trabajo_id(self, trabajo_id: uuid.UUID) -> Optional[SagaInstancia]:
        with SessionLocal() as sesion:
            fila = sesion.query(SagaInstanciaORM).filter_by(correlation_id=str(trabajo_id)).first()
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
        datos_contexto = json.loads(fila.datos_contexto) if fila.datos_contexto else {}
        return SagaInstancia(
            id=fila.id,
            trabajo_id=TrabajoId(uuid.UUID(fila.correlation_id)),
            origen=datos_contexto.get("origen", "API"),
            estado=EstadoSaga(fila.estado),
            paso_actual=PasoSaga(fila.paso_actual),
            iniciada_en=fila.creado_en,
            actualizada_en=fila.actualizado_en
        )

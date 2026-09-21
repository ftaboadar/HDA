from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.common.db import Base


class SuscripcionModel(Base):
    __tablename__ = "suscripciones"
    id = Column(String, primary_key=True)
    cliente_id = Column(String, nullable=False)
    dia_semana = Column(Integer, nullable=False)
    bloque = Column(String, nullable=False)
    proveedor_continuo_id = Column(String, nullable=True)
    ciclos = relationship(
        "CicloSuscripcionModel",
        back_populates="suscripcion",
        cascade="all, delete-orphan",
    )


class CicloSuscripcionModel(Base):
    __tablename__ = "ciclos_suscripcion"
    id = Column(String, primary_key=True)
    suscripcion_id = Column(String, ForeignKey("suscripciones.id"))
    numero_ciclo = Column(Integer, nullable=False)
    proveedor_id = Column(String, nullable=True)
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    completado = Column(Boolean, default=False)
    suscripcion = relationship("SuscripcionModel", back_populates="ciclos")

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import uuid

Base = declarative_base()

class ProveedorModel(Base):
    __tablename__ = 'proveedores'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String(255), nullable=False)
    documento = Column(String(50), nullable=False)
    tipo_documento = Column(String(20), nullable=False)
    email = Column(String(255))
    telefono = Column(String(50))
    estado_verificacion = Column(String(50), default='PENDIENTE')
    score = Column(Integer, default=0)
    
    tecnicos = relationship("TecnicoModel", back_populates="proveedor")
    zonas_cobertura = relationship("ZonaCoberturaModel", back_populates="proveedor")


class TecnicoModel(Base):
    __tablename__ = 'tecnicos'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proveedor_id = Column(String(36), ForeignKey('proveedores.id'))
    nombres = Column(String(255), nullable=False)
    apellidos = Column(String(255), nullable=False)
    documento = Column(String(50), nullable=False)
    email = Column(String(255))
    
    proveedor = relationship("ProveedorModel", back_populates="tecnicos")
    agendas = relationship("AgendaModel", back_populates="tecnico")


class ZonaCoberturaModel(Base):
    __tablename__ = 'zonas_cobertura'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proveedor_id = Column(String(36), ForeignKey('proveedores.id'))
    pais = Column(String(100))
    ciudad = Column(String(100))
    codigo_postal = Column(String(20))
    
    proveedor = relationship("ProveedorModel", back_populates="zonas_cobertura")


class AgendaModel(Base):
    __tablename__ = 'agendas'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tecnico_id = Column(String(36), ForeignKey('tecnicos.id'))
    fecha_inicio = Column(DateTime, nullable=False)
    fecha_fin = Column(DateTime, nullable=False)
    estado = Column(String(50), default='DISPONIBLE') # DISPONIBLE, RESERVADO
    orden_id = Column(String(36), nullable=True) # Referencia al trabajo en gestion-de-trabajos
    
    tecnico = relationship("TecnicoModel", back_populates="agendas")

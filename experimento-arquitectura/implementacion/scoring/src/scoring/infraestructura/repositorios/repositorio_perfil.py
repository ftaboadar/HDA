from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from src.scoring.dominio.entidades.perfil_crediticio import PerfilCrediticio
import uuid

Base = declarative_base()

class PerfilCrediticioModel(Base):
    __tablename__ = "perfiles_crediticios"
    id = Column(String, primary_key=True)
    cliente_id = Column(String, unique=True)
    puntaje = Column(Integer)
    historial_trabajos = Column(Integer)

class RepositorioPerfil:
    def __init__(self, db_url="sqlite:///scoring.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def obtener_por_cliente_id(self, cliente_id: str) -> PerfilCrediticio:
        session = self.Session()
        modelo = session.query(PerfilCrediticioModel).filter_by(cliente_id=cliente_id).first()
        session.close()
        if modelo:
            return PerfilCrediticio(
                id=modelo.id,
                cliente_id=modelo.cliente_id,
                puntaje=modelo.puntaje,
                historial_trabajos=modelo.historial_trabajos
            )
        return PerfilCrediticio(id=str(uuid.uuid4()), cliente_id=cliente_id, puntaje=50, historial_trabajos=0)

    def guardar(self, perfil: PerfilCrediticio):
        session = self.Session()
        modelo = session.query(PerfilCrediticioModel).filter_by(id=perfil.id).first()
        if not modelo:
            modelo = PerfilCrediticioModel(id=perfil.id, cliente_id=perfil.cliente_id)
            session.add(modelo)
        modelo.puntaje = perfil.puntaje
        modelo.historial_trabajos = perfil.historial_trabajos
        session.commit()
        session.close()

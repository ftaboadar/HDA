from sqlalchemy import create_engine, Column, String, Float, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./siniestros.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SiniestroModel(Base):
    __tablename__ = "siniestros"
    id = Column(String, primary_key=True, index=True)
    cliente_id = Column(String, index=True)
    monto_reclamado = Column(Float)
    estado = Column(String)
    reserva = Column(Float)
    facturas = Column(JSON)

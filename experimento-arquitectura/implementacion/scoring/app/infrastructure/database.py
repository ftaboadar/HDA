from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class FotografoScoringModel(Base):
    __tablename__ = 'fotografo_scoring'
    
    id = Column(String(36), primary_key=True)
    fotografo_id = Column(String(36), unique=True, nullable=False)
    puntuacion_actual = Column(Float, default=0.0)
    trabajos_completados = Column(Integer, default=0)
    fecha_ultima_actualizacion = Column(DateTime)

engine = create_engine('sqlite:///scoring.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

"""Engine/sesión SQLAlchemy — persistencia real (Postgres), no un dict en
memoria. Base de datos propia de este microservicio (`hda_pagos`), separada
de la de Gestión de Trabajos desde que Pagos dejó de ser un submódulo ACL
dentro de ese proceso (ver README.md, sección "Frontera del API")."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

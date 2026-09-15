"""Engine/sesión SQLAlchemy — persistencia real (Postgres), no un dict en
memoria. Una sola base de datos para todo el microservicio: la tabla
`pagos` del submódulo ACL vive aquí también (ver 12-plan-entrega-4.md
sección 5: "Pagos no aporta una BD propia al conteo")."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

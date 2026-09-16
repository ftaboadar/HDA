"""Engine/sesión SQLAlchemy — persistencia real (Postgres), no un dict en
memoria. Desde la separación de Pagos en su propio microservicio (ver
`implementacion/pagos/README.md`), esta base de datos solo cubre las tablas
de Gestión de Trabajos (`trabajos`, `trabajos_elegibles_pago`, `novedades`).

`pool_size`/`max_overflow` explícitos (no el default de SQLAlchemy,
5+10=15 conexiones): la prueba de carga de DISP-02
(`tests/integracion/test_disp02_throttler.py`) dispara ráfagas de miles de
`POST /novedades` concurrentes, cada una con su propia escritura síncrona
vía `asyncio.to_thread` (ver `application/commands/publicar_novedad.py`) —
con el default de 15 conexiones, la ráfaga saturaba el pool y las
peticiones HTTP entrantes se acumulaban hasta agotar el `PoolTimeout` del
lado del cliente de prueba (hallazgo real de la primera corrida de esta
tarea, no una suposición). 50+50=100 conexiones es suficiente para esta
escala de PoC; una escala mayor (o múltiples réplicas) requeriría un
pooler externo (PgBouncer) en vez de subir más este número, fuera de
alcance aquí."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=50,
    max_overflow=50,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

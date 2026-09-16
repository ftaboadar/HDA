"""Engine/sesión SQLAlchemy — persistencia real (Postgres), no un dict en
memoria. Desde la separación de Pagos en su propio microservicio (ver
`implementacion/pagos/README.md`), esta base de datos solo cubre las tablas
de Gestión de Trabajos (`trabajos`, `trabajos_elegibles_pago`, `novedades`).

`pool_size`/`max_overflow`/`pool_timeout` son configurables (ver
`app.common.config.Settings.db_pool_size`, `db_max_overflow`,
`db_pool_timeout`; env vars `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
`DB_POOL_TIMEOUT`) — no el default de SQLAlchemy (5+10=15 conexiones):
la prueba de carga de DISP-02 (`tests/integracion/test_disp02_throttler.py`)
dispara ráfagas de miles de `POST /novedades` concurrentes, cada una con su
propia escritura síncrona vía `asyncio.to_thread` (ver
`application/commands/publicar_novedad.py`) — con el default de 15
conexiones, la ráfaga saturaba el pool y las peticiones HTTP entrantes se
acumulaban hasta agotar el `PoolTimeout` del lado del cliente de prueba
(hallazgo real de la primera corrida de esta tarea, no una suposición). El
default actual, 50+50=100 conexiones por instancia, es suficiente para esta
escala de PoC; también es sospechoso como causa de que ESC-01 siga sin
pasar su umbral (<2s) en GCP bajo Cloud Run con `max_instance_count=10`
(ver `RESULTADOS-ESCALABILIDAD-GCP.md`, sección 3, punto 1) — al ser
configurable por variable de entorno, se puede retunear por instancia sin
tocar código, o bajarlo si el tier de Cloud SQL no soporta
(pool_size+max_overflow) × max_instance_count conexiones simultáneas. Una
escala mayor (o múltiples réplicas) requeriría un pooler externo
(PgBouncer) en vez de subir más este número, fuera de alcance aquí."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

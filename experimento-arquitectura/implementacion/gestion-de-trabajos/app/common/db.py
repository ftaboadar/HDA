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
(hallazgo real de la primera corrida de esta tarea, no una suposición).

RE-DIMENSIONADO (sesión de cálculo de capacidad, ver comentario extendido
junto a `db_pool_size`/`db_max_overflow` en `app/common/config.py` y junto
a `sql_tier` en `infra/variables.tf`): el default anterior, 50+50=100 por
instancia, NO era insuficiente en cantidad absoluta — era MAYOR que
`max_connections` real de Postgres dividido entre las instancias posibles,
es decir, generaba sobresuscripción de conexiones contra Cloud SQL en vez
de resolverla (causa raíz confirmada de que las corridas 1 y 2 de ESC-01 en
GCP no mejoraran). El nuevo default, 10+5=15, se eligió para que
`(pool_size+max_overflow) × max_instance_count` quede por debajo de
`max_connections` de la instancia de Cloud SQL con margen — no para
"aguantar más carga" en abstracto. Una escala mayor (más instancias o un
tier de Cloud SQL más grande) requeriría subir este número EN CONJUNTO con
`max_connections` (vía tier o `database_flags`) y con
`max_instance_request_concurrency` de Cloud Run — nunca uno solo de los
tres; o adoptar un pooler externo (PgBouncer) o el "Managed Connection
Pooling" nativo de Cloud SQL Enterprise Plus si el número de conexiones
necesario supera lo que cualquier tier razonable de Cloud SQL ofrece de
forma nativa — fuera de alcance en este PoC."""

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

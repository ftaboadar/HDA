"""Configuración centralizada, cargada desde variables de entorno — mismo
patrón que implementacion/proveedores/app/common/config.py.

Los valores por defecto asumen desarrollo local. `pulsar_service_url`
apunta al cluster local que construye Daniel en
`implementacion/pulsar-infra/` (ver 12-plan-entrega-4.md sección 3).

Separación de Pagos: `stripe_mock_url`/`mercadopago_mock_url` (mocks de
Stripe/MercadoPago) se movieron a `implementacion/pagos/app/common/config.py`
— ya no se usan en este servicio.

Settings de DISP-02 (Sidecar/Throttler hacia el CRM "Gestión de Agentes",
ver `escenarios_calidad.md`): `crm_mock_url`, `crm_limite_rps`,
`throttler_cola_tamano`, `throttler_max_reintentos`,
`throttler_backoff_base_s`, `throttler_backoff_max_s` — nombres exactos que
usa `experimento-runner` para configurar el doble del CRM y la prueba de
carga; no renombrar sin avisar a ese agente."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://hda:hda@postgres:5432/gestion_trabajos"

    # --- Pool de conexiones SQLAlchemy (ver docstring de app/common/db.py) ---
    # RE-DIMENSIONADO (sesión de cálculo de capacidad post-corridas 1 y 2 de
    # ESC-01 en GCP real, ver infra/service.tf y comentario junto a
    # `sql_tier` en infra/variables.tf): el valor anterior (50+50=100) NO
    # era la causa raíz de que ESC-01 siguiera sin pasar su umbral -- era
    # peor que eso, era una fuente de SOBRESUSCRIPCIÓN de conexiones contra
    # Postgres. `db_pool_size + db_max_overflow` debe ser el MISMO número
    # que `max_instance_request_concurrency` (Cloud Run, infra/service.tf) y
    # que `max_workers` del ThreadPoolExecutor (app/api/main.py, ahora
    # derivado de estos dos settings, no un literal aparte) -- los tres
    # deben coincidir, nunca el segundo/tercero mayor que el primero. Ese
    # número, multiplicado por `max_instance_count` (hoy 20), es la demanda
    # máxima de conexiones simultáneas contra Postgres en el peor caso: debe
    # quedar por debajo de `max_connections` de la instancia de Cloud SQL,
    # con margen (no al límite). `max_connections` NO es configurable acá:
    # depende de la memoria del tier de Cloud SQL (ver tabla oficial de
    # `google_sql_database_instance.database_flags` / Cloud SQL "Supported
    # flags" para postgres: 3.75-6GB -> 100, 6-7.5GB -> 200, 7.5-15GB -> 400
    # ...). El tier actual, `db-custom-2-7680` (7.5GB), cae en el bucket de
    # 400. Con 10+5=15 por instancia × 20 instancias = 300 conexiones en el
    # peor caso -- 75% de 400, dejando ~100 de margen para conexiones de
    # sistema/monitoreo de Cloud SQL y solapes transitorios de escalado (no
    # el 100% exacto). Configurables por variable de entorno (DB_POOL_SIZE,
    # DB_MAX_OVERFLOW, DB_POOL_TIMEOUT) para poder re-tunear sin tocar
    # código, siempre manteniendo la igualdad con `max_instance_request_
    # concurrency` de infra/service.tf.
    db_pool_size: int = 10
    db_max_overflow: int = 5
    # Antes 30s: con el pool correctamente dimensionado (sin sobresuscripción)
    # este timeout no debería dispararse en operación normal. Si se dispara
    # de todos modos (pico transitorio durante un evento de escalado de
    # Cloud Run), preferimos que la request falle RÁPIDO -- y cuente como
    # rechazo medible -- a que espere hasta 30s y garantice por sí sola
    # violar el p95 < 2s de ESC-01 aunque termine "exitosa".
    db_pool_timeout: int = 5

    pulsar_service_url: str = "pulsar://localhost:6650"
    # Nombre completo de tópico persistente en Pulsar (namespace propio de
    # este servicio, ver 12-plan-entrega-4.md sección 3) — no solo el
    # nombre corto "trabajos.finalizado", para que quede explícito el
    # namespace/tenant desde configuración y no hardcodeado en el cliente.
    pulsar_topic_trabajos_finalizado: str = (
        "persistent://hda/gestion-trabajos/trabajos.finalizado"
    )

    # --- DISP-02: Sidecar/Throttler hacia el CRM "Gestión de Agentes" ---
    # URL base del doble (mock) del CRM SaaS externo — lo construye otro
    # agente en implementacion/mocks-crm/, expone POST {crm_mock_url}/webhooks
    # con rate limiting real (429 + Retry-After) para poder probar el
    # throttling de verdad.
    crm_mock_url: str = "http://localhost:9200"
    # Límite de tasa (requests/segundo) que el token bucket del Throttler
    # respeta al enviar hacia el CRM — debe configurarse igual o por debajo
    # del límite real (o simulado) del CRM mock.
    crm_limite_rps: float = 50.0
    # Tamaño de la cola en memoria (asyncio.Queue) del Throttler — ver
    # cálculo de dimensionamiento (absorber un pico de 4x) en el docstring
    # de infrastructure/messaging/throttler.py.
    throttler_cola_tamano: int = 10_000
    # Reintentos máximos por Novedad antes de marcarla AGOTADA en vez de
    # perderla en silencio.
    throttler_max_reintentos: int = 5
    throttler_backoff_base_s: float = 0.5
    throttler_backoff_max_s: float = 30.0


settings = Settings()

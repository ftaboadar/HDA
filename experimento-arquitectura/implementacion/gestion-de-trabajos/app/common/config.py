"""Configuración centralizada, cargada desde variables de entorno — mismo
patrón que implementacion/DISP-03/app/common/config.py.

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

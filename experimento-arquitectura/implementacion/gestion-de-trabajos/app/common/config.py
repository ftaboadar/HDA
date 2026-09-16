"""Configuración centralizada, cargada desde variables de entorno — mismo
patrón que implementacion/DISP-03/app/common/config.py.

Los valores por defecto asumen desarrollo local. `pulsar_service_url`
apunta al cluster local que construye Daniel en
`implementacion/pulsar-infra/` (ver 12-plan-entrega-4.md sección 3).

Separación de Pagos: `stripe_mock_url`/`mercadopago_mock_url` (mocks de
Stripe/MercadoPago) se movieron a `implementacion/pagos/app/common/config.py`
— ya no se usan en este servicio."""

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


settings = Settings()

"""Configuración centralizada, cargada desde variables de entorno — mismo
patrón que implementacion/DISP-03/app/common/config.py.

Los valores por defecto asumen desarrollo local. `pulsar_service_url`
apunta al cluster local que construye Daniel en
`implementacion/pulsar-infra/` (ver 12-plan-entrega-4.md sección 3);
`stripe_mock_url`/`mercadopago_mock_url` apuntan a los mocks que construye
Johan en `implementacion/mocks-pagos/` — ambos son stubs razonables para no
bloquear este desarrollo mientras esas piezas se terminan en paralelo."""

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

    # Mocks de sistemas externos (Pagos, GENERIC_SUBDOMAIN — ver
    # 12-plan-entrega-4.md sección 0.1). Stub local por defecto: cada quien
    # levanta implementacion/mocks-pagos/ para probar contra algo real.
    stripe_mock_url: str = "http://localhost:9100"
    mercadopago_mock_url: str = "http://localhost:9100"
    http_timeout_s: float = 5.0


settings = Settings()

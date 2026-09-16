"""Configuración centralizada, cargada desde variables de entorno — mismo
patrón que `gestion-de-trabajos/app/common/config.py` y
`implementacion/DISP-03/app/common/config.py`.

Los valores por defecto asumen desarrollo local. `stripe_mock_url`/
`mercadopago_mock_url` apuntan a los mocks de sistemas externos
(`implementacion/mocks-pagos/`, `GENERIC_SUBDOMAIN` — ver
`12-plan-entrega-4.md` sección 0.1). Sin `pulsar_service_url`: este
microservicio no tiene tópico de integración propio (ver README.md, sección
"Eventos: dominio vs. integración")."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://hda:hda@postgres:5432/hda_pagos"

    # Mocks de sistemas externos (Pagos, GENERIC_SUBDOMAIN — ver
    # 12-plan-entrega-4.md sección 0.1). Stub local por defecto: cada quien
    # levanta implementacion/mocks-pagos/ para probar contra algo real.
    stripe_mock_url: str = "http://localhost:9100"
    mercadopago_mock_url: str = "http://localhost:9100"
    http_timeout_s: float = 5.0


settings = Settings()

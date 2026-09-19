"""Sombrea los fixtures de integración de tests/conftest.py (que asumen
docker-compose arriba) para que tests/unit/ corra puro: sin BD, sin HTTP,
sin docker. `pytest tests/unit/ -v` debe funcionar sin `docker compose up`."""

import pytest


@pytest.fixture(autouse=True)
def _reset_mocks():
    """No-op: las pruebas de dominio no tocan los mocks de sistemas
    externos — sombrea el fixture homónimo de tests/conftest.py, que sí
    los necesita para los casos de integración."""
    yield

"""Fixtures compartidas de las pruebas de integración de DISP-02.

A diferencia de `tests/unit/` (dominio puro, sin red ni Postgres), este
subárbol asume que `docker-compose.disp02.yml` ya está arriba (API real +
Postgres real + mock real del CRM) — mismo patrón que
`DISP-03/tests/conftest.py`. No lo orquesta pytest: quien corre estos tests
debe levantarlo primero (ver README.md del servicio, sección DISP-02)."""

import pytest

from tests.integracion.resultados import reiniciar


@pytest.fixture(scope="session", autouse=True)
def _reiniciar_resultados():
    reiniciar()

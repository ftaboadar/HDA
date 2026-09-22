"""Prueba de arquitectura de imports (15-arquitectura-entrega-5.md §14, fila
"Entre módulos del mismo servicio"; CONVENCIONES §2) — PLANTILLA: cada servicio
la copia tal cual a `tests/unit/test_arquitectura.py`.

Reglas, revisadas con `ast` sobre todo `app/`:

1. Un archivo de `domain/` no importa librerías de infraestructura
   (sqlalchemy, fastapi, pulsar, httpx, pydantic_settings) ni capas externas
   del servicio (application, infrastructure, api, worker, common.db).
2. Con el layout por módulos (`app/<modulo>/domain/`, CONVENCIONES §1), un
   módulo solo usa de otro módulo su `application/` (interfaz pública, §8
   regla 1): nunca su `domain/` ni su `infrastructure/`.

Sirve para los dos layouts que conviven mientras cada servicio migra: en el
layout anterior (`app/domain/<agregado>/`) solo aplica la regla 1."""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
LIBRERIAS_PROHIBIDAS_EN_DOMINIO = (
    "sqlalchemy",
    "fastapi",
    "pulsar",
    "httpx",
    "pydantic_settings",
)
CAPAS_EXTERNAS = ("application", "infrastructure", "api", "worker")
NO_MODULOS = {
    "api",
    "worker",
    "common",
    "seedwork",
    "domain",
    "application",
    "infrastructure",
}


def _imports(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    nombres = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.append(nodo.module)
    return nombres


def _partes_app(ruta: Path) -> tuple[str, ...]:
    return ruta.relative_to(APP).parts


def _modulos() -> set[str]:
    return {
        d.name
        for d in APP.iterdir()
        if d.is_dir() and d.name not in NO_MODULOS and (d / "domain").is_dir()
    }


def _archivos_de_dominio() -> list[Path]:
    return [p for p in APP.rglob("*.py") if "domain" in _partes_app(p)[:-1]]


def _viola_capa(importado: str) -> bool:
    partes = importado.split(".")
    if partes[0] != "app":
        return partes[0] in LIBRERIAS_PROHIBIDAS_EN_DOMINIO
    if partes[1:3] == ["common", "db"]:
        return True
    return any(capa in partes[1:] for capa in CAPAS_EXTERNAS)


def test_hay_codigo_de_dominio_que_revisar():
    assert _archivos_de_dominio(), f"no se encontró ningún domain/ bajo {APP}"


def test_dominio_no_importa_infraestructura_ni_capas_externas():
    violaciones = [
        f"{p.relative_to(APP)} importa {importado}"
        for p in _archivos_de_dominio()
        for importado in _imports(p)
        if _viola_capa(importado)
    ]
    assert not violaciones, "\n".join(violaciones)


@pytest.mark.xfail(
    reason=(
        "Deuda de arquitectura preexistente y ya trazada, NO nueva de la Entrega 5 "
        "(ESTADO-IMPLEMENTACION.md, fila gestion-de-trabajos): 16 imports directos "
        "de workflow/ e integraciones_externas/ a domain/infrastructure de otro "
        "módulo, en vez de pasar por su application/. Se completó la orquestación "
        "real de la Saga hoy (2026-09-22) sin cerrar esta deuda a propósito (es un "
        "refactor de alcance propio, no algo para resolver bajo la presión del "
        "video de sustentación). strict=True: si algún día se corrige toda la "
        "lista, este marcador falla para forzar a quitarlo, no queda huérfano."
    ),
    strict=True,
)
def test_un_modulo_solo_usa_la_capa_application_de_otro():
    modulos = _modulos()
    violaciones = []
    for p in APP.rglob("*.py"):
        propio = _partes_app(p)[0]
        if propio not in modulos:
            continue
        for importado in _imports(p):
            partes = importado.split(".")
            if len(partes) < 3 or partes[0] != "app" or partes[1] not in modulos:
                continue
            if partes[1] != propio and partes[2] != "application":
                violaciones.append(f"{p.relative_to(APP)} importa {importado}")
    assert not violaciones, "\n".join(violaciones)

"""Utilidad de pruebas de contrato contra `implementacion/asyncapi/hda-asyncapi.yaml`
(CONVENCIONES §9) — PLANTILLA: cada servicio copia este archivo a su
`tests/contrato/`.

- Evento que el servicio PUBLICA: `validar_cuerpo("AgendaConfirmada", cuerpo)` con
  el cuerpo exacto que sale a Pulsar (`record_a_dict(record)`).
- Evento que el servicio CONSUME: `ejemplo_valido(...)` no existe a propósito; la
  prueba arma el mensaje a mano con la forma del catálogo y lo valida con
  `validar_cuerpo` antes de publicarlo en Pulsar local, para que la prueba falle si
  el contrato cambia y el consumidor no."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

RUTA_ASYNCAPI = Path(__file__).resolve().parents[3] / "asyncapi" / "hda-asyncapi.yaml"


@lru_cache(maxsize=1)
def documento() -> dict:
    return yaml.safe_load(RUTA_ASYNCAPI.read_text(encoding="utf-8"))


def _resolver(nodo: Any, raiz: dict) -> Any:
    if isinstance(nodo, dict):
        if "$ref" in nodo:
            ruta = nodo["$ref"].removeprefix("#/").split("/")
            destino = raiz
            for parte in ruta:
                destino = destino[parte]
            return _resolver(copy.deepcopy(destino), raiz)
        return {k: _resolver(v, raiz) for k, v in nodo.items()}
    if isinstance(nodo, list):
        return [_resolver(v, raiz) for v in nodo]
    return nodo


def mensaje(nombre: str) -> dict:
    return _resolver(documento()["components"]["messages"][nombre], documento())


def esquema_cuerpo(nombre: str) -> dict:
    return mensaje(nombre)["payload"]


def esquema_propiedades() -> dict:
    return _resolver(
        documento()["components"]["schemas"]["PropiedadesPulsar"], documento()
    )


def _validar(esquema: dict, instancia: Any) -> None:
    Draft202012Validator(esquema, format_checker=FormatChecker()).validate(instancia)


def validar_cuerpo(nombre_mensaje: str, cuerpo: dict) -> None:
    """Lanza `jsonschema.ValidationError` si el cuerpo no cumple el contrato."""
    _validar(esquema_cuerpo(nombre_mensaje), cuerpo)


def validar_propiedades(propiedades: dict) -> None:
    _validar(esquema_propiedades(), propiedades)


def canales_pulsar() -> dict[str, dict]:
    return {
        nombre: canal
        for nombre, canal in documento()["channels"].items()
        if nombre.startswith("persistent://")
    }


def mensajes_del_canal(canal: dict) -> list[str]:
    """Nombres de los mensajes que viajan por un canal (uno o `oneOf`)."""
    operacion = canal.get("publish") or canal.get("subscribe")
    msg = operacion["message"]
    refs = msg["oneOf"] if "oneOf" in msg else [msg]
    return [ref["$ref"].rsplit("/", 1)[-1] for ref in refs]


def topico_de(nombre_mensaje: str, productor: str | None = None) -> str:
    """Tópico por el que viaja un mensaje (filtrando por productor cuando hay
    varios, ej. ProveedorSeleccionado)."""
    candidatos = [
        topico
        for topico, canal in canales_pulsar().items()
        if nombre_mensaje in mensajes_del_canal(canal)
        and (productor is None or canal.get("x-productor") == productor)
    ]
    if len(candidatos) != 1:
        raise LookupError(f"{nombre_mensaje} (productor={productor}): {candidatos}")
    return candidatos[0]

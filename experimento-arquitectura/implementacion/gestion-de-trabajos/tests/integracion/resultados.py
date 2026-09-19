"""Registro de datos crudos por caso de prueba de DISP-02 — mismo patrón que
`proveedores/tests/resultados.py`: compara valor medido contra umbral y anota
cumple/no cumple de forma mecánica, sin ninguna síntesis global. La síntesis
(¿se valida o refuta la hipótesis de DISP-02 en conjunto?, ¿qué amenazas a
la validez aplican?) es responsabilidad exclusiva de `validador-hipotesis`
— este archivo solo produce los datos crudos que ese análisis necesita."""

import json
import pathlib
import time

RUTA_RESULTADOS = pathlib.Path(__file__).parent / "results" / "resultados_disp02.jsonl"


def reiniciar() -> None:
    RUTA_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_RESULTADOS.write_text("")


def registrar(
    caso: str, metrica: str, valor, umbral, cumple: bool, detalle: str = ""
) -> None:
    RUTA_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_RESULTADOS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "caso": caso,
                    "metrica": metrica,
                    "valor": valor,
                    "umbral": umbral,
                    "cumple": cumple,
                    "detalle": detalle,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

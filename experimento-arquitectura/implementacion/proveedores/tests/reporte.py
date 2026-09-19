"""Convierte tests/results/resultados_disp03.jsonl en una tabla legible.

Es un resumen MECÁNICO (valor medido vs. umbral, por caso) — el mismo tipo
de "datos crudos" que experimento-runner produce y le entrega a
validador-hipotesis. No emite un veredicto global; eso es tarea de ese
agente, no de este script."""

import json
import pathlib

RUTA = pathlib.Path(__file__).parent / "results" / "resultados_disp03.jsonl"


def main() -> None:
    if not RUTA.exists() or RUTA.stat().st_size == 0:
        print("No hay resultados todavía — corre 'pytest tests/' primero.")
        return

    filas = [json.loads(linea) for linea in RUTA.read_text().splitlines() if linea.strip()]

    ancho_caso = max(len(f["caso"]) for f in filas)
    ancho_metrica = max(len(f["metrica"]) for f in filas)

    print(
        f"{'caso':<{ancho_caso}}  {'métrica':<{ancho_metrica}}  {'valor':>10}  {'umbral':>10}  cumple"
    )
    print("-" * (ancho_caso + ancho_metrica + 40))
    for f in filas:
        marca = "SI" if f["cumple"] else "NO"
        print(
            f"{f['caso']:<{ancho_caso}}  {f['metrica']:<{ancho_metrica}}  "
            f"{f['valor']!s:>10}  {f['umbral']!s:>10}  {marca}"
        )

    total = len(filas)
    cumplidas = sum(1 for f in filas if f["cumple"])
    print("-" * (ancho_caso + ancho_metrica + 40))
    print(f"{cumplidas}/{total} verificaciones mecánicas cumplidas.")
    if cumplidas < total:
        print(
            "Hay verificaciones que no cumplieron su umbral — antes de sacar "
            "conclusiones, pásale este archivo a validador-hipotesis."
        )


if __name__ == "__main__":
    main()

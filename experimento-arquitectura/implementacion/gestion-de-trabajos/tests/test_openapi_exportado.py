"""El `openapi/openapi.json` versionado coincide con la API real (15-…md §14) —
PLANTILLA: cada servicio la copia. Sin esto, el job oasdiff del CI compararía un
archivo viejo y dejaría pasar un cambio que rompe. Si falla, regenerarlo con
`implementacion/scripts/exportar-openapi.sh <servicio>` y revisar el diff."""

import json
from pathlib import Path

from app.api.main import app

EXPORTADO = Path(__file__).resolve().parents[1] / "openapi" / "openapi.json"


def test_openapi_exportado_esta_al_dia():
    assert (
        EXPORTADO.exists()
    ), "falta openapi/openapi.json: correr scripts/exportar-openapi.sh"
    en_repo = json.loads(EXPORTADO.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(app.openapi()))
    assert (
        en_repo == actual
    ), "openapi.json desactualizado: correr scripts/exportar-openapi.sh"

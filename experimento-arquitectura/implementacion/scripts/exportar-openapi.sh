#!/usr/bin/env bash
# Exporta el OpenAPI de la API de un servicio a <servicio>/openapi/openapi.json
# (15-arquitectura-entrega-5.md §14). El job oasdiff del CI compara ese archivo
# contra el de main y falla si hay un cambio que rompe; la prueba
# tests/test_openapi_exportado.py de cada servicio falla si el archivo quedó
# desactualizado respecto al código. Correr después de cambiar un endpoint:
#
#   scripts/exportar-openapi.sh gestion-de-trabajos
#
# Requiere las dependencias del servicio instaladas (pip install -r requirements-dev.txt).

set -euo pipefail
SERVICIO="${1:?uso: $0 <carpeta-del-servicio>}"
MODULO="${2:-app.api.main}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

cd "${RAIZ}/${SERVICIO}"
mkdir -p openapi
python3 -c "
import json, sys
from importlib import import_module
app = import_module('${MODULO}').app
json.dump(app.openapi(), sys.stdout, indent=2, ensure_ascii=False, sort_keys=True)
print()
" > openapi/openapi.json
echo "OK: ${SERVICIO}/openapi/openapi.json"

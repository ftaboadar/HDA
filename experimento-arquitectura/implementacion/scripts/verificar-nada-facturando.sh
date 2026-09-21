#!/usr/bin/env bash
# Lista lo que puede estar facturando en el proyecto. Sale con código 1 si queda algo.
# El bucket de state (${PROJECT}-tfstate) no cuenta: cuesta centavos y hace falta para destruir.
#
# Uso:   PROJECT=<proyecto> ./verificar-nada-facturando.sh

# shellcheck source=comun.sh
source "$(dirname "$0")/comun.sh"
requiere gcloud

quedan=0
revisar() {
  local nombre="$1"
  shift
  local salida
  salida="$("$@" 2>/dev/null || true)"
  if [ -n "$salida" ]; then
    echo "✗ ${nombre}:"
    while IFS= read -r linea; do echo "    ${linea}"; done <<<"$salida"
    quedan=1
  else
    echo "✓ ${nombre}: nada"
  fi
}

log "Recursos que facturan en ${PROJECT}"
revisar "Cloud Run" gcloud run services list --project "$PROJECT" --format="value(metadata.name)"
revisar "Cloud SQL" gcloud sql instances list --project "$PROJECT" --format="value(name)"
revisar "Compute Engine (VMs)" gcloud compute instances list --project "$PROJECT" --format="value(name)"
revisar "Pub/Sub (tópicos)" gcloud pubsub topics list --project "$PROJECT" --format="value(name)"
revisar "Artifact Registry" gcloud artifacts repositories list --project "$PROJECT" --format="value(name)"
revisar "Buckets (sin el de state)" bash -c "gcloud storage buckets list --project '$PROJECT' --format='value(name)' | grep -vx '${BUCKET_STATE}' || true"

if [ "$quedan" = 1 ]; then
  echo
  echo "Queda algo facturando. Vuelve a correr destruir-todo.sh o bórralo desde la consola."
  exit 1
fi
echo
echo "No queda nada facturando en ${PROJECT}."

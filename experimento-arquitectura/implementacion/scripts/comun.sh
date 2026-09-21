#!/usr/bin/env bash
# shellcheck disable=SC2034  # variables usadas por los scripts que cargan este archivo
# Funciones y variables compartidas por desplegar-todo.sh, destruir-todo.sh y
# verificar-nada-facturando.sh. No se ejecuta solo: se carga con `source`.
#
# Cambiar de proyecto GCP = cambiar PROJECT. Nada más viaja entre proyectos:
# cada proyecto tiene su propio bucket de state (${PROJECT}-tfstate).

set -euo pipefail

: "${PROJECT:?Define PROJECT=<id del proyecto GCP>, ej. PROJECT=hogaralpes ./desplegar-todo.sh}"
REGION="${REGION:-southamerica-east1}"
BUCKET_STATE="${BUCKET_STATE:-${PROJECT}-tfstate}"
# Cuota típica de un proyecto nuevo: 20 vCPU por región. Gestión de Trabajos usa 2 vCPU por instancia.
GT_MAX_INSTANCIAS="${GT_MAX_INSTANCIAS:-9}"

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMPL="$(cd "$SCRIPTS_DIR/.." && pwd)"
AR="${REGION}-docker.pkg.dev/${PROJECT}"
VARS_BASE=(-var "project_id=${PROJECT}" -var "region=${REGION}")

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33m[aviso] %s\033[0m\n' "$*"; }

requiere() {
  local faltan=0
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Falta el comando: $cmd"; faltan=1; }
  done
  [ "$faltan" = 0 ] || exit 1
}

bucket_state_existe() {
  gcloud storage buckets describe "gs://${BUCKET_STATE}" --project "$PROJECT" >/dev/null 2>&1
}

asegurar_bucket_state() {
  if ! bucket_state_existe; then
    log "Creando el bucket de state gs://${BUCKET_STATE} (versionado)"
    gcloud storage buckets create "gs://${BUCKET_STATE}" --project "$PROJECT" \
      --location "$REGION" --uniform-bucket-level-access
    gcloud storage buckets update "gs://${BUCKET_STATE}" --versioning
  fi
}

# tf_init <stack>: backend GCS con prefix = ruta del stack relativa a implementacion/.
tf_init() {
  (cd "$IMPL/$1" && terraform init -input=false -reconfigure \
    -backend-config="bucket=${BUCKET_STATE}" -backend-config="prefix=$1" >/dev/null)
}

# tf <stack> <subcomando terraform> [args...]
tf() {
  local stack="$1"
  shift
  (cd "$IMPL/$stack" && terraform "$@")
}

# Variables extra que algunos stacks exigen también al destruir (su validación corre siempre).
vars_extra() {
  case "$1" in
    gestion-de-trabajos/infra) echo "-var max_instance_count=${GT_MAX_INSTANCIAS}" ;;
    *) echo "" ;;
  esac
}

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

# region_de_stack <stack>: región final de despliegue de cada stack (Regla 3: reparte la cuota de
# 20 vCPU/región entre regiones). Fuente única de verdad: usada tanto para el bootstrap de imágenes
# (Cloud Build + Artifact Registry) como para el `apply` final del servicio. Si difieren, Terraform
# destruye y recrea el repositorio de Artifact Registry en la región nueva (borrando la imagen ya
# subida) y el Cloud Run del paso final falla con "Image ... not found" — bug real encontrado
# desplegando contra project-b68c032a-000b-4601-8bd (2026-09-22).
region_de_stack() {
  case "$1" in
    gestion-de-trabajos/infra | proveedores/infra | scoring/infra | marketplace/infra) echo "us-east1" ;;
    siniestros/infra) echo "us-central1" ;;
    *) echo "$REGION" ;;
  esac
}

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

# Variables extra que algunos stacks exigen también al destruir (su validación corre siempre,
# incluso para `terraform destroy` -- Terraform valida TODAS las variables sin default antes de
# poder construir el plan de destrucción, aunque el valor en sí ya no vaya a usarse para nada).
vars_extra() {
  case "$1" in
    gestion-de-trabajos/infra) echo "-var max_instance_count=${GT_MAX_INSTANCIAS}" ;;
    # bff/infra no tiene default para las 8 *_url (variables.tf) -- en un despliegue real vienen de
    # `output -raw api_url` de los otros stacks (ver desplegar-todo.sh). Para destruir no importa el
    # valor real (identifica recursos por dirección de Terraform, no por el contenido del env var), y
    # además esos stacks pueden ya no existir (ORDEN destruye bff/infra primero) -- placeholder fijo.
    # Bug real encontrado 2026-09-22: sin esto, `terraform destroy` de bff/infra fallaba con "No
    # value for required variable" y dejaba el stack completo (Cloud Run + Cloud SQL si tuviera)
    # facturando en silencio.
    bff/infra) echo "-var gestion_trabajos_url=http://destruido.local -var proveedores_url=http://destruido.local -var pagos_url=http://destruido.local -var siniestros_url=http://destruido.local -var marketplace_url=http://destruido.local -var suscripciones_url=http://destruido.local -var scoring_url=http://destruido.local -var reputacion_url=http://destruido.local" ;;
    *) echo "" ;;
  esac
}

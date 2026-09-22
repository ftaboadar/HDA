#!/usr/bin/env bash
# Apaga TODO lo desplegado por desplegar-todo.sh en el proyecto, en orden inverso, y verifica que no
# quede nada facturando. Funciona desde cualquier máquina con acceso al proyecto, porque el state
# vive en gs://${PROJECT}-tfstate (no en la carpeta de quien desplegó).
# El destroy borra también las bases de Cloud SQL y sus datos: guarda antes la evidencia que necesites.
#
# Uso:   PROJECT=<proyecto> ./destruir-todo.sh
# Opcional: BORRAR_BUCKET_STATE=1 (al final borra también el bucket de state, solo si todo salió bien).

# shellcheck source=comun.sh
source "$(dirname "$0")/comun.sh"
requiere gcloud terraform

if ! bucket_state_existe; then
  aviso "No existe gs://${BUCKET_STATE}: no hay state remoto que destruir en ${PROJECT}."
  aviso "Si alguien desplegó antes del state remoto, destruye desde su carpeta local o borra a mano."
  exec "$SCRIPTS_DIR/verificar-nada-facturando.sh"
fi

# Orden inverso al despliegue (ver desplegar-todo.sh). gestion-de-trabajos y proveedores antes
# que pulsar-infra/gcp (dependen de su IP vía Direct VPC egress).
#
# [2026-09-22] bff/infra, marketplace/infra, siniestros/infra, suscripciones/infra y scoring/infra
# faltaban de este ORDEN (el archivo se quedó con la lista de stacks previa a la Entrega 5) — un
# `destruir-todo.sh` real los habría dejado desplegados y facturando en silencio, porque
# `verificar-nada-facturando.sh` solo lista lo que YA no está en este ORDEN, no compara contra
# `desplegar-todo.sh`. Encontrado corriendo el ciclo completo de verificación de esta sesión contra
# project-b68c032a-000b-4601-8bd, antes de ejecutar el destroy real.
ORDEN=(
  observabilidad
  bff/infra
  siniestros/infra
  proveedores/infra
  reputacion/infra
  marketplace/infra
  scoring/infra
  suscripciones/infra
  pagos/infra
  gestion-de-trabajos/infra
  mocks-crm/infra
  mocks-pagos/infra
  pulsar-infra/gcp
  k6/infra
)
fallidos=()
for stack in "${ORDEN[@]}"; do
  log "Destruyendo ${stack}"
  tf_init "$stack"
  # shellcheck disable=SC2046
  if ! tf "$stack" destroy -auto-approve -input=false "${VARS_BASE[@]}" $(vars_extra "$stack"); then
    aviso "Falló el destroy de ${stack}. Ver 'Notas del destroy' en DESPLIEGUE-GCP-INTEGRAL.md"
    fallidos+=("$stack")
  fi
done

# Bucket que crea Cloud Build solo (no está en Terraform) con el código de cada `gcloud builds submit`.
log "Borrando gs://${PROJECT}_cloudbuild"
gcloud storage rm -r "gs://${PROJECT}_cloudbuild" --quiet 2>/dev/null || aviso "No existía gs://${PROJECT}_cloudbuild"

if [ "${#fallidos[@]}" -gt 0 ]; then
  echo
  echo "Stacks con destroy fallido: ${fallidos[*]}"
  echo "Corrige y vuelve a correr este script (es idempotente)."
  "$SCRIPTS_DIR/verificar-nada-facturando.sh" || true
  exit 1
fi

if [ "${BORRAR_BUCKET_STATE:-0}" = 1 ]; then
  log "Borrando el bucket de state gs://${BUCKET_STATE}"
  gcloud storage rm -r "gs://${BUCKET_STATE}" --quiet
fi

"$SCRIPTS_DIR/verificar-nada-facturando.sh"
echo "Recuerda: actualizar ESTADO-IMPLEMENTACION.md §1 (ya no hay nada desplegado en ${PROJECT})."

#!/usr/bin/env bash
# Despliega en GCP todo lo que ESTADO-IMPLEMENTACION.md marca como desplegable, en el mismo
# orden y con las mismas variables de la "Receta vigente" de DESPLIEGUE-GCP-INTEGRAL.md
# (probada en hogaralpes): imágenes → Pulsar (+ namespaces) → mocks → servicios → Grafana.
#
# Uso:   PROJECT=<proyecto> ./desplegar-todo.sh
# Opcional: REGION (default southamerica-east1), GT_MAX_INSTANCIAS (default 9),
#           SALTAR_IMAGENES=1 (no reconstruye imágenes que ya existen).
# Prerrequisitos: facturación activa, `gcloud auth login`, `gcloud auth application-default login`,
#                 Terraform >= 1.5.
# Es idempotente: si falla a mitad, se puede volver a correr.

# shellcheck source=comun.sh
source "$(dirname "$0")/comun.sh"
requiere gcloud terraform

log "Proyecto ${PROJECT} · región ${REGION} · state en gs://${BUCKET_STATE}"
gcloud services enable cloudbuild.googleapis.com storage.googleapis.com compute.googleapis.com \
  iap.googleapis.com --project "$PROJECT"
asegurar_bucket_state

# 0) Repositorio de Artifact Registry de cada servicio + su imagen. Cloud Run falla al crearse si
#    la imagen no existe, por eso va antes del apply completo.
#    stack | repositorio | imagen | carpeta con el Dockerfile
IMAGENES=(
  "mocks-pagos/infra|mocks-pagos-poc-hda|hda-mocks-pagos|mocks-pagos"
  "mocks-crm/infra|mocks-crm-poc-hda|hda-mocks-crm|mocks-crm"
  "pagos/infra|pagos-poc-hda|hda-pagos|pagos"
  "gestion-de-trabajos/infra|gestion-trabajos-poc-hda|hda-gestion-de-trabajos|gestion-de-trabajos"
  "reputacion/infra|reputacion-poc-hda|hda-reputacion|reputacion"
  "proveedores/infra|disp03-poc-hda|hda-disp03|proveedores" # prefijo disp03-poc: nombre histórico (A20)

  "marketplace/infra|marketplace-poc-hda|hda-marketplace|marketplace"
  "siniestros/infra|siniestros-poc-hda|hda-siniestros|siniestros"
  "suscripciones/infra|suscripciones-poc-hda|hda-suscripciones|suscripciones"
  "scoring/infra|scoring-poc-hda|hda-scoring|scoring"
  "bff/infra|bff-poc-hda|hda-bff|bff"

)
for fila in "${IMAGENES[@]}"; do
  IFS='|' read -r stack repo imagen carpeta <<<"$fila"
  region_stack="$(region_de_stack "$stack")"
  ar_stack="${region_stack}-docker.pkg.dev/${PROJECT}"
  log "Imagen ${imagen} (región ${region_stack})"
  tf_init "$stack"
  # shellcheck disable=SC2046
  tf "$stack" apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=${region_stack}" $(vars_extra "$stack") \
    -target=google_artifact_registry_repository.hda
  if [ "${SALTAR_IMAGENES:-0}" = 1 ] &&
    gcloud artifacts docker images describe "${ar_stack}/${repo}/${imagen}:latest" --project "$PROJECT" >/dev/null 2>&1; then
    aviso "SALTAR_IMAGENES=1 y la imagen ya existe: no se reconstruye"
  else
    gcloud builds submit "$IMPL/$carpeta" --tag "${ar_stack}/${repo}/${imagen}:latest" --project "$PROJECT" --quiet
  fi
done

# 1) Pulsar en VM. El startup script de la VM crea tenant y namespaces y deja una marca al terminar.
log "Pulsar (VM de Compute Engine)"
tf_init pulsar-infra/gcp
tf pulsar-infra/gcp apply -auto-approve -input=false "${VARS_BASE[@]}"
PULSAR_IP="$(tf pulsar-infra/gcp output -raw ip_privada)"
VM="$(tf pulsar-infra/gcp output -raw vm_name)"
ZONA="$(tf pulsar-infra/gcp output -raw vm_zone)"

log "Esperando a que Pulsar y sus namespaces estén listos (hasta 15 min)"
listo=0
for _ in $(seq 1 45); do
  if gcloud compute ssh "$VM" --zone "$ZONA" --tunnel-through-iap --project "$PROJECT" --quiet \
    --command "test -f /opt/pulsar-infra/namespaces-listos" >/dev/null 2>&1; then
    listo=1
    break
  fi
  sleep 20
done
if [ "$listo" != 1 ]; then
  echo "Pulsar no quedó listo. Revisa la VM:"
  echo "  gcloud compute ssh $VM --zone $ZONA --tunnel-through-iap --project $PROJECT --command 'sudo journalctl -u google-startup-scripts --no-pager | tail -50'"
  exit 1
fi

# 2) Mocks de pagos y del CRM.
for stack in mocks-pagos/infra mocks-crm/infra; do
  log "Stack ${stack}"
  tf "$stack" apply -auto-approve -input=false "${VARS_BASE[@]}"
done
STRIPE="$(tf mocks-pagos/infra output -raw mock_stripe_url)"
MP="$(tf mocks-pagos/infra output -raw mock_mercadopago_url)"
CRM="$(tf mocks-crm/infra output -raw mock_crm_url)"

# 3) Servicios de negocio.
log "Stack pagos/infra"
tf pagos/infra apply -auto-approve -input=false "${VARS_BASE[@]}" \
  -var "stripe_mock_url=${STRIPE}" -var "mercadopago_mock_url=${MP}"

log "Stack gestion-de-trabajos/infra"
tf gestion-de-trabajos/infra apply -auto-approve -input=false -var "project_id=${PROJECT}" \
  -var "region=$(region_de_stack gestion-de-trabajos/infra)" \
  -var "max_instance_count=${GT_MAX_INSTANCIAS}" -var "pulsar_service_url=pulsar://${PULSAR_IP}:6650" \
  -var "stripe_mock_url=${STRIPE}" -var "mercadopago_mock_url=${MP}" -var "crm_mock_url=${CRM}"

for stack in suscripciones/infra; do
  log "Stack ${stack}"
  tf "$stack" apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=$(region_de_stack "$stack")"
done
for stack in scoring/infra marketplace/infra; do
  log "Stack ${stack}"
  tf "$stack" apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=$(region_de_stack "$stack")"
done

for stack in reputacion/infra; do
  log "Stack ${stack}"
  tf "$stack" apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=$(region_de_stack "$stack")"
done
for stack in proveedores/infra; do
  log "Stack ${stack}"
  tf "$stack" apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=$(region_de_stack "$stack")" \
    -var "pulsar_service_url=pulsar://${PULSAR_IP}:6650"
done
# Siniestros (Multi-Region patch)
if [ -d "siniestros/infra" ]; then
  log "Stack siniestros/infra"
  tf "siniestros/infra" apply -auto-approve -input=false -var "project_id=${PROJECT}" \
    -var "region=$(region_de_stack siniestros/infra)"
fi


# BFF: va después de TODOS los servicios de negocio porque necesita sus URLs ya
# conocidas (api_url de cada stack) para enrutar — ver bff/app/api/main.py SERVICE_URLS.
log "Stack bff/infra"
tf bff/infra apply -auto-approve -input=false -var "project_id=${PROJECT}" -var "region=$(region_de_stack bff/infra)" \
  -var "gestion_trabajos_url=$(tf gestion-de-trabajos/infra output -raw api_url)" \
  -var "proveedores_url=$(tf proveedores/infra output -raw api_url)" \
  -var "pagos_url=$(tf pagos/infra output -raw api_url)" \
  -var "siniestros_url=$(tf siniestros/infra output -raw api_url)" \
  -var "marketplace_url=$(tf marketplace/infra output -raw api_url)" \
  -var "suscripciones_url=$(tf suscripciones/infra output -raw api_url)" \
  -var "scoring_url=$(tf scoring/infra output -raw api_url)" \
  -var "reputacion_url=$(tf reputacion/infra output -raw api_url)"

# 4) Grafana al final (el dashboard necesita servicios reales que graficar).
log "Stack observabilidad"
tf_init observabilidad
tf observabilidad apply -auto-approve -input=false "${VARS_BASE[@]}"

log "Listo. URLs de los servicios (pégalas en postman/HdA-GCP.postman_environment.json):"
echo "== Servicios en southamerica-east1 (Pagos, Reputación, Mocks, Grafana) =="
gcloud run services list --region "southamerica-east1" --project "$PROJECT" --format="table(metadata.name,status.url)"
echo "== Servicios en us-central1 (Siniestros) =="
gcloud run services list --region "us-central1" --project "$PROJECT" --format="table(metadata.name,status.url)"
echo "== Servicios en us-east1 (Gestión de Trabajos, Proveedores, etc) =="
gcloud run services list --region "us-east1" --project "$PROJECT" --format="table(metadata.name,status.url)"

echo
echo "Grafana: $(tf observabilidad output -raw grafana_url)  (usuario admin; contraseña:"
echo "  gcloud secrets versions access latest --secret=$(tf observabilidad output -raw grafana_admin_password_secret) --project ${PROJECT})"
echo
echo "Recuerda: actualizar ESTADO-IMPLEMENTACION.md §1 (qué quedó desplegado y dónde)."

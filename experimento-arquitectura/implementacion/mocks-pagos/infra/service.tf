# Dos mocks HTTP sin estado (sin Cloud SQL) sobre la MISMA imagen — igual
# que DISP-03/infra/mocks.tf hace con policia/rues/certificadora: un solo
# Dockerfile, distinto módulo FastAPI arrancado por `command`/`args` (ver
# ../docker-compose.yml para el comando uvicorn exacto de cada uno).
#
# container_port = 8000, no el default 8080 del módulo: el Dockerfile de
# este servicio expone 8000 (ver ../Dockerfile) y así lo arranca
# docker-compose.yml localmente — se respeta ese contrato en vez de
# forzar los mocks a escuchar en un puerto distinto al que ya usan en
# local, para no introducir una diferencia entre entornos que nadie pidió.

module "mock_stripe" {
  source = "../../infra-modules/cloud-run-service"

  project_id   = var.project_id
  region       = var.region
  entorno      = var.entorno
  service_name = "mock-stripe"

  image          = local.imagen_app
  command        = ["uvicorn"]
  args           = ["app.stripe_mock:app", "--host", "0.0.0.0", "--port", "8000"]
  container_port = 8000

  min_instance_count = 0
  max_instance_count = 5

  depends_on = [google_project_service.apis]
}

module "mock_mercadopago" {
  source = "../../infra-modules/cloud-run-service"

  project_id   = var.project_id
  region       = var.region
  entorno      = var.entorno
  service_name = "mock-mercadopago"

  image          = local.imagen_app
  command        = ["uvicorn"]
  args           = ["app.mercadopago_mock:app", "--host", "0.0.0.0", "--port", "8000"]
  container_port = 8000

  min_instance_count = 0
  max_instance_count = 5

  depends_on = [google_project_service.apis]
}

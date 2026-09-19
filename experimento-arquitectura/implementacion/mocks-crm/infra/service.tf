# Doble del CRM SaaS "Gestión de Agentes" (DISP-02): responde 429 +
# Retry-After cuando se supera `limite_rps`.
#
# min = max = 1 instancia, a propósito: la ventana deslizante del rate
# limiting y el `limite_rps` configurado vía POST /_control/config viven en
# memoria del proceso (ver ../app/main.py). Con más de una instancia, cada
# réplica tendría su propio contador y el límite efectivo se multiplicaría
# por el número de réplicas, invalidando la prueba de throttling. Con min=1,
# además, la configuración que haga la prueba no se pierde en un cold start.
#
# container_port = 8000: el mismo puerto que usa el Dockerfile y
# docker-compose.disp02.yml en local.

module "mock_crm" {
  source = "../../infra-modules/cloud-run-service"

  project_id   = var.project_id
  region       = var.region
  entorno      = var.entorno
  service_name = "mock-crm"

  image          = local.imagen_app
  command        = ["uvicorn"]
  args           = ["app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  container_port = 8000

  min_instance_count = 1
  max_instance_count = 1

  depends_on = [google_project_service.apis]
}

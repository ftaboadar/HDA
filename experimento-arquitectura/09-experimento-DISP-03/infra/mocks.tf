# Despliegue de los 3 dobles de sistemas externos a Cloud Run — necesarios
# para poder correr los mismos 7 casos de prueba (tests/test_escenarios_disp03.py)
# contra el entorno real de GCP, no solo contra docker-compose local. No
# exponen datos reales, solo simulan comportamiento (ver app/mocks/main.py),
# por eso son públicos sin restricción adicional dentro del alcance de PoC.

resource "google_cloud_run_v2_service" "mock" {
  for_each = toset(["policia", "rues", "certificadora"])

  name     = "${var.entorno}-mock-${each.value}"
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
    containers {
      image   = local.imagen_app
      command = ["uvicorn"]
      args    = ["app.mocks.main:app", "--host", "0.0.0.0", "--port", "8080"]

      env {
        name  = "MOCK_NAME"
        value = each.value
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "publico_mocks" {
  for_each = google_cloud_run_v2_service.mock

  name     = each.value.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

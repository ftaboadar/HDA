resource "google_artifact_registry_repository" "hda" {
  location      = var.region
  repository_id = "${var.entorno}-hda"
  format        = "DOCKER"
  description   = "Imagen de Gestión de Trabajos (API + módulo ACL de Pagos) — ver ../Dockerfile"
  depends_on    = [google_project_service.apis]
}

locals {
  imagen_app = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.hda.repository_id}/hda-gestion-de-trabajos:latest"
}

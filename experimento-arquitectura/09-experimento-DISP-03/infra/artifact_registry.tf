resource "google_artifact_registry_repository" "hda" {
  location      = var.region
  repository_id = "${var.entorno}-hda"
  format        = "DOCKER"
  description   = "Imágenes del experimento DISP-03 (api, worker, mocks) — una sola imagen compartida, ver ../Dockerfile"
  depends_on    = [google_project_service.apis]
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.hda.name
}
output "imagen_app" {
  value = local.imagen_app
}

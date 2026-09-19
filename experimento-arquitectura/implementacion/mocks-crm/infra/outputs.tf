output "mock_crm_url" {
  value = module.mock_crm.uri
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.hda.repository_id
}

output "imagen_app" {
  value = local.imagen_app
}

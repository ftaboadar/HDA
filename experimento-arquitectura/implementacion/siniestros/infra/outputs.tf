output "api_url" {
  value = module.api.uri
}

output "sql_connection_name" {
  value = google_sql_database_instance.siniestros.connection_name
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.hda.repository_id
}

output "imagen_app" {
  value = local.imagen_app
}

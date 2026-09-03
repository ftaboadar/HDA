output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "worker_url" {
  value = google_cloud_run_v2_service.worker.uri
}

output "mock_policia_url" {
  value = google_cloud_run_v2_service.mock["policia"].uri
}

output "mock_rues_url" {
  value = google_cloud_run_v2_service.mock["rues"].uri
}

output "mock_certificadora_url" {
  value = google_cloud_run_v2_service.mock["certificadora"].uri
}

output "topic_solicitudes" {
  value = google_pubsub_topic.solicitudes.name
}

output "topic_fallidas_dlq" {
  value = google_pubsub_topic.fallidas.name
}

output "sql_connection_name" {
  value = google_sql_database_instance.verificacion.connection_name
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.hda.repository_id
}

output "grafana_url" {
  value = google_cloud_run_v2_service.grafana.uri
}

output "grafana_admin_user" {
  value = "admin"
}

output "grafana_admin_password_secret" {
  description = "Secreto de Secret Manager con la contraseña real — no expuesta como output en texto plano"
  value       = google_secret_manager_secret.grafana_admin_password.secret_id
}

output "grafana_provisioning_bucket" {
  value = google_storage_bucket.grafana_provisioning.name
}

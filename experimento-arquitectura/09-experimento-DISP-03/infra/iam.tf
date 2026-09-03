resource "google_service_account" "runtime" {
  account_id   = "${var.entorno}-runtime"
  display_name = "Runtime del experimento DISP-03 (API/Worker)"
}

resource "google_service_account" "invocador_pubsub" {
  account_id   = "${var.entorno}-pubsub-invoker"
  display_name = "Invocador de Pub/Sub hacia Cloud Run (push)"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invoca_worker" {
  name     = google_cloud_run_v2_service.worker.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.invocador_pubsub.email}"
}

resource "google_project_iam_member" "runtime_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.editor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_lee_db_url" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

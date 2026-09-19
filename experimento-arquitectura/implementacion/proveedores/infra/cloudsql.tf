# Equivalente GCP del Postgres local (ver ../docker-compose.yml).
# Nota de alcance PoC: IP pública + red autorizada abierta. En un entorno
# real se reemplazaría por IP privada + conector VPC — fuera de alcance de
# este experimento de resiliencia (ver plan.md, sección 5.2 "Fuera de
# alcance").

resource "google_sql_database_instance" "verificacion" {
  name             = "${var.entorno}-verificacion"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = var.sql_tier

    ip_configuration {
      ipv4_enabled = true

      authorized_networks {
        name  = "abierto-solo-para-poc"
        value = "0.0.0.0/0"
      }
    }
  }

  deletion_protection = false
  depends_on          = [google_project_service.apis]
}

resource "google_sql_database" "verificacion_db" {
  name     = "verificacion"
  instance = google_sql_database_instance.verificacion.name
}

resource "random_password" "db_password" {
  length  = 20
  special = false
}

resource "google_sql_user" "hda" {
  name     = "hda"
  instance = google_sql_database_instance.verificacion.name
  password = random_password.db_password.result
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = "${var.entorno}-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = "postgresql+psycopg2://hda:${random_password.db_password.result}@/verificacion?host=/cloudsql/${google_sql_database_instance.verificacion.connection_name}"
}

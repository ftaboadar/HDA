output "ip_publica" {
  description = "IP externa efímera de la VM — solo para administración/debug manual (ver var.admin_source_ranges); NO usar para pulsar_service_url de los microservicios."
  value       = google_compute_instance.pulsar.network_interface[0].access_config[0].nat_ip
}

output "ip_privada" {
  description = "IP interna de la VM, dentro de la subred \"default\" — esta es la que va en pulsar_service_url (pulsar://<ip_privada>:6650) de gestion-de-trabajos/reputacion, alcanzable vía Direct VPC egress."
  value       = google_compute_instance.pulsar.network_interface[0].network_ip
}

output "vm_name" {
  value = google_compute_instance.pulsar.name
}

output "vm_zone" {
  value = local.zone
}

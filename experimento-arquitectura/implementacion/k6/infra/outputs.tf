output "vm_name" {
  value = google_compute_instance.k6_runner.name
}

output "vm_zone" {
  value = local.zone
}

output "ssh_iap_command" {
  description = "Comando para entrar a la VM y correr la prueba (ver ../README.md para las variables GESTION_TRABAJOS_URL/DISP03_URL exactas del momento)"
  value       = "gcloud compute ssh ${google_compute_instance.k6_runner.name} --zone=${local.zone} --project=${var.project_id} --tunnel-through-iap"
}

output "scp_resultados_command" {
  description = "Comando para traer los resultados de vuelta, después de correr la prueba en la VM"
  value       = "gcloud compute scp --zone=${local.zone} --project=${var.project_id} --tunnel-through-iap ${google_compute_instance.k6_runner.name}:/opt/k6-runner/results/*.json ../results/ --recurse"
}

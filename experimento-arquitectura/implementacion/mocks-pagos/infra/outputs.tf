output "mock_stripe_url" {
  value = module.mock_stripe.uri
}

output "mock_mercadopago_url" {
  value = module.mock_mercadopago.uri
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.hda.repository_id
}

output "imagen_app" {
  value = local.imagen_app
}

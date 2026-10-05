output "api_url" {
  value = local.api_url
}

output "admin_url" {
  value = local.admin_url
}

output "image_repository" {
  description = "Dove la pipeline carica le immagini."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "workload_identity_provider" {
  description = "Da copiare nella variabile GitHub GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Da copiare nella variabile GitHub GCP_DEPLOYER."
  value       = google_service_account.deployer.email
}

output "secrets_to_fill" {
  description = "Segreti da riempire con: gcloud secrets versions add <nome> --data-file=-"
  value       = sort([for s in google_secret_manager_secret.app : s.secret_id])
}

output "media_bucket" {
  value = cloudflare_r2_bucket.media.name
}

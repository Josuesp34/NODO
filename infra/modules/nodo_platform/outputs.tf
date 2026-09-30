output "artifact_repository" {
  description = "Ruta regional del registro de contenedores."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "database_private_ip" {
  description = "IP privada; sensible para reducir exposición accidental en logs."
  value       = google_sql_database_instance.postgres.private_ip_address
  sensitive   = true
}

output "database_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "fit_bucket" {
  value = google_storage_bucket.fit.name
}

output "exports_bucket" {
  value = google_storage_bucket.exports.name
}

output "logical_backups_bucket" {
  value = google_storage_bucket.logical_backups.name
}

output "github_workload_identity_provider" {
  description = "Valor para GCP_WORKLOAD_IDENTITY_PROVIDER en GitHub Environment."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_deploy_service_account" {
  description = "Valor para GCP_DEPLOY_SERVICE_ACCOUNT en GitHub Environment."
  value       = google_service_account.github_deploy.email
}

output "api_uri" {
  value = var.deploy_workloads ? google_cloud_run_v2_service.api[0].uri : null
}

output "pwa_uri" {
  value = var.deploy_workloads ? google_cloud_run_v2_service.pwa[0].uri : null
}

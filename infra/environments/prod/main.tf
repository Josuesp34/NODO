module "nodo" {
  source = "../../modules/nodo_platform"

  providers = {
    google      = google
    google-beta = google-beta
  }

  project_id         = var.project_id
  environment        = "prod"
  region             = var.region
  database_tier      = var.database_tier
  bucket_name_prefix = var.bucket_name_prefix
  github_repository  = var.github_repository

  deletion_protection                 = true
  api_min_instances                   = 1
  pwa_min_instances                   = 1
  billing_account_id                  = var.billing_account_id
  monthly_budget_units                = var.monthly_budget_units
  monitoring_notification_channel_ids = var.monitoring_notification_channel_ids
  enable_monitoring_alerts            = var.enable_monitoring_alerts

  deploy_workloads = var.deploy_workloads
  enable_worker    = var.enable_worker
  api_image        = var.api_image
  pwa_image        = var.pwa_image

  api_secret_bindings       = var.api_secret_bindings
  pwa_secret_bindings       = var.pwa_secret_bindings
  worker_secret_bindings    = var.worker_secret_bindings
  migration_secret_bindings = var.migration_secret_bindings

  api_env                 = var.api_env
  pwa_env                 = var.pwa_env
  worker_env              = var.worker_env
  artifact_reader_members = var.artifact_reader_members
}

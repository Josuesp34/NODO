locals {
  resource_prefix = "${var.name_prefix}-${var.environment}"
  labels = merge(var.labels, {
    project     = "nodo"
    environment = var.environment
    managed-by  = "terraform"
  })

  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])

  runtime_service_accounts = {
    api       = google_service_account.api.email
    pwa       = google_service_account.pwa.email
    worker    = google_service_account.worker.email
    migration = google_service_account.migration.email
  }

  secret_bindings_by_service = {
    api       = var.api_secret_bindings
    pwa       = var.pwa_secret_bindings
    worker    = var.worker_secret_bindings
    migration = var.migration_secret_bindings
  }

  secret_access_pairs = {
    for item in flatten([
      for service_name, bindings in local.secret_bindings_by_service : [
        for _, binding in bindings : {
          key          = "${service_name}:${binding.secret_id}"
          service_name = service_name
          secret_id    = binding.secret_id
        }
      ]
    ]) : item.key => item
  }

  deploy_ref_condition = join(" || ", [
    for ref in sort(tolist(var.github_deploy_refs)) : "assertion.ref == '${ref}'"
  ])
}

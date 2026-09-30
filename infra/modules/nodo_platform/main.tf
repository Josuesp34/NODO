resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "main" {
  project                 = var.project_id
  name                    = "${local.resource_prefix}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "cloud_run" {
  project                  = var.project_id
  name                     = "${local.resource_prefix}-run"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = var.network_cidr
  private_ip_google_access = true
}

resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "${local.resource_prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_prefix_length
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_artifact_registry_repository" "containers" {
  project       = var.project_id
  location      = var.region
  repository_id = "${local.resource_prefix}-containers"
  description   = "Imágenes inmutables de NODO ${var.environment}"
  format        = "DOCKER"
  labels        = local.labels

  docker_config {
    immutable_tags = true
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "fit" {
  project                     = var.project_id
  name                        = "${var.bucket_name_prefix}-${var.environment}-fit"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  # User erasure removes every generation; soft delete would secretly retain PII.
  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    condition {
      age            = var.fit_retention_days
      matches_prefix = ["fit/"]
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age            = var.export_retention_days
      matches_prefix = ["export/"]
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "exports" {
  project                     = var.project_id
  name                        = "${var.bucket_name_prefix}-${var.environment}-exports"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    condition {
      age = var.export_retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "logical_backups" {
  project                     = var.project_id
  name                        = "${var.bucket_name_prefix}-${var.environment}-logical-backups"
  location                    = var.region
  storage_class               = "NEARLINE"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  # Recovery copies have a separate, disclosed retention and erasure replay policy.
  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  lifecycle_rule {
    condition {
      age = var.logical_backup_retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "runtime" {
  for_each = var.managed_secret_ids

  project   = var.project_id
  secret_id = "${local.resource_prefix}-${each.value}"
  labels    = local.labels

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database_instance" "postgres" {
  project             = var.project_id
  name                = "${local.resource_prefix}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.database_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.database_disk_size_gb
    disk_autoresize   = true
    user_labels       = local.labels

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = var.database_backup_retained_count
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.main.id
      enable_private_path_for_google_cloud_services = true
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
      record_client_address   = false
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    database_flags {
      name  = "cloudsql.enable_pg_cron"
      value = "on"
    }

    maintenance_window {
      day          = 7
      hour         = 6
      update_track = "stable"
    }
  }

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_services,
  ]
}

resource "google_sql_database" "nodo" {
  project  = var.project_id
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-${var.environment}-api"
  display_name = "NODO ${var.environment} API"
}

resource "google_service_account" "pwa" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-${var.environment}-pwa"
  display_name = "NODO ${var.environment} PWA BFF"
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-${var.environment}-worker"
  display_name = "NODO ${var.environment} worker"
}

resource "google_service_account" "migration" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-${var.environment}-migrate"
  display_name = "NODO ${var.environment} migration job"
}

resource "google_project_iam_member" "runtime_log_writer" {
  for_each = local.runtime_service_accounts

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "runtime_metric_writer" {
  for_each = local.runtime_service_accounts

  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "database_client" {
  for_each = toset(["api", "worker", "migration"])

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.runtime_service_accounts[each.value]}"
}

resource "google_project_iam_member" "database_instance_user" {
  for_each = toset(["api", "worker", "migration"])

  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${local.runtime_service_accounts[each.value]}"
}

resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each = local.secret_access_pairs

  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.runtime_service_accounts[each.value.service_name]}"
}

resource "google_storage_bucket_iam_member" "api_fit" {
  bucket = google_storage_bucket.fit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "worker_fit" {
  bucket = google_storage_bucket.fit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_storage_bucket_iam_member" "api_exports" {
  bucket = google_storage_bucket.exports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "worker_exports" {
  bucket = google_storage_bucket.exports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_service_identity" "cloud_sql" {
  provider = google-beta
  project  = var.project_id
  service  = "sqladmin.googleapis.com"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "cloud_sql_logical_backups" {
  bucket = google_storage_bucket.logical_backups.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_project_service_identity.cloud_sql.email}"
}

resource "google_artifact_registry_repository_iam_member" "runtime_readers" {
  for_each = local.runtime_service_accounts

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.containers.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value}"
}

resource "google_artifact_registry_repository_iam_member" "additional_readers" {
  for_each = var.artifact_reader_members

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.containers.repository_id
  role       = "roles/artifactregistry.reader"
  member     = each.value
}

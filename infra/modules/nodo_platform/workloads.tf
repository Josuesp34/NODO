resource "google_cloud_run_v2_service" "api" {
  count = var.deploy_workloads ? 1 : 0

  project             = var.project_id
  name                = "${local.resource_prefix}-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection
  labels              = local.labels

  template {
    service_account                  = google_service_account.api.email
    timeout                          = "60s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.main.name
        subnetwork = google_compute_subnetwork.cloud_run.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      name  = "api"
      image = var.api_image

      ports {
        container_port = var.api_container_port
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        initial_delay_seconds = 3
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 12
        http_get {
          path = "/health"
          port = var.api_container_port
        }
      }

      liveness_probe {
        timeout_seconds   = 3
        period_seconds    = 30
        failure_threshold = 3
        http_get {
          path = "/health"
          port = var.api_container_port
        }
      }

      dynamic "env" {
        for_each = local.api_runtime_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.api_runtime_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[env.value.secret_id].secret_id
              version = env.value.version
            }
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
      error_message = "deploy_workloads requiere api_image fijada por digest sha256."
    }
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.required,
    google_project_iam_member.database_client,
    google_secret_manager_secret_iam_member.runtime_access,
    google_storage_bucket_iam_member.api_fit,
    google_project_iam_member.api_vertex_prompt,
    terraform_data.runtime_contract,
  ]
}

resource "google_cloud_run_v2_service" "pwa" {
  count = var.deploy_workloads ? 1 : 0

  project             = var.project_id
  name                = "${local.resource_prefix}-pwa"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection
  labels              = local.labels

  template {
    service_account                  = google_service_account.pwa.email
    timeout                          = "60s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.pwa_min_instances
      max_instance_count = var.pwa_max_instances
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.main.name
        subnetwork = google_compute_subnetwork.cloud_run.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      name  = "pwa"
      image = var.pwa_image

      ports {
        container_port = var.pwa_container_port
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        initial_delay_seconds = 3
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 12
        http_get {
          path = "/"
          port = var.pwa_container_port
        }
      }

      dynamic "env" {
        for_each = merge(var.pwa_env, {
          NODO_API_URL            = "${google_cloud_run_v2_service.api[0].uri}/api/v1"
          NODO_CLOUD_RUN_AUDIENCE = google_cloud_run_v2_service.api[0].uri
          SESSION_COOKIE_SECURE   = "true"
          NODO_APP_ORIGIN         = var.public_app_url
        })
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.pwa_secret_bindings
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[env.value.secret_id].secret_id
              version = env.value.version
            }
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", var.pwa_image))
      error_message = "deploy_workloads requiere pwa_image fijada por digest sha256."
    }
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_cloud_run_v2_service.api,
    google_secret_manager_secret_iam_member.runtime_access,
  ]
}

resource "google_cloud_run_v2_job" "migration" {
  count = var.deploy_workloads ? 1 : 0

  project             = var.project_id
  name                = "${local.resource_prefix}-migrate"
  location            = var.region
  deletion_protection = var.deletion_protection
  labels              = local.labels

  template {
    template {
      service_account = google_service_account.migration.email
      timeout         = "1800s"
      max_retries     = 0

      vpc_access {
        network_interfaces {
          network    = google_compute_network.main.name
          subnetwork = google_compute_subnetwork.cloud_run.name
        }
        egress = "PRIVATE_RANGES_ONLY"
      }

      containers {
        name    = "migration"
        image   = var.api_image
        command = var.migration_command
        args    = var.migration_args

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        dynamic "env" {
          for_each = var.migration_secret_bindings
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.runtime[env.value.secret_id].secret_id
                version = env.value.version
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
      error_message = "deploy_workloads requiere api_image fijada por digest sha256."
    }
    ignore_changes = [template[0].template[0].containers[0].image]
  }

  depends_on = [
    google_project_iam_member.database_client,
    google_secret_manager_secret_iam_member.runtime_access,
  ]
}

resource "google_cloud_run_v2_worker_pool" "worker" {
  provider = google-beta
  count    = var.deploy_workloads && var.enable_worker ? 1 : 0

  project             = var.project_id
  name                = "${local.resource_prefix}-worker"
  location            = var.region
  deletion_protection = var.deletion_protection
  labels              = local.labels

  template {
    service_account = google_service_account.worker.email

    vpc_access {
      network_interfaces {
        network    = google_compute_network.main.name
        subnetwork = google_compute_subnetwork.cloud_run.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      name    = "worker"
      image   = var.api_image
      command = var.worker_command
      args    = var.worker_args

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.worker_runtime_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.worker_runtime_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[env.value.secret_id].secret_id
              version = env.value.version
            }
          }
        }
      }
    }
  }

  scaling {
    scaling_mode          = "MANUAL"
    manual_instance_count = var.worker_instances
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
      error_message = "enable_worker requiere api_image fijada por digest sha256."
    }
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_iam_member.database_client,
    google_secret_manager_secret_iam_member.runtime_access,
    google_storage_bucket_iam_member.worker_fit,
    google_storage_bucket_iam_member.worker_exports,
    terraform_data.runtime_contract,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "pwa_public" {
  count = var.deploy_workloads ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.pwa[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "pwa_calls_api" {
  count = var.deploy_workloads ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pwa.email}"
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  count = var.deploy_workloads && var.api_allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

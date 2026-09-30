# All providers are mocks. No project, remote state, identity, or Cloud APIs are used.
mock_provider "google" {
  override_during = plan
  mock_data "google_project" {
    defaults = { number = "123456789" }
  }
}
mock_provider "google-beta" {
  override_during = plan
}

variables {
  project_id         = "nodo-synthetic-test"
  environment        = "staging"
  region             = "us-central1"
  database_tier      = "db-custom-1-3840"
  bucket_name_prefix = "nodo-synthetic-test"
  github_repository  = "synthetic/nodo"
}

run "private_storage_and_disabled_providers" {
  command = plan
  assert {
    condition     = local.api_runtime_env.STORAGE_BACKEND == "gcs" && local.worker_runtime_env.STORAGE_BUCKET == google_storage_bucket.fit.name
    error_message = "API/worker require the same configured private GCS bucket."
  }
  assert {
    condition     = google_storage_bucket.fit.soft_delete_policy[0].retention_duration_seconds == 0 && google_storage_bucket.exports.soft_delete_policy[0].retention_duration_seconds == 0 && google_storage_bucket.logical_backups.soft_delete_policy[0].retention_duration_seconds == 604800
    error_message = "User erasure and backup recovery need distinct explicit soft-delete policies."
  }
  assert {
    condition     = local.ai_env.AI_PROVIDER == "simulated" && length(google_project_iam_member.api_vertex_prompt) == 0 && !contains(local.required_services, "aiplatform.googleapis.com")
    error_message = "Vertex API/IAM must remain disabled until approved."
  }
}

run "vertex_and_provider_binding_contract" {
  command = plan
  variables {
    enable_vertex_ai    = true
    enable_intervals    = true
    enable_web_push     = true
    public_app_url      = "https://nodo.example"
    web_push_public_key = "synthetic-public-key"
    web_push_contact    = "mailto:operator@example.com"
    provider_secret_versions = {
      intervals-client-id           = "1"
      intervals-client-secret       = "2"
      intervals-webhook-secret      = "3"
      provider-token-encryption-key = "4"
      web-push-private-key          = "5"
      push-encryption-key           = "6"
    }
    ai_configuration = {
      model                  = "synthetic-model"
      location               = "us-central1"
      user_monthly_usd       = 1
      org_monthly_usd        = 10
      input_usd_per_million  = 1
      output_usd_per_million = 2
    }
  }
  assert {
    condition     = google_project_iam_custom_role.vertex_prompt[0].permissions == toset(["aiplatform.endpoints.predict"]) && length(google_project_iam_member.api_vertex_prompt) == 1
    error_message = "Vertex permission must be inference-only and granted to API."
  }
  assert {
    condition     = !contains(keys(local.worker_runtime_secrets), "INTERVALS_CLIENT_SECRET") && local.worker_runtime_secrets.PROVIDER_TOKEN_ENCRYPTION_KEY.version == "4" && local.api_runtime_secrets.WEB_PUSH_PRIVATE_KEY.version == "5"
    error_message = "Only necessary provider secrets may be bound to each runtime."
  }
  assert {
    condition     = local.provider_env.INTERVALS_REDIRECT_URI == "https://nodo.example/athlete/connections/intervals/callback"
    error_message = "OAuth callback belongs to public PWA, never private API."
  }
}

run "reject_public_api" {
  command = plan
  variables { api_allow_unauthenticated = true }
  expect_failures = [var.api_allow_unauthenticated]
}

run "workloads_keep_storage_private_and_pwa_managed" {
  command = plan
  variables {
    deploy_workloads          = true
    enable_worker             = true
    public_app_url            = "https://nodo.example"
    api_image                 = "us-central1-docker.pkg.dev/synthetic/nodo/api@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    pwa_image                 = "us-central1-docker.pkg.dev/synthetic/nodo/pwa@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    api_secret_bindings       = { DATABASE_URL = { secret_id = "database-url", version = "1" } }
    worker_secret_bindings    = { DATABASE_URL = { secret_id = "database-url", version = "1" } }
    migration_secret_bindings = { DATABASE_URL = { secret_id = "database-url", version = "1" } }
    pwa_env                   = { SESSION_COOKIE_SECURE = "false", NODO_API_URL = "http://untrusted.example" }
  }
  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.api_public) == 0
    error_message = "API must never be exposed to allUsers."
  }
  assert {
    condition = alltrue([for item in google_cloud_run_v2_service.pwa[0].template[0].containers[0].env :
    item.name == "SESSION_COOKIE_SECURE" ? item.value == "true" : item.name == "NODO_APP_ORIGIN" ? item.value == "https://nodo.example" : true])
    error_message = "PWA security bindings cannot be overridden by free-form env."
  }
  assert {
    condition = alltrue([for item in google_cloud_run_v2_worker_pool.worker[0].template[0].containers[0].env :
    item.name == "STORAGE_BACKEND" ? item.value == "gcs" : item.name == "STORAGE_BUCKET" ? item.value == google_storage_bucket.fit.name : true])
    error_message = "Worker must be able to delete the same private storage generations."
  }
}

run "reject_missing_provider_versions" {
  command = plan
  variables { enable_intervals = true }
  expect_failures = [terraform_data.runtime_contract]
}

run "reject_unapproved_paid_calls" {
  command = plan
  variables { enable_vertex_ai = true }
  expect_failures = [terraform_data.runtime_contract]
}

run "reject_latest_secret_alias" {
  command = plan
  variables { provider_secret_versions = { intervals-client-secret = "latest" } }
  expect_failures = [var.provider_secret_versions]
}

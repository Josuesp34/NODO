output "platform" {
  value = {
    artifact_repository               = module.nodo.artifact_repository
    database_connection_name          = module.nodo.database_connection_name
    fit_bucket                        = module.nodo.fit_bucket
    exports_bucket                    = module.nodo.exports_bucket
    logical_backups_bucket            = module.nodo.logical_backups_bucket
    github_workload_identity_provider = module.nodo.github_workload_identity_provider
    github_deploy_service_account     = module.nodo.github_deploy_service_account
    api_uri                           = module.nodo.api_uri
    pwa_uri                           = module.nodo.pwa_uri
  }
}

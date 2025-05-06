resource "google_cloud_run_v2_service" "web_scraper_service" {
  provider = google
  name     = "web-scraper"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_sa.email
    timeout         = "3600s"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.web_scraper.repository_id}/production:latest"
      resources {
        limits = {
          memory = "2Gi"
          cpu    = "1"
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "PROXY_LIST_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.proxy_list_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "ML_PAPERS_BUCKET_NAME"
        value = google_storage_bucket.ml_papers.name
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.database_url_accessor,
    google_secret_manager_secret_iam_member.proxy_list_url_accessor,
  ]
}

resource "google_cloud_run_v2_service" "pdf_processor_service" {
  provider = google
  name     = "pdf-processor"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    service_account                  = google_service_account.cloud_run_sa.email
    timeout                          = "3600s"
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    max_instance_request_concurrency = 1

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.pdf_processor.repository_id}/production:latest"
      resources {
        limits = {
          memory           = "16Gi"
          cpu              = "4"
          "nvidia.com/gpu" = "1"
        }
        cpu_idle          = false
        startup_cpu_boost = true
      }

      env {
        name  = "ML_PAPERS_BUCKET_NAME"
        value = google_storage_bucket.ml_papers.name
      }
    }
  }
}

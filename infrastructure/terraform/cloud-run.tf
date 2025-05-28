resource "google_cloud_run_v2_job" "web_scraper_worker" {
  provider = google
  name     = "web-scraper-worker"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    template {
      service_account       = google_service_account.cloud_run_sa.email
      timeout               = "86400s"
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      max_retries           = 10

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.web_scraper_worker.repository_id}/production:latest"

        resources {
          limits = {
            memory = "4Gi"
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
  }
}

resource "google_cloud_run_v2_job" "markdown_processor" {
  provider = google
  name     = "markdown-processor"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    template {
      service_account       = google_service_account.cloud_run_sa.email
      timeout               = "86400s"
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.markdown_processor.repository_id}/production:latest"

		resources {
		  limits = {
			memory = "1Gi"
			cpu    = "1"
		  }
		}

        env {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gemini_api_key.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.openai_api_key.secret_id
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
  }
}

resource "google_cloud_run_v2_service" "web_scraper_service" {
  provider = google
  name     = "web-scraper-service"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    service_account                  = google_service_account.cloud_run_sa.email
    timeout                          = "3600s"
    max_instance_request_concurrency = 1
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.web_scraper_service.repository_id}/production:latest"

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
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "JOB_NAME"
        value = google_cloud_run_v2_job.web_scraper_worker.name
      }
      env {
        name  = "REGION"
        value = var.region
      }
    }
  }
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
    gpu_zonal_redundancy_disabled    = true

    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.pdf_processor.repository_id}/production:latest"
      resources {
        limits = {
          memory           = "16Gi"
          cpu              = "4"
          "nvidia.com/gpu" = "1"
        }
        cpu_idle = false
      }

      env {
        name  = "ML_PAPERS_BUCKET_NAME"
        value = google_storage_bucket.ml_papers.name
      }
    }

    node_selector {
      accelerator = "nvidia-l4"
    }
  }
}

resource "google_project_iam_member" "cloud_run_sa_job_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

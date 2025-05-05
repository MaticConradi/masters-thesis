resource "google_cloud_run_v2_service" "web_scraper_service" {
  provider = google
  name     = "web-scraper"
  location = var.region
  project  = var.project_id

  deletion_protection = false

  template {
    service_account = "${var.cloud_run_sa_email}@${var.project_id}.iam.gserviceaccount.com"
    timeout         = "3600s"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.web_scraper.repository_id}/production:latest"
      resources {
        limits = {
          memory = "1Gi"
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
		name = "ML_PAPERS_BUCKET_NAME"
		value = google_storage_bucket.ml_papers.name
	  }
    }
  }

  depends_on = [
    google_artifact_registry_repository.web_scraper,
    google_secret_manager_secret_iam_member.database_url_accessor,
    google_secret_manager_secret_iam_member.proxy_list_url_accessor,
  ]
}

resource "google_secret_manager_secret_iam_member" "database_url_accessor" {
  project    = google_secret_manager_secret.database_url.project
  secret_id  = google_secret_manager_secret.database_url.secret_id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${var.cloud_run_sa_email}@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "proxy_list_url_accessor" {
  project    = google_secret_manager_secret.proxy_list_url.project
  secret_id  = google_secret_manager_secret.proxy_list_url.secret_id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${var.cloud_run_sa_email}@${var.project_id}.iam.gserviceaccount.com"
}
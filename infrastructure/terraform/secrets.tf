resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "proxy_list_url" {
  project   = var.project_id
  secret_id = "proxy-list-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "gemini_api_key" {
  project   = var.project_id
  secret_id = "gemini-api-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "database_url_accessor" {
  project    = google_secret_manager_secret.database_url.project
  secret_id  = google_secret_manager_secret.database_url.secret_id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "proxy_list_url_accessor" {
  project    = google_secret_manager_secret.proxy_list_url.project
  secret_id  = google_secret_manager_secret.proxy_list_url.secret_id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}
resource "google_secret_manager_secret_iam_member" "gemini_api_key_accessor" {
  project    = google_secret_manager_secret.gemini_api_key.project
  secret_id  = google_secret_manager_secret.gemini_api_key.secret_id
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}
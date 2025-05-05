resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "database_url_accessor" {
  project   = google_secret_manager_secret.database_url.project
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.project_number}-compute@developer.gserviceaccount.com"
}

# 2. Proxy List URL Secret
resource "google_secret_manager_secret" "proxy_list_url" {
  project   = var.project_id
  secret_id = "proxy-list-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "proxy_list_url_accessor" {
  project   = google_secret_manager_secret.proxy_list_url.project
  secret_id = google_secret_manager_secret.proxy_list_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.project_number}-compute@developer.gserviceaccount.com"
}

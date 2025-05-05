resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "database-url"

  replication {
    auto {}
  }
}

# 2. Proxy List URL Secret
resource "google_secret_manager_secret" "proxy_list_url" {
  project   = var.project_id
  secret_id = "proxy-list-url"

  replication {
    auto {}
  }
}
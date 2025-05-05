resource "google_artifact_registry_repository" "web_scraper" {
  provider      = google
  location      = var.region
  repository_id = "web-scraper"
  description   = "Web scraper repository (masters thesis)"
  format        = "DOCKER"
}
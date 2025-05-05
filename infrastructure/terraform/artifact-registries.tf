resource "google_artifact_registry_repository" "scraper" {
  provider      = google
  location      = var.region
  repository_id = "scraper"
  description   = "Web scraper repository (masters thesis)"
  format        = "DOCKER"
}
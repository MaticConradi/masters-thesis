resource "google_artifact_registry_repository" "web_scraper" {
  provider      = google
  location      = var.region
  repository_id = "web-scraper"
  description   = "Web scraper repository (masters thesis)"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "pdf_processor" {
  provider      = google
  location      = var.region
  repository_id = "pdf-processor"
  description   = "PDF processor repository (masters thesis)"
  format        = "DOCKER"
}
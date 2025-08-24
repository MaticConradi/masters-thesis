resource "google_artifact_registry_repository" "web_scraper_service" {
  provider      = google
  location      = var.region
  repository_id = "web-scraper-service"
  description   = "Web Scraper Service repository (masters thesis)"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "web_scraper_worker" {
  provider      = google
  location      = var.region
  repository_id = "web-scraper-worker"
  description   = "Web Scraper Worker repository (masters thesis)"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "pdf_processor" {
  provider      = google
  location      = var.region
  repository_id = "pdf-processor"
  description   = "PDF Processor repository (masters thesis)"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "markdown_processor" {
  provider      = google
  location      = var.region
  repository_id = "markdown-processor"
  description   = "Markdown Processor repository (masters thesis)"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "retrieval_service" {
  provider      = google
  location      = var.region
  repository_id = "retrieval-service"
  description   = "Retrieval Service repository (masters thesis)"
  format        = "DOCKER"
}
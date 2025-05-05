variable "bucket_prefix" {
  description = "Prefix for GCS bucket names"
  type        = string
}

resource "google_storage_bucket" "ml_papers" {
  name                        = "${var.bucket_prefix}-ml-papers"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  force_destroy = false
}

resource "google_storage_bucket_iam_member" "ml_papers_cloud_run_writer" {
	bucket = google_storage_bucket.ml_papers.name
	role   = "roles/storage.objectCreator"
	member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_storage_bucket_iam_member" "ml_papers_cloud_run_reader" {
	bucket = google_storage_bucket.ml_papers.name
	role   = "roles/storage.objectViewer"
	member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}
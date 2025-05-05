variable "bucket_prefix" {
  description = "Prefix for GCS bucket names"
  type        = string
}

# Input Bucket: For PDFs and metadata from Cloud Run
resource "google_storage_bucket" "ml_papers" {
  name                        = "${var.bucket_prefix}-ml-papers"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  force_destroy = false
}
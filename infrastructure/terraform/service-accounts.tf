variable "cloud_run_sa_email" {
  description = "The email address of the Service Account used by your Cloud Run service."
  type        = string
  default = "cloud-run-sa"
}

resource "google_service_account" "cloud_run_sa" {
  account_id   = var.cloud_run_sa_email
  display_name = "Cloud Run Service Account"
  project      = var.project_id
  description  = "Service Account for Cloud Run to access necessary resources."
}
# 1. Workload Identity Pool
resource "google_iam_workload_identity_pool" "github_pool" {
  provider                  = google
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-identity-pool"
  display_name              = "Github Identity Pool"
  description               = "Workload Identity Pool for Github Actions"
}

# 2. Workload Identity Pool Provider
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  provider                           = google
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-identity-provider"
  display_name                       = "Github Identity Provider"
  description                        = "Workload Identity Provider for Github Actions"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.aud"              = "assertion.aud"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository_owner == 'MaticConradi'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# 3. Service Account for Github Actions
resource "google_service_account" "github_actions_sa" {
  provider     = google
  project      = var.project_id
  account_id   = "github-actions-sa"
  display_name = "Github Actions SA"
  description  = "Service Account for Github Actions"
}

# 4. Grant IAM Roles to the Service Account

# Allow SA to manage Cloud Run services
resource "google_project_iam_member" "run_admin" {
  provider = google
  project  = var.project_id
  role     = "roles/run.admin"
  member   = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

# Allow SA to be impersonated by Workload Identity Pool
resource "google_project_iam_member" "service_account_user" {
  provider = google
  project  = var.project_id
  role     = "roles/iam.serviceAccountUser"
  member   = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

# Allow SA to read/write/delete from Artifact Registry
resource "google_project_iam_member" "artifact_registry_admin" {
	provider = google
	project  = var.project_id
	role     = "roles/artifactregistry.admin"
	member   = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

# 5. IAM Policy Binding for Workload Identity User Role
# Allows Github Actions from the specified repository to impersonate the Service Account
resource "google_service_account_iam_binding" "github_actions_wif_binding" {
  provider           = google
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github_pool.workload_identity_pool_id}/attribute.repository/MaticConradi/masters-thesis",
    "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github_pool.workload_identity_pool_id}/attribute.repository/MaticConradi/scraper",
  ]
}

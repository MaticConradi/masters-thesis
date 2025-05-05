resource "google_bigquery_dataset" "mc_magistrska" {
  dataset_id = "mc_magistrska"
  project    = var.project_id
  location   = "EU"
}

resource "google_bigquery_table" "articles" {
  dataset_id = google_bigquery_dataset.mc_magistrska.dataset_id
  table_id   = "articles"

  schema = jsonencode([
    {
      name = "url"
      type = "STRING"
      mode = "REQUIRED"
      description = "URL of the article"
    },
    {
      name = "title"
      type = "STRING"
      mode = "REQUIRED"
      description = "Title of the article"
    },
    {
      name = "text"
      type = "STRING"
      mode = "REQUIRED"
      description = "Text of the article"
    },
    {
      name = "origin"
      type = "STRING"
      mode = "REQUIRED"
      description = "Origin URL of the article"
    },
    {
      name = "tasks"
      type = "STRING"
      mode = "REPEATED"
      description = "Tasks that the article is related to"
    },
    {
      name = "datasets"
      type = "STRING"
      mode = "REPEATED"
      description = "Datasets that the article is related to"
    },
    {
      name = "results"
      type = "RECORD"
      mode = "REPEATED"
      description = "Results of the article"
      fields = [
        {
          name = "task"
          type = "STRING"
          mode = "REQUIRED"
          description = "Task that the result is related to"
        },
        {
          name = "dataset"
          type = "STRING"
          mode = "REQUIRED"
          description = "Dataset that the result is related to"
        },
        {
          name = "model"
          type = "STRING"
          mode = "REQUIRED"
          description = "Model that the result is related to"
        },
        {
          name = "metric"
          type = "STRING"
          mode = "REQUIRED"
          description = "Metric of the result"
        },
        {
          name = "value"
          type = "STRING"
          mode = "REQUIRED"
          description = "Value of the result"
        },
        {
          name = "rank"
          type = "INTEGER"
          mode = "REQUIRED"
          description = "Rank of the result"
        },
      ]
    },
    {
      name = "methods"
      type = "STRING"
      mode = "REPEATED"
      description = "Methods that the article is related to"
    }
  ])
}

resource "google_project_iam_member" "mc_magistrska_cloud_run_job_user" {
	project    = var.project_id
	role       = "roles/bigquery.admin"
	member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "mc_magistrska_cloud_run_job_user_project" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}
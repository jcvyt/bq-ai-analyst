resource "google_service_account" "analyst_agent" {
  account_id   = "sa-analyst-agent"
  display_name = "BQ AI Analyst agent runtime"
  description  = "Cloud Run runtime identity. Reads semantic dataset only."
}

resource "google_project_iam_member" "agent_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.analyst_agent.email}"
}

# Test-as-agent without keys (keys are blocked by org policy anyway)
resource "google_service_account_iam_member" "admins_impersonate_agent" {
  service_account_id = google_service_account.analyst_agent.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "group:${var.admins_group}"
}

# Create the DLP service agent explicitly (otherwise lazily created -> 404 on first job)
resource "google_project_service_identity" "dlp" {
  provider   = google-beta
  project    = var.project_id
  service    = "dlp.googleapis.com"
  depends_on = [google_project_service.svc]
}

resource "google_project_iam_member" "dlp_agent" {
  project = var.project_id
  role    = "roles/dlp.serviceAgent"
  member  = "serviceAccount:${google_project_service_identity.dlp.email}"
}

# No impersonate_service_account here on purpose:
# - locally: GOOGLE_IMPERSONATE_SERVICE_ACCOUNT env var
# - CI (Day 7): WIF authenticates directly AS sa-tf-ci
provider "google" {
  project = var.project_id
  region  = var.region
  default_labels = {
    env        = "dev"
    app        = "bq-ai-analyst"
    managed-by = "terraform"
  }
}

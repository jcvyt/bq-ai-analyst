locals {
  services = [
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "dlp.googleapis.com",
  ]
}

resource "google_project_service" "svc" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

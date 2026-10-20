resource "google_storage_bucket" "tfstate" {
  name                        = "${var.bootstrap_project}-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning { enabled = true }

  lifecycle_rule {
    condition { num_newer_versions = 10 }
    action { type = "Delete" }
  }

  labels = { app = "bq-ai-analyst", layer = "bootstrap" }
}

output "tfstate_bucket" {
  value = google_storage_bucket.tfstate.name
}

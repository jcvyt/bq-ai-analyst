locals {
  staging = {
    us   = "US"              # Day 5: export target (source is US multi-region)
    use4 = upper(var.region) # Day 5: load source for us-east4 datasets
  }
}

resource "google_storage_bucket" "staging" {
  for_each                    = local.staging
  name                        = "${var.project_id}-staging-${each.key}"
  location                    = each.value
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # ephemeral staging only -- never on data buckets

  soft_delete_policy {
    retention_duration_seconds = 0 # FinOps: no 7-day soft-delete charges on churned staging files
  }

  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }

  labels = { purpose = "staging" }

  depends_on = [google_project_service.svc]
}

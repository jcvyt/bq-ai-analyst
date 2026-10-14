resource "google_org_policy_policy" "public_access_prevention" {
  name   = "organizations/${var.org_id}/policies/storage.publicAccessPrevention"
  parent = "organizations/${var.org_id}"
  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

resource "google_org_policy_policy" "resource_locations" {
  name   = "folders/${var.folder_id}/policies/gcp.resourceLocations"
  parent = "folders/${var.folder_id}"
  spec {
    rules {
      values {
        allowed_values = ["in:us-locations"]
      }
    }
  }
}

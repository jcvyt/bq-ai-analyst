locals {
  admins     = "group:gcp-admins@${var.domain}"
  billing    = "group:gcp-billing@${var.domain}"
  developers = "group:gcp-developers@${var.domain}"
  folder     = "folders/${var.folder_id}"
  org_parent = "organizations/${var.org_id}"
}

resource "google_organization_iam_member" "admins_orgpolicy" {
  org_id = var.org_id
  role   = "roles/orgpolicy.policyAdmin"
  member = local.admins
}

resource "google_folder_iam_member" "admins_folder" {
  for_each = toset(["roles/resourcemanager.folderAdmin", "roles/owner"])
  folder   = local.folder
  role     = each.value
  member   = local.admins
}

resource "google_billing_account_iam_member" "billing" {
  for_each           = toset(["roles/billing.costsManager", "roles/billing.viewer"])
  billing_account_id = var.billing_account
  role               = each.value
  member             = local.billing
}

resource "google_folder_iam_member" "developers" {
  for_each = toset(["roles/viewer", "roles/bigquery.jobUser"])
  folder   = local.folder
  role     = each.value
  member   = local.developers
}

# infra/bootstrap/iam_org.tf
resource "google_organization_iam_member" "admins_asset_viewer" {
  org_id = var.org_id
  role   = "roles/cloudasset.viewer"
  member = local.admins
}
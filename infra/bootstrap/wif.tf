# ---------------------------------------------------------------------------
# Workload Identity Federation for GitHub Actions
# ---------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.bootstrap_project
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.bootstrap_project
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Mandatory: only YOUR repo can exchange tokens
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ---------------------------------------------------------------------------
# CI service account
# ---------------------------------------------------------------------------

resource "google_service_account" "tf_ci" {
  project      = var.bootstrap_project
  account_id   = "sa-tf-ci"
  display_name = "Terraform CI for envs/dev"
}

# Allow GitHub Actions (scoped to your repo) to impersonate the CI SA
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.tf_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Admins impersonate the CI SA locally instead of holding write perms themselves
resource "google_service_account_iam_member" "admins_impersonate" {
  service_account_id = google_service_account.tf_ci.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.admins
}

# ---------------------------------------------------------------------------
# State bucket + workload project permissions
# ---------------------------------------------------------------------------

resource "google_storage_bucket_iam_member" "ci_state" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.tf_ci.member
}

resource "google_project_iam_member" "ci_workload" {
  for_each = toset([
    "roles/bigquery.admin",
    "roles/storage.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    # escalation risk: constrain with IAM Conditions in Phase 2
    "roles/resourcemanager.projectIamAdmin",
    "roles/logging.configWriter",
    "roles/serviceusage.serviceUsageAdmin",
  ])
  project = var.workload_project
  role    = each.value
  member  = google_service_account.tf_ci.member
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "tf_ci_sa" {
  value = google_service_account.tf_ci.email
}

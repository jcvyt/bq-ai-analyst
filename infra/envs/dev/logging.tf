locals {
  ops_audit_dataset_id = "ops_audit"
}

resource "google_logging_project_sink" "bq_audit" {
  project = var.project_id
  name    = "bq-audit-to-ops-audit"
  # String-built, not google_bigquery_dataset.ds["ops_audit"].id — avoids the cycle
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${local.ops_audit_dataset_id}"
  unique_writer_identity = true

  filter = <<-EOT
    (log_id("cloudaudit.googleapis.com/data_access") OR log_id("cloudaudit.googleapis.com/activity"))
    AND protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.BigQueryAuditMetadata"
    AND NOT protoPayload.authenticationInfo.principalEmail:"gcp-sa-logging.iam.gserviceaccount.com"
  EOT

  bigquery_options {
    use_partitioned_tables = true
  }
}
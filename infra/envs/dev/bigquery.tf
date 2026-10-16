locals {
  datasets = {
    raw_thelook = { desc = "Landing copy of thelook_ecommerce. Contains PII. No agent access.", data_class = "confidential" }
    curated     = { desc = "Cleaned, conformed tables. Read only via authorized views.",        data_class = "confidential" }
    semantic    = { desc = "Governed views/metrics exposed to the AI analyst agent.",          data_class = "internal" }
    ops_audit   = { desc = "Agent query audit + log sink target.",                             data_class = "internal" }
    ops_eval    = { desc = "Golden questions and eval run results.",                           data_class = "internal" }
  }
}

resource "google_bigquery_dataset" "ds" {
  for_each                   = local.datasets
  dataset_id                 = each.key
  location                   = var.region
  description                = each.value.desc
  max_time_travel_hours      = "48"
  delete_contents_on_destroy = false

  labels = {
    layer      = replace(each.key, "_", "-")
    data-class = each.value.data_class
  }

  depends_on = [google_project_service.svc]
}

# Authorized dataset: views in `semantic` may read `curated`
resource "google_bigquery_dataset_access" "semantic_reads_curated" {
  dataset_id = google_bigquery_dataset.ds["curated"].dataset_id
  dataset {
    dataset {
      project_id = var.project_id
      dataset_id = google_bigquery_dataset.ds["semantic"].dataset_id
    }
    target_types = ["VIEWS"]
  }
}

# Agent: read semantic only.
# Use legacy "READER", not roles/bigquery.dataViewer -- the API rewrites it and you get a perpetual diff.
resource "google_bigquery_dataset_access" "agent_semantic_reader" {
  dataset_id    = google_bigquery_dataset.ds["semantic"].dataset_id
  role          = "READER"
  user_by_email = google_service_account.analyst_agent.email
}

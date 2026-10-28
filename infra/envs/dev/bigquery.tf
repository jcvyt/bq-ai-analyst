locals {
  datasets = {
    raw_thelook = { desc = "Landing copy of thelook_ecommerce. Contains PII. No agent access.", data_class = "confidential" }
    curated     = { desc = "Cleaned, conformed tables. Read only via authorized views.", data_class = "confidential" }
    semantic    = { desc = "Governed views/metrics exposed to the AI analyst agent.", data_class = "internal" }
    ops_audit   = { desc = "Agent query audit + log sink target.", data_class = "internal" }
    ops_eval    = { desc = "Golden questions and eval run results.", data_class = "internal" }
  }

  raw_access = [
    { role = "OWNER", special_group = "projectOwners", group_by_email = null },
    { role = "OWNER", special_group = null, group_by_email = var.admins_group },
  ]

  # NEW: Moved OUTSIDE the datasets map
  ops_audit_access = [
    # Keep at least one owner. 'projectOwners' is the safest generic choice.
    {
      role           = "OWNER",
      special_group  = "projectOwners",
      group_by_email = null,
      user_by_email  = null
    },
    # The sink writer you already added.
    {
      role           = "WRITER",
      special_group  = null,
      group_by_email = null,
      user_by_email  = trimprefix(google_logging_project_sink.bq_audit.writer_identity, "serviceAccount:")
    }
  ]
}

resource "google_bigquery_dataset" "ds" {
  for_each                   = local.datasets
  dataset_id                 = each.key
  location                   = var.region
  description                = each.value.desc
  max_time_travel_hours      = "48"
  delete_contents_on_destroy = false

  # NEW: 90-day partition expiry, ops_audit only (sink's tables are partitioned)
  default_partition_expiration_ms = each.key == "ops_audit" ? 90 * 24 * 60 * 60 * 1000 : null

  labels = merge(
    {
      layer      = replace(each.key, "_", "-")
      data-class = each.value.data_class
    },
    each.key == "ops_eval" ? { phase = "2" } : {},
  )
  depends_on = [google_project_service.svc]

  # existing: raw_thelook owners (unchanged)
  dynamic "access" {
    for_each = [for a in local.raw_access : a if each.key == "raw_thelook"]
    content {
      role           = access.value.role
      special_group  = access.value.special_group
      group_by_email = access.value.group_by_email
    }
  }

  # NEW block for ops_audit (owners + sink writer)
  dynamic "access" {
    for_each = each.key == "ops_audit" ? local.ops_audit_access : []
    content {
      role           = access.value.role
      special_group  = access.value.special_group
      group_by_email = access.value.group_by_email
      user_by_email  = access.value.user_by_email
    }
  }
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

resource "google_bigquery_dataset_access" "devs_reader" {
  for_each       = toset(["curated", "semantic", "ops_eval"])
  dataset_id     = google_bigquery_dataset.ds[each.value].dataset_id
  role           = "READER"
  group_by_email = var.developers_group
}

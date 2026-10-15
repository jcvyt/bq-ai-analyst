output "agent_sa_email"  { value = google_service_account.analyst_agent.email }
output "datasets"        { value = keys(google_bigquery_dataset.ds) }
output "staging_buckets" { value = { for k, b in google_storage_bucket.staging : k => b.name } }
